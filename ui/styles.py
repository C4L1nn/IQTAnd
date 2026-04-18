"""Tüm QSS stilleri."""
from PySide6.QtGui import QColor

from core.constants import (
    BG_BLACK, BG_CARD, BG_CARD_HOVER, BG_ELEVATED, BORDER_COLOR,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, FONT_MAIN
)
from core.theme import get_accent, get_accent_hover


def _rgba(color: str, alpha: int) -> str:
    qcolor = QColor(str(color or "#6EA8FF"))
    if not qcolor.isValid():
        return str(color)
    alpha = max(0, min(255, int(alpha)))
    return f"rgba({qcolor.red()}, {qcolor.green()}, {qcolor.blue()}, {alpha})"


def get_main_stylesheet() -> str:
    acc  = get_accent()
    acc2 = get_accent_hover()
    return f"""
    * {{
        font-family:'{FONT_MAIN}';
        color:{TEXT_PRIMARY};
        selection-background-color:{acc};
        selection-color:#061019;
        outline: none;
    }}

    /* Genel odak stili: yalnızca butonlar ve etiketler için noktalı
       odak çerçevesini kaldır; QLineEdit ve form elemanları hariç. */
    QPushButton:focus {{
        outline: none;
        border: none;
    }}
    QLabel:focus {{
        outline: none;
        border: none;
    }}
    QFrame:focus {{
        outline: none;
    }}
    QWidget#TC:focus {{
        outline: none;
    }}
    QToolTip {{
        background:rgba(8,13,22,0.96);
        color:{TEXT_PRIMARY};
        border:1px solid rgba(255,255,255,0.10);
        border-radius:8px;
        padding:4px 7px;
        font-size:11px;
        font-weight:700;
    }}
    QMainWindow {{
        background:{BG_BLACK};
    }}
    QWidget#AppShell {{
        background:{BG_BLACK};
        border-radius:0px;
    }}
    QFrame#Sidebar {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
            stop:0 #09111B, stop:0.55 #08111C, stop:1 #070B12);
        border-right: 1px solid {BORDER_COLOR};
        border-top-left-radius:0px;
        border-bottom-left-radius:12px;
        border-top-right-radius:0px;
        border-bottom-right-radius:0px;
    }}
    QFrame#Sidebar[flatWindow="true"] {{
        border-radius:0px;
    }}
    QFrame#PlayerBar {{
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
            stop:0 rgba(12,18,29,0.992), stop:1 rgba(7,11,18,0.998));
        border-top: 1px solid {BORDER_COLOR};
        border-bottom-right-radius:12px;
    }}
    QFrame#PlayerBar[flatWindow="true"] {{
        border-radius:0px;
    }}
    QWidget#ContentFrame {{
        background:{BG_BLACK};
        border-top-right-radius:0px;
        border-bottom-right-radius:12px;
    }}
    QWidget#ContentFrame[flatWindow="true"] {{
        border-radius:0px;
    }}
    QFrame {{
        border: none;
    }}
    QLabel {{
        background:transparent;
        color:{TEXT_PRIMARY};
        border: none;
    }}
    QPushButton {{
        border:none;
        background:transparent;
        color:{TEXT_SECONDARY};
        outline:none;
    }}
    QPushButton:hover {{
        color:{TEXT_PRIMARY};
    }}
    QPushButton:focus {{
        border:none;
        outline:none;
    }}
    QPushButton#PlayButton {{
        background: transparent;
        color:#FFFFFF;
        border: none;
        padding: 0;
    }}
    QPushButton#PlayButton:hover {{
        background: transparent;
        border: none;
    }}
    QPushButton#PlayButton:pressed {{
        background: transparent;
    }}
    QSlider#SeekBar::groove:horizontal,
    QSlider#MiniSeekBar::groove:horizontal,
    QSlider#MiniVolSlider::groove:horizontal,
    QSlider#VolSlider::groove:horizontal {{
        border:none; height:3px;
        background:rgba(255,255,255,0.08);
        margin:0; border-radius:2px;
    }}
    QSlider#SeekBar::sub-page:horizontal,
    QSlider#MiniSeekBar::sub-page:horizontal,
    QSlider#MiniVolSlider::sub-page:horizontal,
    QSlider#VolSlider::sub-page:horizontal {{
        background:qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {acc}, stop:1 {acc2});
        border-radius:2px;
    }}
    QSlider#SeekBar::add-page:horizontal,
    QSlider#MiniSeekBar::add-page:horizontal,
    QSlider#MiniVolSlider::add-page:horizontal,
    QSlider#VolSlider::add-page:horizontal {{
        background:rgba(255,255,255,0.07);
        border-radius:2px;
    }}
    QSlider#SeekBar::handle:horizontal,
    QSlider#VolSlider::handle:horizontal {{
        background:{acc};
        border:1px solid rgba(255,255,255,0.16);
        width:10px; height:10px;
        margin:-4px 0; border-radius:5px;
    }}
    QSlider#MiniSeekBar::handle:horizontal,
    QSlider#MiniVolSlider::handle:horizontal {{
        background:{acc};
        border:1px solid rgba(255,255,255,0.16);
        width:9px; height:9px;
        margin:-3px 0; border-radius:4px;
    }}
    QSlider#SeekBar::handle:horizontal:hover,
    QSlider#MiniSeekBar::handle:horizontal:hover,
    QSlider#MiniVolSlider::handle:horizontal:hover,
    QSlider#VolSlider::handle:horizontal:hover {{
        background:{acc2};
        border:1px solid rgba(255,255,255,0.22);
    }}
    QScrollArea {{
        background:transparent;
        border:none;
    }}
    QWidget#TC {{
        background:transparent;
    }}
    QScrollBar:vertical {{
        border:none; background:transparent;
        width:8px; margin:4px 0 4px 0;
    }}
    QScrollBar::handle:vertical {{
        background: rgba(255,255,255,0.12);
        min-height:30px; border-radius:4px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: rgba(255,255,255,0.20);
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        border:none; background:none; height:0;
    }}
    QScrollBar:horizontal {{
        border:none; background:transparent;
        height:8px; margin:0 4px 0 4px;
    }}
    QScrollBar::handle:horizontal {{
        background: rgba(255,255,255,0.12);
        min-width:30px; border-radius:4px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: rgba(255,255,255,0.20);
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        border:none; background:none; width:0;
    }}
    QLineEdit {{
        background:qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {BG_ELEVATED}, stop:1 {BG_CARD});
        color:{TEXT_PRIMARY};
        border-radius:24px;
        padding:0 18px;
        font-size:15px;
        border: 1px solid {BORDER_COLOR};
    }}
    QLineEdit:focus {{
        border: 1px solid {_rgba(acc, 136)};
        background:{BG_CARD};
    }}
    QMenu {{
        background:{BG_ELEVATED};
        color:{TEXT_PRIMARY};
        border:1px solid {BORDER_COLOR};
        border-radius:14px;
        padding:6px;
    }}
    QMenu::item {{
        padding:10px 18px;
        border-radius:10px;
        font-size:13px;
    }}
    QMenu::item:selected {{
        background:{_rgba(acc, 34)};
        color:{TEXT_PRIMARY};
    }}
    QMenu::separator {{
        height:1px;
        background:{BORDER_COLOR};
        margin:6px 10px;
    }}
    QProgressBar {{
        background:{BG_ELEVATED};
        border-radius:5px;
        border:none;
        text-align:center;
        color:transparent;
    }}
    QProgressBar::chunk {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
            stop:0 {acc}, stop:1 {acc2});
        border-radius:5px;
    }}
    """
