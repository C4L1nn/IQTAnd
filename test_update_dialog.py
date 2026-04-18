"""Update dialog görsel test — gerçek indirme/kurulum yapmaz."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

ACCENT = "#1DB954"

FAKE_INFO = {
    "version": "2.5.0",
    "asset_name": "iqtMusic_patch_2.5.0.zip",
    "download_url": "https://example.com/fake_update.zip",
    "size": 18_350_000,
    "notes": "",
    "mode": "patch",
    "sha256": "a" * 64,
}

def launch_dialog(lang: str):
    from utils.updater import UpdateDialog

    class _SafeDialog(UpdateDialog):
        """Butonları devre dışı bırakır — gerçek işlem yapmaz."""

        def _start_download(self):
            self._btn_update.setEnabled(False)
            self._btn_update.setText(self._s["downloading"])
            self._btn_skip.setEnabled(False)
            self._progress_area.setVisible(True)
            self._lbl_status.setText(self._s["connecting"])
            self.adjustSize()
            # Sahte ilerleme simüle et
            from PySide6.QtCore import QTimer
            self._fake_pct = 0
            self._fake_timer = QTimer(self)
            self._fake_timer.setInterval(60)
            self._fake_timer.timeout.connect(self._fake_tick)
            self._fake_timer.start()

        def _fake_tick(self):
            self._fake_pct += 2
            if self._fake_pct > 100:
                self._fake_timer.stop()
                self._bar.setValue(100)
                self._lbl_pct.setText("100%")
                self._lbl_status.setText(self._s["verified"])
                self._lbl_done.setText(self._s["applying"])
                self._lbl_done.setVisible(True)
                self.adjustSize()
                return
            self._bar.setValue(self._fake_pct)
            self._lbl_pct.setText(f"{self._fake_pct}%")
            total = FAKE_INFO["size"]
            done = int(total * self._fake_pct / 100)
            self._lbl_status.setText(
                f"{self._s['downloading']}  {done/1_048_576:.1f} / {total/1_048_576:.1f} MB"
            )

        def _run_patch(self, zip_path):
            pass

        def _run_installer(self, exe_path):
            pass

    dlg = _SafeDialog(FAKE_INFO, accent=ACCENT, lang=lang)
    dlg.exec()


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet("""
        * { font-family: 'Segoe UI Variable', 'Segoe UI'; }
        QWidget { background: #1a1a1a; color: #e0e0e0; }
        QPushButton {
            background: #2a2a2a; border: 1px solid #444; border-radius: 8px;
            padding: 10px 22px; color: #fff; font-size: 13px; font-weight: 600;
        }
        QPushButton:hover { background: #333; border-color: """ + ACCENT + """; }
    """)

    win = QWidget()
    win.setWindowTitle("Update Dialog Test")
    win.setFixedSize(320, 160)
    layout = QVBoxLayout(win)
    layout.setContentsMargins(30, 28, 30, 28)
    layout.setSpacing(14)

    lbl = QLabel("Hangi dilde açılsın?")
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet("font-size:14px; font-weight:600; color:#e0e0e0;")
    layout.addWidget(lbl)

    row = QHBoxLayout()
    row.setSpacing(12)

    btn_tr = QPushButton("🇹🇷  Türkçe")
    btn_en = QPushButton("🇬🇧  English")

    for btn in (btn_tr, btn_en):
        btn.setMinimumHeight(44)
        row.addWidget(btn)

    btn_tr.clicked.connect(lambda: launch_dialog("tr"))
    btn_en.clicked.connect(lambda: launch_dialog("en"))

    layout.addLayout(row)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
