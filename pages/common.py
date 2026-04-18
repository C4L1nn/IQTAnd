import logging
log = logging.getLogger("iqtMusic")
"""Sayfalar arasında paylaşılan yardımcı fonksiyonlar ve widget'lar."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from core.constants import (
    BG_BLACK, BG_CARD, BG_CARD_HOVER, BG_ELEVATED, BORDER_COLOR,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED
)
from core.theme import get_accent, get_accent_hover
from utils.helpers import create_icon


def _rgba(color: str, alpha: int) -> str:
    qcolor = QColor(str(color or "#6EA8FF"))
    if not qcolor.isValid():
        return str(color)
    alpha = max(0, min(255, int(alpha)))
    return f"rgba({qcolor.red()}, {qcolor.green()}, {qcolor.blue()}, {alpha})"


def _build_page_header(app, title: str, subtitle: str = "", eyebrow: str = "GEZİN", back: bool = False, right_widget=None):
    acc = get_accent()
    shell = QFrame()
    shell.setObjectName("PageHeaderShell")
    shell.setAttribute(Qt.WA_StyledBackground, True)
    shell.setStyleSheet(f"""
        QFrame#PageHeaderShell {{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 rgba(255,255,255,0.025),
                stop:0.34 {_rgba(acc, 18)},
                stop:0.72 {BG_CARD},
                stop:1 {BG_ELEVATED});
            border-radius:24px;
            border:1px solid {_rgba(acc, 52)};
        }}
        QFrame#PageHeaderShell QLabel {{
            background:transparent;
            border:none;
        }}
    """)
    hl = QHBoxLayout(shell)
    hl.setContentsMargins(20, 18, 20, 18)
    hl.setSpacing(14)

    if back:
        hl.addWidget(_back_btn(app), 0, Qt.AlignTop)

    accent_line = QFrame()
    accent_line.setFixedSize(4, 46 if subtitle else 34)
    accent_line.setStyleSheet(
        f"background:qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {acc}, stop:1 {get_accent_hover()}); "
        "border:none; border-radius:2px;"
    )
    hl.addWidget(accent_line, 0, Qt.AlignVCenter)

    text_v = QVBoxLayout()
    text_v.setContentsMargins(0, 0, 0, 0)
    text_v.setSpacing(4)

    title_lbl = QLabel(title)
    title_lbl.setStyleSheet(
        f"font-size:30px; font-weight:900; color:{TEXT_PRIMARY};")
    if str(eyebrow or "").strip():
        eyebrow_lbl = QLabel(str(eyebrow).upper())
        eyebrow_lbl.setStyleSheet(
            f"font-size:10px; font-weight:900; letter-spacing:2px; color:{acc};")
        text_v.addWidget(eyebrow_lbl)
    text_v.addWidget(title_lbl)
    if subtitle:
        sub_lbl = QLabel(subtitle)
        sub_lbl.setWordWrap(True)
        sub_lbl.setStyleSheet(
            f"font-size:13px; color:{TEXT_SECONDARY};")
        text_v.addWidget(sub_lbl)

    hl.addLayout(text_v, 1)

    if right_widget is not None:
        hl.addWidget(right_widget, 0, Qt.AlignRight | Qt.AlignVCenter)

    return shell


def _back_btn(app) -> QPushButton:
    bb = QPushButton()
    bb.setIcon(create_icon("arrow_back", TEXT_SECONDARY, 22))
    bb.setFixedSize(34, 34)
    bb.setCursor(Qt.PointingHandCursor)
    bb.setStyleSheet(
        f"QPushButton{{border:1px solid {BORDER_COLOR}; background:{BG_CARD}; border-radius:20px;}}"
        f"QPushButton:hover{{background:{BG_CARD_HOVER}; border-color:{get_accent()};}}")
    bb.clicked.connect(app._go_back)
    return bb


def _scrollable():
    sc = QScrollArea()
    sc.setWidgetResizable(True)
    sc.setStyleSheet("background:transparent; border:none;")
    ct = QWidget()
    ct.setObjectName("TC")
    cl = QVBoxLayout(ct)
    cl.setContentsMargins(0, 0, 0, 36)
    cl.setSpacing(8)
    sc.setWidget(ct)
    return sc, ct, cl
