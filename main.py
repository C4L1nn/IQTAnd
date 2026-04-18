"""iqtMusic — Giriş Noktası"""
import sys
import os
import time
import logging

# Proje kökünü Python yoluna ekle (modüler import için)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── VLC libvlc.dll yolu — import vlc'den ÖNCE ayarlanmalı ──────────────────
def _setup_vlc_path():
    """
    libvlc.dll'yi bulmak için VLC kurulum dizinlerini PATH'e ekler.
    python-vlc paketi ctypes ile libvlc.dll'yi arar; VLC kurulu ama
    PATH'de yoksa FileNotFoundError verir. Bu fonksiyon import'tan önce
    standart VLC konumlarını PATH'e ekler.
    """
    # Önce proje içi vlc/ klasörüne bak (taşınabilir kurulum)
    # PyInstaller frozen modda data dosyaları sys._MEIPASS altında olur
    if getattr(sys, "frozen", False):
        _base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        _base = os.path.dirname(os.path.abspath(__file__))
    for _local_vlc in (os.path.join(_base, "vlc"), _base):
        if not os.path.isfile(os.path.join(_local_vlc, "libvlc.dll")):
            continue
        os.environ["PATH"] = _local_vlc + os.pathsep + os.environ.get("PATH", "")
        _plugins = os.path.join(_local_vlc, "plugins")
        if os.path.isdir(_plugins):
            os.environ.setdefault("VLC_PLUGIN_PATH", _plugins)
        return

    # Windows standart VLC kurulum yerleri
    _candidates = [
        r"C:\Program Files\VideoLAN\VLC",
        r"C:\Program Files (x86)\VideoLAN\VLC",
        os.path.join(os.environ.get("PROGRAMFILES", ""), "VideoLAN", "VLC"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "VideoLAN", "VLC"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "VLC"),
    ]
    for _p in _candidates:
        if _p and os.path.isfile(os.path.join(_p, "libvlc.dll")):
            os.environ["PATH"] = _p + os.pathsep + os.environ.get("PATH", "")
            _plugins = os.path.join(_p, "plugins")
            if os.path.isdir(_plugins):
                os.environ.setdefault("VLC_PLUGIN_PATH", _plugins)
            break

_setup_vlc_path()
# ────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger("iqtMusic")

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from PySide6.QtCore import QTimer, qInstallMessageHandler
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from core.constants import THEMES, FONT_MAIN, APP_VERSION
from core.app import IqtMusic
from core.i18n import DEFAULT_LANGUAGE, normalize_language, translate
from ui.splash import MusicSplashScreen
from utils.helpers import get_app_dir, safe_load_json
from utils.updater import run_update_check


_INSTANCE_SERVER_NAME = "iqtMusicElite_single_instance"
_QT_SUPPRESSED_WARNINGS = (
    "QFont::setPointSize: Point size <= 0",
)


def _install_qt_message_filter():
    def _qt_message_handler(_msg_type, _context, message):
        text = str(message or "")
        for ignored in _QT_SUPPRESSED_WARNINGS:
            if ignored in text:
                return
        sys.stderr.write(f"{text}\n")
        sys.stderr.flush()

    qInstallMessageHandler(_qt_message_handler)


def _load_ui_language() -> str:
    settings_file = os.path.join(get_app_dir("iqtMusicElite"), "settings.json")
    settings = safe_load_json(settings_file, {})
    return normalize_language(settings.get("language", DEFAULT_LANGUAGE))


def _parse_join_code_from_args() -> str | None:
    """sys.argv içinden iqtmusic://join/ROOMCODE URL'ini ayrıştırır."""
    for arg in sys.argv[1:]:
        if arg.lower().startswith("iqtmusic://join/"):
            code = arg[len("iqtmusic://join/"):]
            code = code.strip("/").strip()
            if code:
                return code
    return None


def _notify_running_instance(join_code: str | None = None) -> bool:
    socket = QLocalSocket()
    socket.connectToServer(_INSTANCE_SERVER_NAME)
    if not socket.waitForConnected(220):
        return False
    try:
        if join_code:
            msg = f"join:{join_code}".encode()
        else:
            msg = b"show"
        socket.write(msg)
        socket.flush()
        socket.waitForBytesWritten(220)
    except Exception as _e:
        log.debug("Sessiz hata: %s", _e)
    socket.disconnectFromServer()
    return True


def _install_single_instance_bridge(window):
    server = QLocalServer(window)
    # Eski/çökmüş process'ten kalma soket dosyasını her zaman temizle
    QLocalServer.removeServer(_INSTANCE_SERVER_NAME)
    if not server.listen(_INSTANCE_SERVER_NAME):
        log.warning("Single instance sunucusu başlatılamadı: %s", server.errorString())

    def _bring_existing_window_forward():
        try:
            window._show_window()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)

    def _handle_join(room_code: str):
        try:
            window._show_window()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        try:
            window.collab_join(room_code, from_discord=True)
        except Exception as _e:
            log.debug("Collab join hatası: %s", _e)

    def _handle_new_connection():
        while server.hasPendingConnections():
            socket = server.nextPendingConnection()
            if socket is None:
                continue
            socket.waitForReadyRead(400)
            data = bytes(socket.readAll()).decode("utf-8", errors="ignore").strip()
            if data.startswith("join:"):
                room_code = data[5:]
                QTimer.singleShot(0, lambda rc=room_code: _handle_join(rc))
            else:
                QTimer.singleShot(0, _bring_existing_window_forward)
            socket.disconnectFromServer()
            socket.deleteLater()

    server.newConnection.connect(_handle_new_connection)
    window._single_instance_server = server


def main():
    _install_qt_message_filter()
    app = QApplication(sys.argv)
    ui_lang = _load_ui_language()

    join_code = _parse_join_code_from_args()

    if _notify_running_instance(join_code):
        sys.exit(0)

    # Varsayılan tema rengini al
    default_theme  = THEMES.get("Yeşil")
    default_accent = default_theme["accent"]
    default_accent_hover = default_theme["accent_hover"]

    # Başlangıç stili (QSS override — ana stil _apply_styles'da uygulanır)
    app.setStyleSheet(f"""
    * {{
        outline: none;
        font-family: 'Segoe UI Variable Text', 'Segoe UI Variable', 'Segoe UI';
    }}
    QMainWindow, QWidget {{
        background-color: #121212;
        color: #E0E0E0;
    }}
    QPushButton {{
        background-color: #1E1E1E;
        border: 1px solid #333333;
        border-radius: 8px;
        padding: 8px 16px;
        color: #FFFFFF;
        font-size: 14px;
        font-weight: bold;
    }}
    QPushButton:hover {{
        background-color: #2A2A2A;
        border: 1px solid {default_accent};
    }}
    QPushButton:pressed {{
        background-color: #151515;
        border: 1px solid {default_accent};
    }}
    QSlider::groove:horizontal {{
        border-radius: 2px;
        height: 3px;
        background: #243042;
    }}
    QSlider::handle:horizontal {{
        background: {default_accent};
        width: 10px;
        height: 10px;
        margin: -4px 0;
        border-radius: 5px;
    }}
    QSlider::handle:horizontal:hover {{
        background: {default_accent_hover};
    }}
    QLineEdit {{
        background-color: #1E1E1E;
        border: 1px solid #333333;
        border-radius: 8px;
        padding: 8px;
        color: white;
        font-size: 14px;
    }}
    QLineEdit:focus {{
        border: 1px solid {default_accent};
    }}
    """)

    # ── Splash ekranı ─────────────────────────────────────────────────────
    splash_path = os.path.join(
        getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))),
        "assets", "splash_music.png"
    )
    splash = MusicSplashScreen(splash_path, accent=default_accent, subtitle=translate(ui_lang, "splash.subtitle"))
    splash.set_progress(0, translate(ui_lang, "splash.starting"))
    splash.show()
    app.processEvents()

    # ── Güncelleme kontrolü ───────────────────────────────────────────────
    # Splash animasyonu devam ederken arka planda ağ kontrolü yapar.
    # Güncelleme bulunursa diyalog açılır; kullanıcı kabul ederse
    # kurulum başlatılıp uygulama kapanır.
    splash.set_progress(5, translate(ui_lang, "splash.update_check"))
    app.processEvents()
    if run_update_check(APP_VERSION, accent=default_accent, lang=ui_lang):
        # Güncelleme başlatıldı: updater arka planda 1.2sn sonra os._exit(0) yapacak.
        # Bu noktada pencere göstermeden bekle — splash dışında hiçbir şey açılmayacak.
        splash.close()
        while True:
            app.processEvents()
            time.sleep(0.05)
    splash.set_progress(10, translate(ui_lang, "splash.starting"))
    app.processEvents()
    # ─────────────────────────────────────────────────────────────────────

    # IqtMusic'in her init aşamasında splash'ı güncelleyen callback.
    # app.processEvents() çağrısı sayesinde splash timer (30ms) çalışmaya
    # devam eder ve ekran donmaz.
    def _on_init_progress(value: int, message: str):
        splash.set_progress(value, message)
        app.processEvents()

    window = IqtMusic(progress_cb=_on_init_progress)

    # Init tamamlandı — kalan işler
    splash.set_progress(97, translate(ui_lang, "splash.preparing"))
    app.processEvents()

    _install_single_instance_bridge(window)
    app.setFont(QFont(FONT_MAIN, 10))

    # %100'e ulaş, kısa bekle, pencereyi aç
    QTimer.singleShot(120, lambda: splash.set_progress(100, translate(ui_lang, "splash.ready")))

    def _launch():
        splash.finish(window)
        window.show()

    QTimer.singleShot(520, _launch)

    # Discord "Beraber Dinle" butonu ile başlatıldıysa odaya otomatik katıl
    if join_code:
        QTimer.singleShot(2000, lambda: window.collab_join(join_code, from_discord=True))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
