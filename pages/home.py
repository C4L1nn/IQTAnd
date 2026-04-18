"""Ana Sayfa yardımcı modülü.

Bu modül home_clean.py tarafından ``import pages.home as _H`` şeklinde
kullanılır. Doğrudan çağrılmaz; yalnızca aşağıdaki utility fonksiyonları
ve re-export'lar sağlar:

  _clean_section_title   – Bölüm başlığını temizler
  _make_section_header   – Bölüm başlığı widget'ı (monkey-patch ile override edilir)
  _make_home_compact_card – Kompakt şarkı kartı
  _mk_hscroll            – Yatay kaydırma widget'ı
"""
import logging

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QFrame, QLabel, QScrollArea,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor

from ui.widgets import AnimatedCard, TrackCoverWidget

from core.constants import (
    BG_BLACK, BG_CARD, BG_CARD_HOVER, BG_ELEVATED, BORDER_COLOR,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, DYNAMIC_CONTENT,
    CATEGORY_BUTTONS, TRENDING_SECTIONS,
)
from core.theme import get_accent, get_accent_hover
from utils.helpers import create_icon

log = logging.getLogger("iqtMusic")


def _clean_section_title(text: str) -> str:
    text = " ".join(str(text or "").split())
    if not text:
        return "Keşfet"

    start = 0
    while start < len(text):
        ch = text[start]
        if ch.isalnum() or ch in "ÇĞİÖŞÜçğıöşü":
            break
        start += 1

    cleaned = text[start:].strip()
    return cleaned or "Keşfet"


def _make_section_header(text: str) -> QWidget:
    title = _clean_section_title(text)
    acc = get_accent()

    shell = QWidget()
    shell.setStyleSheet("background:transparent;")
    row = QHBoxLayout(shell)
    row.setContentsMargins(0, 14, 0, 8)
    row.setSpacing(10)

    accent_line = QFrame()
    accent_line.setFixedSize(3, 18)
    accent_line.setStyleSheet(
        f"background:qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {acc}, stop:1 {get_accent_hover()}); "
        "border:none; border-radius:2px;")

    lbl = QLabel(title)
    lbl.setStyleSheet(
        f"font-size:18px; font-weight:860; color:{TEXT_PRIMARY}; "
        f"letter-spacing:0.2px; background:transparent;")

    row.addWidget(accent_line, 0, Qt.AlignVCenter)
    row.addWidget(lbl, 0, Qt.AlignVCenter)
    row.addStretch()
    return shell


def _make_home_compact_card(app, track: dict, size: str = "normal") -> QFrame:
    acc = get_accent()
    card = AnimatedCard()
    card.setObjectName("CompactCard")
    w = 280 if size == "wide" else 190
    h = 100
    card.setFixedSize(w, h)
    card.setStyleSheet(f"""
        QFrame#CompactCard {{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 rgba(255,255,255,0.02), stop:0.7 {BG_CARD}, stop:1 {BG_ELEVATED});
            border-radius:14px;
            border: none;
        }}
        QFrame#CompactCard:hover {{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 {acc}10, stop:0.6 {BG_CARD_HOVER}, stop:1 {BG_ELEVATED});
        }}
    """)
    lay = QHBoxLayout(card)
    lay.setContentsMargins(10, 8, 10, 8)
    lay.setSpacing(10)

    s = 76 if size == "wide" else 64
    img = TrackCoverWidget(s, s, radius=10)
    thumb = app._thumb(track, big=True)
    if thumb:
        app._load_image(thumb, img, (s, s))
    else:
        try:
            fall_pix = create_icon("music", TEXT_MUTED, s // 2 if s > 0 else 30)
            img.setPixmap(fall_pix.pixmap(s // 2 if s > 0 else 30, s // 2 if s > 0 else 30))
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)

    txt = QVBoxLayout()
    txt.setSpacing(3)
    txt.setContentsMargins(0, 0, 0, 0)
    title_raw = (track.get("title") or "Bilinmiyor")
    ttl = QLabel(title_raw)
    ttl.setWordWrap(False)
    ttl.setStyleSheet(
        f"font-size:{16 if size == 'wide' else 13}px; font-weight:800; "
        f"color:{TEXT_PRIMARY}; background:transparent;")
    _art_str = app._artist_str(track) if hasattr(app, "_artist_str") else (track.get("artist") or "")
    art = QLabel(_art_str or "Bilinmeyen")
    art.setWordWrap(False)
    art.setStyleSheet(f"font-size:11px; color:{TEXT_SECONDARY}; background:transparent;")
    txt.addStretch()
    txt.addWidget(ttl)
    txt.addWidget(art)
    txt.addStretch()
    if size == "wide":
        meta = QLabel("Kaldığın yerden devam et")
        meta.setStyleSheet(f"font-size:11px; color:{TEXT_MUTED}; background:transparent;")
        txt.addWidget(meta)

    lay.addWidget(img, 0, Qt.AlignVCenter)
    lay.addLayout(txt, 1)

    card.clicked.connect(lambda t=track: app.force_play(t))
    card.setContextMenuPolicy(Qt.CustomContextMenu)
    card.customContextMenuRequested.connect(
        lambda _pos, t=track: app._ctx_menu(QCursor.pos(), t))
    return card


def _mk_hscroll():
    hs = QScrollArea()
    hs.setFixedHeight(300)
    hs.setWidgetResizable(False)
    hs.setStyleSheet("background:transparent; border:none;")
    hs.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    hs.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    hf = QWidget()
    hf.setObjectName("TC")
    hl = QHBoxLayout(hf)
    hl.setAlignment(Qt.AlignLeft)
    hl.setContentsMargins(0, 0, 0, 0)
    hl.setSpacing(16)
    hs.setWidget(hf)
    return hs
