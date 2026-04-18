"""Equalizer diyaloğu."""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QFrame, QWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from core.constants import (
    BG_DARK, BG_CARD, BG_ELEVATED, BORDER_COLOR,
    TEXT_SECONDARY, TEXT_MUTED, EQ_PRESETS
)
from core.theme import get_accent
from ui.titlebar import TitleBar


def open_eq_dialog(app):
    acc = get_accent()
    t = app._tr
    # Frameless pencere — lyrics diyaloğuyla aynı yapı
    app._eq_win = QDialog(app)
    app._eq_win.setWindowFlags(app._eq_win.windowFlags() | Qt.FramelessWindowHint)
    app._eq_win.setFixedSize(720, 480)
    app._eq_win.setStyleSheet(f"background:{BG_DARK}; color:white;")

    host_l = QVBoxLayout(app._eq_win)
    host_l.setContentsMargins(0, 0, 0, 0)
    host_l.setSpacing(0)

    # Başlık çubuğu — emoji yok, arka plan içerikle aynı
    tb = TitleBar(app._eq_win, title=t("equalizer.title"))
    tb.setStyleSheet(f"background:{BG_DARK}; color:white;")
    host_l.addWidget(tb)

    # İnce accent ayırıcı çizgi
    sep_top = QFrame()
    sep_top.setFixedHeight(1)
    sep_top.setStyleSheet(f"background:{acc}44;")
    host_l.addWidget(sep_top)

    # İçerik alanı
    content = QWidget()
    content.setStyleSheet(f"background:{BG_DARK};")
    host_l.addWidget(content, 1)

    vl = QVBoxLayout(content)
    vl.setContentsMargins(24, 16, 24, 20)
    vl.setSpacing(0)

    pf = QFrame()
    pf.setStyleSheet("background:transparent;")
    pl = QHBoxLayout(pf)
    pl.setSpacing(8)
    preset_labels = {
        "Düz": t("equalizer.preset.flat"),
        "Bass": t("equalizer.preset.bass"),
        "Rock": t("equalizer.preset.rock"),
        "Pop": t("equalizer.preset.pop"),
        "Jazz": t("equalizer.preset.jazz"),
        "Klasik": t("equalizer.preset.classical"),
    }
    for pname in EQ_PRESETS:
        b = QPushButton(preset_labels.get(pname, pname))
        b.setFixedHeight(36)
        b.setStyleSheet(f"""
            QPushButton {{
                background:{BG_CARD}; color:{TEXT_SECONDARY};
                border-radius:14px; padding:0 16px; font-size:13px;
                border:1px solid {BORDER_COLOR};
            }}
            QPushButton:hover {{
                background:{acc}33; color:{acc}; border-color:{acc}55;
            }}
        """)
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(lambda _, n=pname: app._apply_eq_preset(n))
        pl.addWidget(b)
    pl.addStretch()
    vl.addWidget(pf)
    vl.addSpacing(16)

    sf = QFrame()
    sf.setStyleSheet("background:transparent;")
    sl = QHBoxLayout(sf)
    sl.setSpacing(12)
    freqs = ["60", "170", "310", "600", "1K", "3K", "6K", "12K", "14K", "16K"]
    app._eq_sliders = []
    for i, freq in enumerate(freqs):
        vb = QVBoxLayout()
        vb.setAlignment(Qt.AlignCenter)
        val_lbl = QLabel(f"{app._eq_vals[i] if i < len(app._eq_vals) else 0:+d}")
        val_lbl.setAlignment(Qt.AlignCenter)
        val_lbl.setStyleSheet(
            f"font-size:11px; color:{acc}; font-weight:700; background:transparent;")
        s = QSlider(Qt.Vertical)
        s.setRange(-20, 20)
        s.setValue(app._eq_vals[i] if i < len(app._eq_vals) else 0)
        s.setFixedHeight(200)
        s.setStyleSheet(f"""
            QSlider::groove:vertical {{
                border:none; width:6px;
                background:{BG_ELEVATED}; border-radius:3px;
            }}
            QSlider::handle:vertical {{
                background:{acc}; border:none;
                width:16px; height:16px;
                margin:-5px -5px; border-radius:8px;
            }}
            QSlider::add-page:vertical {{
                background:{acc}66; border-radius:3px;
            }}
            QSlider::sub-page:vertical {{
                background:{BG_ELEVATED}; border-radius:3px;
            }}
        """)
        s.valueChanged.connect(lambda v, idx=i: app._eq_change(idx, v))
        s.valueChanged.connect(lambda v, lx=val_lbl: lx.setText(f"{v:+d}"))
        app._eq_sliders.append(s)
        freq_lbl = QLabel(freq)
        freq_lbl.setAlignment(Qt.AlignCenter)
        freq_lbl.setStyleSheet(
            f"font-size:11px; color:{TEXT_MUTED}; background:transparent;")
        vb.addWidget(val_lbl)
        vb.addWidget(s, alignment=Qt.AlignHCenter)
        vb.addWidget(freq_lbl)
        sl.addLayout(vb)
    vl.addWidget(sf)
    app._eq_win.show()
