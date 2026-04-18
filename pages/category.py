"""Kategori sayfası — Playlist görünümü."""
import logging
import random as _random

log = logging.getLogger("iqtMusic")

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QLabel,
    QFrame, QPushButton, QGridLayout
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor

from core.constants import (
    BG_BLACK, BG_CARD, BG_ELEVATED, BORDER_COLOR,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED
)
from core.theme import get_accent, get_accent_hover
from utils.helpers import create_icon
from ui.widgets import TrackCoverWidget


def build_category_page(app, title, query, ftype="songs"):
    app.current_page = f"cat_{title}"
    app.prev_page = {"type": "home"}
    acc = get_accent()
    acc_hover = get_accent_hover()
    t = app._tr

    pg = QWidget()
    pg.setStyleSheet(f"background:{BG_BLACK};")
    vl = QVBoxLayout(pg)
    vl.setContentsMargins(0, 0, 0, 0)
    vl.setSpacing(0)

    # ─── HERO ─────────────────────────────────────────────────────────────────
    hero = QFrame()
    hero.setObjectName("CatHeroFrame")
    hero.setFixedHeight(230)
    hero.setStyleSheet(f"""
        QFrame#CatHeroFrame {{
            background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 #080f1c, stop:1 #050c17);
            border-bottom: 1px solid {acc}30;
        }}
    """)
    hero_l = QHBoxLayout(hero)
    hero_l.setContentsMargins(36, 28, 36, 28)
    hero_l.setSpacing(30)

    # ── Geri butonu (sol üst) ─────────────────────────────────────────────────
    back_col = QVBoxLayout()
    back_col.setContentsMargins(0, 0, 0, 0)
    back_col.setSpacing(0)
    back_btn = QPushButton()
    back_btn.setFixedSize(38, 38)
    back_btn.setIcon(create_icon("arrow_back", TEXT_MUTED, 16))
    back_btn.setIconSize(QSize(16, 16))
    back_btn.setCursor(Qt.PointingHandCursor)
    back_btn.setFocusPolicy(Qt.NoFocus)
    back_btn.setToolTip(t("common.back"))
    back_btn.setStyleSheet(f"""
        QPushButton {{
            background: rgba(255,255,255,0.06);
            border: 1px solid {BORDER_COLOR};
            border-radius: 19px;
        }}
        QPushButton:hover {{
            background: rgba(255,255,255,0.13);
            border-color: {acc}55;
        }}
    """)
    back_btn.clicked.connect(app._go_back)
    back_col.addWidget(back_btn, 0, Qt.AlignTop)
    back_col.addStretch()
    hero_l.addLayout(back_col)

    # ── Kapak kolajı (2×2) ───────────────────────────────────────────────────
    cover_outer = QFrame()
    cover_outer.setObjectName("CatCoverOuter")
    cover_outer.setFixedSize(168, 168)
    cover_outer.setStyleSheet(f"""
        QFrame#CatCoverOuter {{
            background: {BG_ELEVATED};
            border-radius: 22px;
            border: 1px solid {acc}28;
        }}
    """)
    try:
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 160))
        cover_outer.setGraphicsEffect(shadow)
    except Exception:
        pass

    cg = QGridLayout(cover_outer)
    cg.setContentsMargins(6, 6, 6, 6)
    cg.setSpacing(4)

    cover_slots = []
    for r in range(2):
        for c in range(2):
            slot = TrackCoverWidget(72, 72, radius=10)
            cg.addWidget(slot, r, c)
            cover_slots.append(slot)

    hero_l.addWidget(cover_outer, 0, Qt.AlignVCenter)

    # ── Bilgi paneli ──────────────────────────────────────────────────────────
    info_v = QVBoxLayout()
    info_v.setSpacing(0)
    info_v.setContentsMargins(0, 4, 0, 0)

    eyebrow_lbl = QLabel(t("category.eyebrow"))
    eyebrow_lbl.setStyleSheet(
        f"font-size:11px; font-weight:900; letter-spacing:2.5px;"
        f" color:{acc}; background:transparent;"
    )
    info_v.addWidget(eyebrow_lbl)
    info_v.addSpacing(8)

    title_lbl = QLabel(title)
    title_lbl.setWordWrap(True)
    title_lbl.setMaximumWidth(700)
    title_lbl.setStyleSheet(
        f"font-size:26px; font-weight:900; color:{TEXT_PRIMARY}; background:transparent;"
        f" font-family:'Segoe UI Variable Display','Segoe UI Black','Segoe UI';"
    )
    info_v.addWidget(title_lbl)
    info_v.addSpacing(10)

    count_lbl = QLabel(t("common.loading"))
    count_lbl.setStyleSheet(
        f"font-size:13px; color:{TEXT_MUTED}; background:transparent;"
    )
    info_v.addWidget(count_lbl)
    info_v.addSpacing(18)

    # Buton satırı
    btn_row = QHBoxLayout()
    btn_row.setSpacing(10)
    btn_row.setContentsMargins(0, 0, 0, 0)

    play_btn = QPushButton(f"  {t('common.play_all')}")
    play_btn.setFixedHeight(42)
    play_btn.setMinimumWidth(148)
    play_btn.setIcon(create_icon("play", "#000000", 14))
    play_btn.setIconSize(QSize(14, 14))
    play_btn.setCursor(Qt.PointingHandCursor)
    play_btn.setFocusPolicy(Qt.NoFocus)
    play_btn.setEnabled(False)
    play_btn.setStyleSheet(f"""
        QPushButton {{
            background: {acc};
            color: #000;
            font-weight: 800;
            font-size: 13px;
            border: none;
            border-radius: 21px;
            padding: 0 22px;
        }}
        QPushButton:hover {{
            background: {acc_hover};
        }}
        QPushButton:disabled {{
            background: rgba(255,255,255,0.1);
            color: {TEXT_MUTED};
        }}
    """)

    shuffle_btn = QPushButton(f"  {t('common.shuffle')}")
    shuffle_btn.setFixedHeight(42)
    shuffle_btn.setMinimumWidth(126)
    shuffle_btn.setIcon(create_icon("shuffle", TEXT_SECONDARY, 14))
    shuffle_btn.setIconSize(QSize(14, 14))
    shuffle_btn.setCursor(Qt.PointingHandCursor)
    shuffle_btn.setFocusPolicy(Qt.NoFocus)
    shuffle_btn.setEnabled(False)
    shuffle_btn.setStyleSheet(f"""
        QPushButton {{
            background: rgba(255,255,255,0.07);
            color: {TEXT_SECONDARY};
            font-weight: 700;
            font-size: 13px;
            border: 1px solid {BORDER_COLOR};
            border-radius: 21px;
            padding: 0 22px;
        }}
        QPushButton:hover {{
            background: rgba(255,255,255,0.13);
            border-color: {acc}55;
            color: {TEXT_PRIMARY};
        }}
        QPushButton:disabled {{
            background: transparent;
            color: {TEXT_MUTED};
            border-color: {BORDER_COLOR};
        }}
    """)

    btn_row.addWidget(play_btn)
    btn_row.addWidget(shuffle_btn)
    btn_row.addStretch()

    info_v.addLayout(btn_row)
    info_v.addStretch()

    hero_l.addLayout(info_v, 1)
    vl.addWidget(hero)

    # ─── AYIRICI + LİSTE BAŞLIĞI ──────────────────────────────────────────────
    list_header = QFrame()
    list_header.setFixedHeight(46)
    list_header.setStyleSheet(f"background:{BG_BLACK}; border:none;")
    lh_l = QHBoxLayout(list_header)
    lh_l.setContentsMargins(44, 0, 48, 0)
    lh_l.setSpacing(0)

    def _col_lbl(text, align=Qt.AlignLeft, width=None):
        l = QLabel(text)
        l.setStyleSheet(
            f"font-size:11px; font-weight:700; letter-spacing:1px;"
            f" color:{TEXT_MUTED}; background:transparent;"
        )
        l.setAlignment(align)
        if width:
            l.setFixedWidth(width)
        return l

    lh_l.addWidget(_col_lbl("#", Qt.AlignCenter, 34))
    lh_l.addSpacing(12)
    lh_l.addWidget(_col_lbl("  ", Qt.AlignLeft, 46))   # cover boşluğu
    lh_l.addSpacing(12)
    lh_l.addWidget(_col_lbl(t("category.column.title")), 1)
    lh_l.addWidget(_col_lbl("", Qt.AlignRight, 76))    # play + fav buton alanı

    sep = QFrame()
    sep.setFrameShape(QFrame.HLine)
    sep.setFixedHeight(1)
    sep.setStyleSheet(f"background:{BORDER_COLOR}; border:none;")

    vl.addWidget(list_header)
    vl.addWidget(sep)

    # ─── ŞARKI LİSTESİ ────────────────────────────────────────────────────────
    sc = QScrollArea()
    sc.setWidgetResizable(True)
    sc.setStyleSheet(f"""
        QScrollArea {{ background: transparent; border: none; }}
        QScrollBar:vertical {{
            background: transparent; width: 10px; margin: 6px 0;
        }}
        QScrollBar::handle:vertical {{
            background: {BORDER_COLOR}; border-radius: 5px; min-height: 48px;
        }}
        QScrollBar::handle:vertical:hover {{ background: {acc}88; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: transparent; border: none; height: 0;
        }}
    """)

    ct = QWidget()
    ct.setObjectName("CatListContainer")
    ct.setStyleSheet("background: transparent;")
    list_layout = QVBoxLayout(ct)
    list_layout.setContentsMargins(36, 12, 36, 36)
    list_layout.setSpacing(4)
    list_layout.setAlignment(Qt.AlignTop)
    sc.setWidget(ct)

    ld = QLabel(t("common.loading"))
    ld.setStyleSheet(f"color:{TEXT_MUTED}; font-size:15px; background:transparent;")
    ld.setAlignment(Qt.AlignCenter)
    list_layout.addWidget(ld)

    # Referansları container'a bağla (fill_h_grid sonraki adımda günceller)
    ct._hero_count_lbl = count_lbl
    ct._hero_cover_slots = cover_slots
    ct._play_btn = play_btn
    ct._shuffle_btn = shuffle_btn

    vl.addWidget(sc, 1)

    app._net_pool.submit(lambda: app._fetch_cat(query, ftype, ct, ld))
    return pg
