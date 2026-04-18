"""Downloads page."""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from core.constants import BG_BLACK, BG_ELEVATED, BORDER_COLOR, TEXT_PRIMARY, TEXT_SECONDARY
from core.theme import get_accent
from pages.common import _build_page_header
from pages.reorderable_tracks import build_reorderable_track_panel
from utils.helpers import create_icon


def build_downloads_page(app):
    app.current_page = "downloads"
    t = app._tr

    acc = get_accent()
    pg = QWidget()
    pg.setStyleSheet(f"background:{BG_BLACK};")
    vl = QVBoxLayout(pg)
    vl.setContentsMargins(36, 36, 36, 0)

    fmt = getattr(app.dl, "dl_format", "m4a").upper()
    qual = getattr(app.dl, "dl_quality", "best")
    qual_disp = f"{qual} kbps" if qual != "best" else t("downloads.best_quality")
    info_lbl = QLabel(f"{fmt}  ·  {qual_disp}")
    info_lbl.setAlignment(Qt.AlignCenter)
    info_lbl.setStyleSheet(
        f"font-size:12px; font-weight:800; color:{TEXT_SECONDARY}; background:{BG_ELEVATED}; "
        f"padding:8px 14px; border-radius:12px; border:1px solid {acc}24;"
    )

    btn_ss = f"""
        QPushButton {{
            background:transparent;
            color:{TEXT_PRIMARY};
            padding:10px 14px;
            border-radius:12px;
            font-weight:800;
            font-size:13px;
            border:1px solid transparent;
        }}
        QPushButton:hover {{
            background:rgba(255,255,255,0.045);
            border-color:{acc}30;
        }}
        QPushButton:pressed {{
            background:rgba(255,255,255,0.065);
            border-color:{acc}4A;
        }}
    """

    settings_btn = QPushButton(t("downloads.settings_button"))
    settings_btn.setCursor(Qt.PointingHandCursor)
    settings_btn.setIcon(create_icon("settings", TEXT_SECONDARY, 15))
    settings_btn.setIconSize(QSize(15, 15))
    settings_btn.setStyleSheet(btn_ss)
    settings_btn.clicked.connect(lambda: app.page_settings("downloads"))

    folder_btn = QPushButton(t("downloads.open_folder"))
    folder_btn.setCursor(Qt.PointingHandCursor)
    folder_btn.setIcon(create_icon("folder", TEXT_SECONDARY, 15))
    folder_btn.setIconSize(QSize(15, 15))
    folder_btn.setStyleSheet(btn_ss)
    folder_btn.clicked.connect(app._open_dl_folder)

    actions = QFrame()
    actions.setObjectName("DownloadsHeaderActions")
    actions.setAttribute(Qt.WA_StyledBackground, True)
    actions.setStyleSheet(
        f"""
        QFrame#DownloadsHeaderActions {{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 rgba(255,255,255,0.026), stop:1 rgba(255,255,255,0.016));
            border:1px solid rgba(255,255,255,0.06);
            border-radius:16px;
        }}
        """
    )
    app._add_soft_shadow(actions, 18, QColor(0, 0, 0, 72), 0, 6)
    actions_l = QHBoxLayout(actions)
    actions_l.setContentsMargins(8, 8, 8, 8)
    actions_l.setSpacing(8)

    sep_1 = QFrame()
    sep_1.setFixedWidth(1)
    sep_1.setStyleSheet(f"background:{BORDER_COLOR}; border:none;")

    sep_2 = QFrame()
    sep_2.setFixedWidth(1)
    sep_2.setStyleSheet(f"background:{BORDER_COLOR}; border:none;")

    actions_l.addWidget(info_lbl)
    actions_l.addWidget(sep_1)
    actions_l.addWidget(settings_btn)
    actions_l.addWidget(sep_2)
    actions_l.addWidget(folder_btn)

    tracks = app.dl.all_tracks()
    vl.addWidget(
        _build_page_header(
            app,
            t("downloads.title"),
            t("downloads.subtitle", count=len(tracks)),
            eyebrow=t("downloads.eyebrow"),
            right_widget=actions,
        )
    )
    vl.addSpacing(24)
    vl.addWidget(
        build_reorderable_track_panel(
            app,
            tracks,
            "downloads",
            t("downloads.empty"),
        )
    )
    return pg
