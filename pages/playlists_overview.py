"""Tüm playlistlerin genel bakış sayfası."""

import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QFrame, QGridLayout, QFileDialog, QMenu
)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPixmap, QDrag
from PySide6.QtCore import QMimeData

from core.constants import (
    BG_BLACK, BG_CARD, BG_CARD_HOVER, BG_ELEVATED, BORDER_COLOR,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED
)
from core.theme import get_accent, get_accent_hover
from ui.widgets import ClickableFrame, TrackCoverWidget
from pages.common import _build_page_header


class _PlaylistOverviewCard(ClickableFrame):
    def __init__(self, accent: str, parent=None):
        super().__init__(parent)
        self._accent = accent

        self.setObjectName("PlaylistOverviewCard")
        self.setFixedSize(180, 220)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"""
            QFrame#PlaylistOverviewCard {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {BG_CARD}, stop:0.7 {BG_ELEVATED}, stop:1 {BG_CARD});
                border-radius: 18px;
                border: 1px solid {BORDER_COLOR};
            }}
            QFrame#PlaylistOverviewCard:hover {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {accent}14, stop:0.62 {BG_CARD_HOVER}, stop:1 {BG_ELEVATED});
                border: 1px solid {accent}66;
            }}
            QFrame#PlaylistOverviewCard QLabel {{
                border: none;
                background: transparent;
            }}
        """)


def _playlist_sort_options(app) -> list[tuple[str, str]]:
    return [
        ("added", app._tr("playlists.sort.added")),
        ("recent", app._tr("playlists.sort.recent")),
        ("name", app._tr("playlists.sort.name")),
        ("tracks_desc", app._tr("playlists.sort.tracks_desc")),
        ("tracks_asc", app._tr("playlists.sort.tracks_asc")),
    ]


def _playlist_sort_mode(app) -> str:
    mode = str(getattr(app, "_playlist_overview_sort_mode", "added") or "added").strip().lower()
    valid = {key for key, _ in _playlist_sort_options(app)}
    return mode if mode in valid else "added"


def _playlist_sort_label(app) -> str:
    mode = _playlist_sort_mode(app)
    for key, label in _playlist_sort_options(app):
        if key == mode:
            return label
    return app._tr("playlists.sort.added")


def _sorted_playlist_items(app) -> list[tuple[str, list]]:
    items = list((app.playlists or {}).items())
    mode = _playlist_sort_mode(app)
    if mode == "added":
        manual_order = list(getattr(app, "_playlist_manual_order", None) or [])
        if manual_order:
            item_dict = dict(items)
            seen: set = set()
            ordered = []
            for pl_name in manual_order:
                if pl_name in item_dict and pl_name not in seen:
                    ordered.append((pl_name, item_dict[pl_name]))
                    seen.add(pl_name)
            for pl_name, tracks in items:
                if pl_name not in seen:
                    ordered.append((pl_name, tracks))
            return ordered
        return items
    elif mode == "recent":
        items.reverse()
    elif mode == "name":
        items.sort(key=lambda row: str(row[0] or "").casefold())
    elif mode == "tracks_desc":
        items.sort(key=lambda row: (-len(row[1] or []), str(row[0] or "").casefold()))
    elif mode == "tracks_asc":
        items.sort(key=lambda row: (len(row[1] or []), str(row[0] or "").casefold()))
    return items


def _apply_playlist_sort(app, mode: str):
    clean_mode = str(mode or "added").strip().lower() or "added"
    if clean_mode == _playlist_sort_mode(app):
        return
    app._playlist_overview_sort_mode = clean_mode
    try:
        app._save_settings()
    except Exception:
        pass
    app.page_playlists()


def build_playlists_overview_page(app):
    """
    Tüm playlistleri albüm kapağı kartı olarak gösteren genel bakış sayfası.
    İlk şarkının albüm kapağı, liste adı ve şarkı sayısı gösterilir.
    """
    acc = get_accent()
    t = app._tr
    app.current_page = "playlists"

    pg = QWidget()
    pg.setStyleSheet(f"background:{BG_BLACK};")
    outer = QVBoxLayout(pg)
    outer.setContentsMargins(36, 36, 36, 0)
    outer.setSpacing(0)

    new_btn = QPushButton(t("playlists.new_button"))
    new_btn.setObjectName("PlaylistsNewButton")
    new_btn.setCursor(Qt.PointingHandCursor)
    new_btn.setStyleSheet(f"""
        QPushButton#PlaylistsNewButton {{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {acc}, stop:1 {get_accent_hover()});
            color:#08110B;
            padding:10px 20px;
            border-radius:14px;
            font-weight:800;
            font-size:13px;
            border:1px solid {acc}44;
        }}
        QPushButton#PlaylistsNewButton:hover {{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {get_accent_hover()}, stop:1 {acc});
            border:1px solid {acc}88;
        }}
        QPushButton#PlaylistsNewButton:pressed {{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {acc}, stop:1 {acc});
            border:1px solid {acc}AA;
        }}
    """)
    new_btn.clicked.connect(app._dlg_new_playlist)

    controls = QWidget()
    controls.setStyleSheet("background:transparent;")
    controls_l = QHBoxLayout(controls)
    controls_l.setContentsMargins(0, 0, 0, 0)
    controls_l.setSpacing(10)

    sort_btn = QPushButton(f"{t('playlists.sort.label')}: {_playlist_sort_label(app)}")
    sort_btn.setCursor(Qt.PointingHandCursor)
    sort_btn.setStyleSheet(f"""
        QPushButton {{
            background:rgba(255,255,255,0.04);
            color:{TEXT_PRIMARY};
            padding:10px 16px;
            border-radius:14px;
            font-weight:800;
            font-size:12px;
            border:1px solid {BORDER_COLOR};
        }}
        QPushButton:hover {{
            border-color:{acc}66;
            color:{acc};
            background:{BG_CARD_HOVER};
        }}
    """)
    sort_menu = QMenu(sort_btn)
    sort_menu.setStyleSheet(f"""
        QMenu {{
            background:#101827;
            border:1px solid {acc}33;
            border-radius:12px;
            padding:6px 0;
            color:{TEXT_PRIMARY};
        }}
        QMenu::item {{
            padding:9px 16px;
            margin:1px 4px;
            border-radius:8px;
            font-size:12px;
            font-weight:700;
        }}
        QMenu::item:selected {{
            background:{acc}22;
            color:{acc};
        }}
    """)
    current_sort = _playlist_sort_mode(app)
    for mode, label in _playlist_sort_options(app):
        action = sort_menu.addAction(label)
        action.setCheckable(True)
        action.setChecked(mode == current_sort)
        action.triggered.connect(lambda _checked=False, m=mode: _apply_playlist_sort(app, m))
    sort_btn.setMenu(sort_menu)
    controls_l.addWidget(sort_btn)
    controls_l.addWidget(new_btn)

    outer.addWidget(_build_page_header(
        app,
        t("playlists.title"),
        t("playlists.subtitle", count=len(app.playlists)),
        eyebrow=t("playlists.eyebrow"),
        right_widget=controls,
    ))
    outer.addSpacing(28)

    # Scroll
    sc = QScrollArea()
    sc.setWidgetResizable(True)
    sc.setStyleSheet("background:transparent; border:none;")
    sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    inner = QWidget()
    inner.setStyleSheet("background:transparent;")
    grid = QGridLayout(inner)
    grid.setContentsMargins(0, 0, 16, 20)
    grid.setSpacing(18)
    sc.setWidget(inner)
    outer.addWidget(sc)

    if not app.playlists:
        empty = QLabel(t("playlists.empty"))
        empty.setAlignment(Qt.AlignCenter)
        empty.setStyleSheet(
            f"font-size:15px; color:{TEXT_MUTED}; background:transparent;")
        grid.addWidget(empty, 0, 0)
        return pg

    col, row = 0, 0
    MAX_COLS = 4
    card_list: list[tuple[str, "_PlaylistOverviewCard"]] = []

    inner.setAcceptDrops(True)

    def _drag_enter(e):
        if e.mimeData().hasText():
            e.acceptProposedAction()

    def _drag_move(e):
        e.acceptProposedAction()

    def _drop(e):
        src_name = e.mimeData().text()
        drop_pos = e.position().toPoint()
        tgt_name = None
        child = inner.childAt(drop_pos)
        while child is not None and child is not inner:
            if getattr(child, "_pl_name", None) is not None:
                tgt_name = child._pl_name
                break
            child = child.parent()
        if tgt_name and tgt_name != src_name:
            cur_order = [n for n, _ in card_list]
            if src_name in cur_order and tgt_name in cur_order:
                si = cur_order.index(src_name)
                ti = cur_order.index(tgt_name)
                cur_order.insert(ti, cur_order.pop(si))
                app._playlist_manual_order = cur_order
                app._playlist_overview_sort_mode = "added"
                try:
                    app._save_settings()
                except Exception:
                    pass
                app.page_playlists()
        e.acceptProposedAction()

    inner.dragEnterEvent = _drag_enter
    inner.dragMoveEvent = _drag_move
    inner.dropEvent = _drop

    for name, tracks in _sorted_playlist_items(app):
        # Kart çerçevesi
        card = _PlaylistOverviewCard(acc)
        card._pl_name = name

        cl = QVBoxLayout(card)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)

        # Kapak fotoğrafı alanı
        cover_w = QFrame()
        cover_w.setObjectName("PlaylistOverviewCover")
        cover_w.setFixedHeight(140)
        cover_w.setStyleSheet(f"""
            QFrame#PlaylistOverviewCover {{
                background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #161f30, stop:1 #121a29);
                border-radius:16px 16px 0 0;
                border:none;
            }}
        """)
        cover_l = QVBoxLayout(cover_w)
        cover_l.setContentsMargins(0, 0, 0, 0)
        cover_l.setSpacing(0)

        cover_lbl = TrackCoverWidget(180, 140, radius=14)

        # Özel kapak varsa kullan, yoksa ilk şarkının resmi
        custom_cover = app._playlist_covers.get(name, "") if hasattr(app, "_playlist_covers") else ""
        has_image_source = False
        if custom_cover and os.path.isfile(custom_cover):
            pix = QPixmap(custom_cover)
            cover_lbl.setPixmap(pix)
            has_image_source = True
        elif tracks:
            thumb = app._thumb(tracks[0])
            if thumb:
                app._load_image(thumb, cover_lbl, (180, 140))
                has_image_source = True

        # cover_lbl'yi her zaman layout'a ekle (async resim gelince dolar)
        cover_l.addWidget(cover_lbl)

        cover_overlay = QFrame(cover_w)
        cover_overlay.setGeometry(0, 0, 180, 140)
        cover_overlay.setStyleSheet(f"""
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 rgba(0,0,0,0.04), stop:0.45 rgba(0,0,0,0.00),
                stop:1 rgba(10,18,28,0.62));
            border-radius:16px 16px 0 0;
            border:none;
        """)
        cover_overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        badge = QLabel(t("playlists.cover_badge", count=len(tracks)), cover_w)
        badge.setGeometry(12, 102, 90, 26)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            f"background:rgba(7,12,19,0.78); color:{TEXT_PRIMARY}; "
            f"border:1px solid {acc}55; border-radius:13px; font-size:11px; font-weight:700;")
        badge.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        # Resim kaynağı yoksa müzik notu ikonu göster
        if not has_image_source:
            note_lbl = QLabel("♫")
            note_lbl.setAlignment(Qt.AlignCenter)
            note_lbl.setStyleSheet(
                f"font-size:52px; color:{acc}55; background:transparent;")
            note_lbl.setFixedSize(180, 140)
            cover_lbl.hide()
            cover_l.addWidget(note_lbl, alignment=Qt.AlignCenter)
        cover_overlay.raise_()
        badge.raise_()
        cl.addWidget(cover_w)

        # Alt bilgi
        info_w = QWidget()
        info_w.setStyleSheet("background:transparent;")
        il = QVBoxLayout(info_w)
        il.setContentsMargins(12, 10, 12, 12)
        il.setSpacing(4)

        glow_bar = QFrame()
        glow_bar.setFixedHeight(3)
        glow_bar.setStyleSheet(
            f"background:qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {acc}, stop:1 {get_accent_hover()}); "
            "border-radius:2px; border:none;")

        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(
            f"font-size:13px; font-weight:800; color:{TEXT_PRIMARY}; background:transparent;")
        name_lbl.setWordWrap(False)

        cnt_lbl = QLabel(t("playlists.track_count", count=len(tracks)))
        cnt_lbl.setStyleSheet(
            f"font-size:11px; color:{TEXT_MUTED}; background:transparent;")

        il.addWidget(glow_bar)
        il.addWidget(name_lbl)
        il.addWidget(cnt_lbl)
        cl.addWidget(info_w)

        # Tıklama / sürükleme ayrımı
        def _card_press(e, c=card):
            if e.button() == Qt.LeftButton:
                c._drag_start_pos = e.position().toPoint()
                c._dragging = False

        def _card_move(e, c=card):
            start = getattr(c, "_drag_start_pos", None)
            if start is not None and not getattr(c, "_dragging", False):
                if (e.position().toPoint() - start).manhattanLength() > 8:
                    c._dragging = True
                    drag = QDrag(c)
                    mime = QMimeData()
                    mime.setText(c._pl_name)
                    pix = c.grab()
                    scaled = pix.scaled(
                        int(pix.width() * 0.75), int(pix.height() * 0.75),
                        Qt.KeepAspectRatio, Qt.SmoothTransformation,
                    )
                    drag.setPixmap(scaled)
                    drag.setHotSpot(QPoint(scaled.width() // 2, 30))
                    drag.setMimeData(mime)
                    c._drag_start_pos = None
                    drag.exec(Qt.MoveAction)
                    c._dragging = False

        def _card_release(e, c=card, n=name):
            if not getattr(c, "_dragging", False) and e.button() == Qt.LeftButton:
                app.page_playlist(n)
            c._drag_start_pos = None
            c._dragging = False

        card._drag_start_pos = None
        card._dragging = False
        card.mousePressEvent = _card_press
        card.mouseMoveEvent = _card_move
        card.mouseReleaseEvent = _card_release

        # Sağ tık → kapat / kapak değiştir
        card.setContextMenuPolicy(Qt.CustomContextMenu)
        def _card_ctx(pos, n=name, crd=card):
            m = QMenu(crd)
            m.setStyleSheet(f"""
                QMenu {{ background:#1A1A2E; border:1px solid {acc}33;
                    border-radius:12px; padding:6px 0; color:white; }}
                QMenu::item {{ padding:9px 16px; font-size:13px; font-weight:600;
                    border-radius:8px; margin:1px 4px; }}
                QMenu::item:selected {{ background:{acc}28; color:{acc}; }}
            """)
            m.addAction(t("playlists.menu.play_all")).triggered.connect(
                lambda: app._play_all(app.playlists.get(n, [])))
            m.addAction(t("playlists.menu.change_cover")).triggered.connect(
                lambda: _change_cover(n))
            m.addSeparator()
            m.addAction(t("playlists.menu.rename")).triggered.connect(
                lambda: app._pl_rename(n))
            m.addAction(t("playlists.menu.delete")).triggered.connect(
                lambda: app._pl_delete(n))
            m.exec(crd.mapToGlobal(pos))

        card.customContextMenuRequested.connect(_card_ctx)
        card_list.append((name, card))
        grid.addWidget(card, row, col)
        col += 1
        if col >= MAX_COLS:
            col = 0
            row += 1

    # Sütunları eşit genişlikte yap
    for c in range(MAX_COLS):
        grid.setColumnStretch(c, 1)
    grid.setRowStretch(row + 1, 1)

    def _change_cover(pl_name):
        path, _ = QFileDialog.getOpenFileName(
            pg,
            t("playlists.cover_dialog.title"),
            "",
            t("playlists.cover_dialog.filter"),
        )
        if path:
            if not hasattr(app, "_playlist_covers"):
                app._playlist_covers = {}
            app._playlist_covers[pl_name] = path
            app._save_settings()
            app.page_playlists()

    return pg
