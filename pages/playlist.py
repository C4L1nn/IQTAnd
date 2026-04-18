"""Playlist sayfası — drag & drop destekli."""
import logging
log = logging.getLogger("iqtMusic")

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout,
    QListWidget, QListWidgetItem, QAbstractItemView, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QCursor

from core.constants import (
    BG_BLACK, BG_CARD, BG_CARD_HOVER, BG_ELEVATED, BORDER_COLOR,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED
)
from core.theme import get_accent
from utils.helpers import create_icon, safe_save_json
from ui.widgets import ClickableFrame, TrackCoverWidget
from pages.common import _build_page_header


# ──────────────────────────────────────────────────────────────────────────────
# Satır widget fabrikası — drag sonrası yeniden oluşturmak için ayrı fonksiyon
# ──────────────────────────────────────────────────────────────────────────────

def _make_row(app, track: dict, playlist_name: str, fav_vids: set, acc: str) -> QWidget:
    """Bir playlist şarkısı için holder+row widget'ı oluşturur."""
    vid = track.get("videoId", "")
    t = app._tr

    row = QFrame()
    row.setObjectName("PlaylistTrackRow")
    row.setAttribute(Qt.WA_StyledBackground, True)
    row.setStyleSheet(f"""
        QFrame#PlaylistTrackRow {{
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {BG_CARD}, stop:1 {BG_ELEVATED});
            border-radius: 16px;
            border: 1px solid {BORDER_COLOR};
        }}
        QFrame#PlaylistTrackRow:hover {{
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {BG_CARD_HOVER}, stop:1 {BG_ELEVATED});
            border-color: {acc}55;
        }}
        QFrame#PlaylistTrackRow QLabel {{ border:none; background:transparent; }}
    """)

    rl = QHBoxLayout(row)
    rl.setContentsMargins(10, 10, 10, 10)
    rl.setSpacing(10)

    # Sürükleme tutamacı — fare üstünde sürükleme hint'i
    drag_lbl = QLabel("⠿")
    drag_lbl.setFixedWidth(14)
    drag_lbl.setAlignment(Qt.AlignCenter)
    drag_lbl.setStyleSheet(f"color:{TEXT_MUTED}; font-size:16px;")
    drag_lbl.setToolTip(t("common.drag_drop"))

    # Albüm kapağı
    img = TrackCoverWidget(52, 52, radius=8)
    thumb = app._thumb(track, big=True)
    if thumb:
        app._load_image(thumb, img, (52, 52))
    else:
        img.setPixmap(create_icon("music", TEXT_MUTED, 28).pixmap(28, 28))

    # Şarkı bilgisi
    info = QVBoxLayout()
    info.setSpacing(2)
    t_lbl = QLabel(track.get("title", t("common.unknown_title")))
    t_lbl.setStyleSheet(f"font-size:13px; font-weight:850; color:{TEXT_PRIMARY};")
    a_lbl = QLabel(app._artist_str(track))
    a_lbl.setStyleSheet(f"font-size:11px; color:{TEXT_MUTED};")
    info.addWidget(t_lbl)
    info.addWidget(a_lbl)

    meta_parts = []
    if vid in fav_vids:
        meta_parts.append(t("common.favorite"))
    if app.dl.is_downloaded(vid):
        meta_parts.append("Offline")
    if meta_parts:
        meta_lbl = QLabel("  •  ".join(meta_parts))
        meta_lbl.setStyleSheet(f"font-size:10px; color:{acc}; font-weight:700;")
        info.addWidget(meta_lbl)

    info.addStretch()

    # Aksiyon butonları
    act = QHBoxLayout()
    act.setSpacing(6)

    play_btn = QPushButton()
    play_btn.setFixedSize(32, 32)
    play_btn.setCursor(Qt.PointingHandCursor)
    play_btn.setFocusPolicy(Qt.NoFocus)
    play_btn.setIcon(create_icon("play", acc, 16))
    play_btn.setIconSize(QSize(16, 16))
    play_btn.setStyleSheet(
        f"QPushButton{{background:transparent;border:none;border-radius:16px;}}"
        f"QPushButton:hover{{background:{acc}22;}}"
    )
    play_btn.clicked.connect(lambda _=False, t=track: app.force_play(t))

    rm_btn = QPushButton(t("common.remove"))
    rm_btn.setCursor(Qt.PointingHandCursor)
    rm_btn.setFocusPolicy(Qt.NoFocus)
    rm_btn.setFixedHeight(30)
    rm_btn.setStyleSheet(f"""
        QPushButton {{
            background: rgba(255,255,255,0.04);
            color: {TEXT_PRIMARY};
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 10px;
            padding: 0 12px;
            font-size: 12px;
            font-weight: 800;
        }}
        QPushButton:hover {{
            background: rgba(255,107,107,0.10);
            border-color: #FF6B6B66;
            color: #FFB3B3;
        }}
    """)
    rm_btn.clicked.connect(lambda _=False, n=playlist_name, t=track: app._remove_from_pl(n, t))

    act.addWidget(play_btn)
    act.addWidget(rm_btn)

    rl.addWidget(drag_lbl, 0, Qt.AlignVCenter)
    rl.addWidget(img, 0, Qt.AlignVCenter)
    rl.addLayout(info, 1)
    rl.addLayout(act, 0)

    # Sağ tık context menu (sol tıkta drag çalışsın diye mousePressEvent YOK)
    row.setContextMenuPolicy(Qt.CustomContextMenu)
    row.customContextMenuRequested.connect(
        lambda _, t=track: app._ctx_menu(QCursor.pos(), t)
    )

    # holder — sadece padding için
    holder = QWidget()
    holder.setStyleSheet("background:transparent;")
    h_l = QVBoxLayout(holder)
    h_l.setContentsMargins(0, 3, 0, 3)
    h_l.setSpacing(0)
    h_l.addWidget(row)
    holder._track = track   # kolay erişim için
    return holder


# ──────────────────────────────────────────────────────────────────────────────
# DRAG-DROP LISTE
# ──────────────────────────────────────────────────────────────────────────────

class _DragPlaylistList(QListWidget):
    """Sürükle-bırak ile yeniden sıralama destekli playlist listesi."""

    def __init__(self, app, playlist_name: str):
        super().__init__()
        self._app           = app
        self._playlist_name = playlist_name
        acc = get_accent()

        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)

        self.setStyleSheet(f"""
            QListWidget {{
                background: transparent;
                border: none;
                outline: none;
                padding-right: 4px;
            }}
            QListWidget::item {{
                background: transparent;
                border: none;
                margin: 0;
                padding: 0;
            }}
            QListWidget::item:selected {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 10px;
                margin: 6px 0;
            }}
            QScrollBar::handle:vertical {{
                background: {BORDER_COLOR};
                border-radius: 5px;
                min-height: 40px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {acc}88;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent; border: none; height: 0;
            }}
        """)

    def dropEvent(self, event):
        """Drop sonrası: item'ı taşı, sırayı kaydet, widget'ları yenile."""
        # 1) Hangi index'ten alındığını kaydet
        src_row = self.currentRow()

        # 2) Qt'nin kendi InternalMove mekanizması item datasını taşısın
        super().dropEvent(event)

        # 3) Item data'sından yeni sırayı çıkar ve kaydet
        new_tracks = []
        for i in range(self.count()):
            item = self.item(i)
            if item:
                t = item.data(Qt.UserRole)
                if t:
                    new_tracks.append(t)

        self._app.playlists[self._playlist_name] = new_tracks
        try:
            safe_save_json(self._app.playlist_file, self._app.playlists)
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)

        # 4) Widget'lar kaybolabilir → kısa gecikmeyle yeniden kur
        QTimer.singleShot(0, self._reinstall_widgets)
        event.accept()

    def _reinstall_widgets(self):
        """Drag sonrası kaybolmuş item widget'larını yeniden oluşturur."""
        acc      = get_accent()
        fav_vids = {f.get("videoId", "") for f in self._app.favorites}

        for i in range(self.count()):
            item = self.item(i)
            if not item:
                continue
            track = item.data(Qt.UserRole)
            if not track:
                continue
            # Widget hala var ve geçerliyse dokunma
            existing = self.itemWidget(item)
            if existing is not None:
                try:
                    _ = existing.size()   # widget geçerli mi?
                    continue
                except Exception:
                    pass
            # Widget kaybolmuş veya geçersiz → yeniden oluştur
            holder = _make_row(self._app, track, self._playlist_name, fav_vids, acc)
            self.setItemWidget(item, holder)


def _populate_list(lst: _DragPlaylistList, app, playlist_name: str, tracks: list):
    """Listeye item'ları ekler."""
    acc      = get_accent()
    fav_vids = {f.get("videoId", "") for f in app.favorites}

    for track in tracks:
        item = QListWidgetItem()
        item.setData(Qt.UserRole, track)
        item.setSizeHint(QSize(0, 88))
        # ItemIsDropEnabled OLMADAN — üstüne bırakınca kaybolma bug'ını önler
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled)

        holder = _make_row(app, track, playlist_name, fav_vids, acc)
        lst.addItem(item)
        lst.setItemWidget(item, holder)


# ──────────────────────────────────────────────────────────────────────────────
# SAYFA YAPICI
# ──────────────────────────────────────────────────────────────────────────────

def build_playlist_page(app, name: str):
    app.current_page = f"playlist_{name}"
    t = app._tr

    pg = QWidget()
    pg.setStyleSheet(f"background:{BG_BLACK};")
    vl = QVBoxLayout(pg)
    vl.setContentsMargins(36, 36, 36, 0)

    tracks = app.playlists.get(name, [])

    bpa = QPushButton(f"▶  {t('common.play_all')}")
    bpa.setCursor(Qt.PointingHandCursor)
    bpa.setStyleSheet(
        f"background:{get_accent()}; color:black; padding:10px 22px; "
        f"border-radius:15px; font-weight:700; font-size:14px;")
    bpa.clicked.connect(lambda: app._play_all(list(tracks)))

    vl.addWidget(_build_page_header(
        app,
        name,
        t("playlist.subtitle", count=len(tracks)),
        eyebrow="PLAYLIST",
        back=True,
        right_widget=bpa,
    ))
    vl.addSpacing(16)

    if not tracks:
        empty = QLabel(t("playlist.empty"))
        empty.setAlignment(Qt.AlignCenter)
        empty.setStyleSheet(
            f"color:{TEXT_MUTED}; font-size:14px; background:transparent; margin-top:48px;")
        vl.addWidget(empty)
        vl.addStretch()
    else:
        app._prime_stream_urls(tracks, limit=3)
        drag_list = _DragPlaylistList(app, name)
        _populate_list(drag_list, app, name, tracks)
        vl.addWidget(drag_list)

    return pg


# Eski API — geriye dönük uyumluluk
def _populate_playlist_tracks(app, playlist_name, layout, tracks):
    pass
