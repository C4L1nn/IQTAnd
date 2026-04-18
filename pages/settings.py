"""Main settings page."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QAbstractSpinBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QKeySequenceEdit,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.constants import (
    BG_BLACK,
    BG_CARD,
    BG_CARD_HOVER,
    BG_ELEVATED,
    BORDER_COLOR,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from core.i18n import LANGUAGE_OPTIONS
from core.theme import get_accent, get_accent_hover
from core.geo import COUNTRY_NAMES, detect_content_region, normalize_region, region_display_name
from pages.common import _build_page_header
from utils.helpers import create_icon


_TAB_IDS = ("general", "playback", "shortcuts", "discord", "downloads")


def _rgba(color: str, alpha: int) -> str:
    qcolor = QColor(str(color or "#6EA8FF"))
    if not qcolor.isValid():
        return str(color)
    alpha = max(0, min(255, int(alpha)))
    return f"rgba({qcolor.red()}, {qcolor.green()}, {qcolor.blue()}, {alpha})"


def _control_button_style() -> str:
    acc = get_accent()
    return f"""
        QPushButton {{
            background:{acc};
            color:#061019;
            border:none;
            border-radius:10px;
            padding:8px 12px;
            font-size:12px;
            font-weight:850;
        }}
        QPushButton:hover {{
            background:{get_accent_hover()};
        }}
    """


def _combo_style() -> str:
    acc = get_accent()
    return f"""
        QComboBox {{
            background:{BG_ELEVATED};
            color:{TEXT_PRIMARY};
            border:1px solid {BORDER_COLOR};
            border-radius:10px;
            padding:7px 10px;
            min-width:150px;
            font-size:12px;
            font-weight:750;
        }}
        QComboBox:hover {{
            border-color:{_rgba(acc, 78)};
        }}
        QComboBox::drop-down {{
            width:26px;
            border:none;
        }}
        QComboBox QAbstractItemView {{
            background:{BG_ELEVATED};
            color:{TEXT_PRIMARY};
            border:1px solid {BORDER_COLOR};
            selection-background-color:{_rgba(acc, 50)};
            padding:4px;
        }}
    """


def _key_sequence_style() -> str:
    acc = get_accent()
    return f"""
        QKeySequenceEdit {{
            background:{BG_ELEVATED};
            color:{TEXT_PRIMARY};
            border:1px solid {BORDER_COLOR};
            border-radius:10px;
            padding:7px 10px;
            min-width:150px;
            font-size:12px;
            font-weight:750;
        }}
        QKeySequenceEdit:hover {{
            border-color:{_rgba(acc, 78)};
        }}
    """


def _spin_style() -> str:
    acc = get_accent()
    return f"""
        QSpinBox {{
            background:{BG_ELEVATED};
            color:{TEXT_PRIMARY};
            border:1px solid {BORDER_COLOR};
            border-radius:10px;
            padding:7px 10px;
            min-width:82px;
            font-size:12px;
            font-weight:750;
        }}
        QSpinBox:hover {{
            border-color:{_rgba(acc, 78)};
        }}
    """


def _switch_style() -> str:
    acc = get_accent()
    return f"""
        QCheckBox {{
            color:{TEXT_PRIMARY};
            font-size:12px;
            font-weight:800;
            spacing:8px;
            background:transparent;
        }}
        QCheckBox::indicator {{
            width:34px;
            height:18px;
            border-radius:9px;
            background:rgba(255,255,255,0.10);
            border:1px solid rgba(255,255,255,0.12);
        }}
        QCheckBox::indicator:checked {{
            background:{_rgba(acc, 210)};
            border-color:{_rgba(acc, 230)};
        }}
    """


def _section_title(app, key: str) -> QLabel:
    lbl = QLabel(app._tr(key))
    lbl.setStyleSheet(
        f"font-size:11px; font-weight:900; letter-spacing:1.4px; "
        f"color:{get_accent()}; background:transparent; border:none;"
    )
    return lbl


def _row(app, title_key: str, desc_key: str, control: QWidget) -> QFrame:
    row = QFrame()
    row.setObjectName("SettingsRow")
    row.setAttribute(Qt.WA_StyledBackground, True)
    row.setStyleSheet(f"""
        QFrame#SettingsRow {{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 rgba(255,255,255,0.026), stop:1 {BG_CARD});
            border:1px solid {BORDER_COLOR};
            border-radius:16px;
        }}
        QFrame#SettingsRow:hover {{
            background:{BG_CARD_HOVER};
            border-color:{_rgba(get_accent(), 58)};
        }}
        QFrame#SettingsRow QLabel {{
            background:transparent;
            border:none;
        }}
    """)
    layout = QHBoxLayout(row)
    layout.setContentsMargins(16, 13, 14, 13)
    layout.setSpacing(16)

    text_col = QVBoxLayout()
    text_col.setContentsMargins(0, 0, 0, 0)
    text_col.setSpacing(3)
    title = QLabel(app._tr(title_key))
    title.setStyleSheet(f"font-size:14px; font-weight:850; color:{TEXT_PRIMARY};")
    desc = QLabel(app._tr(desc_key))
    desc.setWordWrap(True)
    desc.setStyleSheet(f"font-size:11px; color:{TEXT_MUTED};")
    text_col.addWidget(title)
    text_col.addWidget(desc)
    layout.addLayout(text_col, 1)
    layout.addWidget(control, 0, Qt.AlignRight | Qt.AlignVCenter)
    return row


def _make_switch(app, checked: bool, on_change) -> QCheckBox:
    switch = QCheckBox()
    switch.setChecked(bool(checked))
    switch.setCursor(Qt.PointingHandCursor)
    switch.setStyleSheet(_switch_style())

    def _sync_text(value: bool):
        switch.setText(app._tr("settings.enabled" if value else "settings.disabled"))

    _sync_text(switch.isChecked())
    switch.toggled.connect(lambda value: (_sync_text(bool(value)), on_change(bool(value))))
    return switch


def _make_combo(items: list[tuple[str, object]], current, on_change) -> QComboBox:
    combo = QComboBox()
    combo.setStyleSheet(_combo_style())
    for label, data in items:
        combo.addItem(label, data)
    idx = combo.findData(current)
    combo.setCurrentIndex(idx if idx >= 0 else 0)
    combo.currentIndexChanged.connect(lambda _idx, c=combo: on_change(c.currentData()))
    return combo


def _make_spin(value: int, minimum: int, maximum: int, suffix: str, on_change) -> QSpinBox:
    spin = QSpinBox()
    spin.setRange(minimum, maximum)
    spin.setValue(max(minimum, min(maximum, int(value or minimum))))
    spin.setSuffix(suffix)
    spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
    spin.setAlignment(Qt.AlignCenter)
    spin.setStyleSheet(_spin_style())
    spin.valueChanged.connect(lambda val: on_change(int(val)))
    return spin


def _tab_container() -> tuple[QScrollArea, QVBoxLayout]:
    sc = QScrollArea()
    sc.setWidgetResizable(True)
    sc.setFrameShape(QFrame.NoFrame)
    sc.setStyleSheet("background:transparent; border:none;")

    holder = QWidget()
    holder.setObjectName("SettingsTabBody")
    holder.setStyleSheet("background:transparent; border:none;")
    layout = QVBoxLayout(holder)
    layout.setContentsMargins(2, 16, 2, 28)
    layout.setSpacing(10)
    sc.setWidget(holder)
    return sc, layout


def _notify_saved(app):
    try:
        app.sig.notify.emit(app._tr("settings.applied"))
    except Exception:
        pass


def _general_tab(app) -> QScrollArea:
    sc, layout = _tab_container()
    layout.addWidget(_section_title(app, "settings.section.interface"))

    lang_items = [(app._tr(f"language.name.{code}"), code) for code in LANGUAGE_OPTIONS]
    lang_combo = _make_combo(
        lang_items,
        getattr(app, "_language", "tr"),
        lambda code: app._set_language(str(code or "tr")),
    )
    layout.addWidget(_row(app, "settings.general.language", "settings.general.language_desc", lang_combo))

    region_items = [(app._tr("settings.region.auto"), "auto")]
    for code in sorted(COUNTRY_NAMES.keys(), key=lambda item: region_display_name(item, getattr(app, "_language", "tr"))):
        label = f"{region_display_name(code, getattr(app, '_language', 'tr'))} ({code})"
        region_items.append((label, f"manual:{code}"))
    current_mode = str(getattr(app, "_content_region_mode", "auto") or "auto").strip().lower()
    current_region = normalize_region(getattr(app, "_content_region", "TR") or "TR")
    region_value = "auto" if current_mode != "manual" else f"manual:{current_region}"
    region_combo = _make_combo(
        region_items,
        region_value,
        lambda value: _set_content_region(app, str(value or "auto")),
    )
    layout.addWidget(_row(app, "settings.general.region", "settings.general.region_desc", region_combo))
    layout.addStretch()
    return sc


def _set_content_region(app, value: str):
    clean = str(value or "auto").strip()
    if clean == "auto":
        app._content_region_mode = "auto"
        try:
            app._content_region = detect_content_region(
                {
                    "content_region_mode": "auto",
                    "content_region": getattr(app, "_content_region", "TR"),
                },
                session=getattr(app, "_http", None),
                base_dir=getattr(app, "base_dir", ""),
            )
        except Exception:
            app._content_region = normalize_region(getattr(app, "_content_region", "TR") or "TR")
    elif clean.startswith("manual:"):
        app._content_region_mode = "manual"
        app._content_region = normalize_region(clean.split(":", 1)[1], "TR")
    else:
        return

    app._save_settings()
    try:
        app._home_force_curated_cover_refresh = True
        app._home_cache.clear()
    except Exception:
        pass
    try:
        app._invalidate_home_cache()
        if getattr(app, "current_page", None) == "home":
            app.page_home()
    except Exception:
        pass
    _notify_saved(app)


def _playback_tab(app) -> QScrollArea:
    sc, layout = _tab_container()
    layout.addWidget(_section_title(app, "settings.section.playback"))

    layout.addWidget(_row(
        app,
        "settings.playback.media_keys",
        "settings.playback.media_keys_desc",
        _make_switch(app, getattr(app, "_media_keys_enabled", True), lambda enabled: _set_media_keys(app, enabled)),
    ))
    layout.addWidget(_row(
        app,
        "settings.playback.preload",
        "settings.playback.preload_desc",
        _make_switch(app, getattr(app, "_next_preload_on", True), lambda enabled: _set_attr_saved(app, "_next_preload_on", enabled)),
    ))

    loudness_items = [
        (app._tr("settings.playback.loudness.off"), "off"),
        (app._tr("settings.playback.loudness.light"), "light"),
        (app._tr("settings.playback.loudness.strong"), "strong"),
    ]
    layout.addWidget(_row(
        app,
        "settings.playback.loudness",
        "settings.playback.loudness_desc",
        _make_combo(loudness_items, getattr(app, "_loudness_mode", "light"), lambda mode: _set_loudness(app, str(mode or "light"))),
    ))

    rate_items = [("0.75x", 0.75), ("1.0x", 1.0), ("1.25x", 1.25), ("1.5x", 1.5), ("2.0x", 2.0)]
    layout.addWidget(_row(
        app,
        "settings.playback.rate",
        "settings.playback.rate_desc",
        _make_combo(rate_items, float(getattr(app, "_playback_rate", 1.0) or 1.0), lambda rate: app._set_playback_rate(float(rate or 1.0))),
    ))

    layout.addWidget(_row(
        app,
        "settings.playback.volume_step",
        "settings.playback.volume_step_desc",
        _make_spin(getattr(app, "_volume_step", 5), 1, 20, "%", lambda value: _set_attr_saved(app, "_volume_step", value)),
    ))
    layout.addWidget(_row(
        app,
        "settings.playback.seek_step",
        "settings.playback.seek_step_desc",
        _make_spin(getattr(app, "_seek_step_sec", 5), 1, 30, " s", lambda value: _set_attr_saved(app, "_seek_step_sec", value)),
    ))
    layout.addStretch()
    return sc


def _set_media_keys(app, enabled: bool):
    app._media_keys_enabled = bool(enabled)
    app._save_settings()
    if enabled and getattr(app, "_media_key_listener", None) is None:
        try:
            app._setup_media_keys()
        except Exception:
            pass
    _notify_saved(app)


def _set_attr_saved(app, attr: str, value):
    setattr(app, attr, value)
    app._save_settings()
    _notify_saved(app)


def _set_loudness(app, mode: str):
    clean = str(mode or "light").strip().lower()
    if clean not in {"off", "light", "strong"}:
        clean = "light"
    app._loudness_mode = clean
    app._save_settings()
    _notify_saved(app)


def _shortcuts_tab(app) -> QScrollArea:
    sc, layout = _tab_container()
    layout.addWidget(_section_title(app, "settings.section.shortcuts"))

    definitions = list(getattr(app, "_shortcut_definitions", []) or [])
    if not definitions and hasattr(app, "_setup_shortcuts"):
        try:
            app._setup_shortcuts()
            definitions = list(getattr(app, "_shortcut_definitions", []) or [])
        except Exception:
            definitions = []

    for item in definitions:
        shortcut_id = str(item.get("id") or "").strip()
        if not shortcut_id:
            continue
        control = _shortcut_control(app, item)
        layout.addWidget(_row(
            app,
            item.get("label_key") or shortcut_id,
            f"shortcut.desc.{shortcut_id}",
            control,
        ))

    layout.addStretch()
    return sc


def _shortcut_control(app, item: dict) -> QWidget:
    wrap = QWidget()
    wrap.setStyleSheet("background:transparent; border:none;")
    layout = QHBoxLayout(wrap)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    shortcut_id = str(item.get("id") or "").strip()
    current = str((getattr(app, "_shortcut_map", {}) or {}).get(shortcut_id) or item.get("default") or "")

    editor = QKeySequenceEdit()
    editor.setKeySequence(QKeySequence(current))
    editor.setStyleSheet(_key_sequence_style())
    editor.setMinimumWidth(170)

    reset_btn = QPushButton(app._tr("settings.shortcuts.reset"))
    reset_btn.setCursor(Qt.PointingHandCursor)
    reset_btn.setStyleSheet(_control_button_style())

    def _save_editor():
        sequence = editor.keySequence().toString(QKeySequence.NativeText)
        if hasattr(app, "_set_shortcut_sequence"):
            app._set_shortcut_sequence(shortcut_id, sequence)
        _notify_saved(app)

    def _reset():
        default = str(item.get("default") or "")
        editor.setKeySequence(QKeySequence(default))
        if hasattr(app, "_reset_shortcut_sequence"):
            app._reset_shortcut_sequence(shortcut_id)
        _notify_saved(app)

    editor.editingFinished.connect(_save_editor)
    reset_btn.clicked.connect(_reset)
    layout.addWidget(editor)
    layout.addWidget(reset_btn)
    return wrap


def _discord_tab(app) -> QScrollArea:
    sc, layout = _tab_container()
    layout.addWidget(_section_title(app, "settings.section.discord"))

    layout.addWidget(_row(
        app,
        "settings.discord.presence",
        "settings.discord.presence_desc",
        _make_switch(
            app,
            getattr(app, "_discord_presence_enabled", True),
            lambda enabled: _set_discord_presence(app, enabled),
        ),
    ))

    display_items = [
        (app._tr("settings.discord.display.song"), "song"),
        (app._tr("settings.discord.display.artist"), "artist"),
    ]
    layout.addWidget(_row(
        app,
        "settings.discord.display",
        "settings.discord.display_desc",
        _make_combo(
            display_items,
            getattr(app, "_discord_display_mode", "song"),
            lambda mode: _set_discord_display(app, str(mode or "song")),
        ),
    ))
    layout.addStretch()
    return sc


def _set_discord_presence(app, enabled: bool):
    if hasattr(app, "_set_discord_presence_enabled"):
        app._set_discord_presence_enabled(bool(enabled))
    else:
        app._discord_presence_enabled = bool(enabled)
        app._save_settings()
    _notify_saved(app)


def _set_discord_display(app, mode: str):
    if hasattr(app, "_set_discord_display_mode"):
        app._set_discord_display_mode(mode)
    else:
        app._discord_display_mode = mode if mode in {"song", "artist"} else "song"
        app._save_settings()
    _notify_saved(app)


def _downloads_tab(app) -> QScrollArea:
    sc, layout = _tab_container()
    layout.addWidget(_section_title(app, "settings.section.downloads"))

    current_fmt = str(getattr(app.dl, "dl_format", "m4a") or "m4a").lower()
    current_qual = str(getattr(app.dl, "dl_quality", "best") or "best")

    qual_combo = _make_combo(
        [("128 kbps", "128"), ("192 kbps", "192"), ("320 kbps", "320"), (app._tr("downloads.best_quality"), "best")],
        current_qual,
        lambda quality: _set_download_quality(app, format_combo.currentData(), str(quality or "best")),
    )
    qual_combo.setEnabled(current_fmt == "mp3")

    def _format_changed(fmt):
        fmt = str(fmt or "m4a").lower()
        qual_combo.setEnabled(fmt == "mp3")
        quality = str(qual_combo.currentData() or "best") if fmt == "mp3" else "best"
        _set_download_quality(app, fmt, quality)

    format_combo = _make_combo(
        [("M4A", "m4a"), ("MP3", "mp3"), ("FLAC", "flac"), ("WAV", "wav")],
        current_fmt,
        _format_changed,
    )

    layout.addWidget(_row(app, "settings.downloads.format", "settings.downloads.format_desc", format_combo))
    layout.addWidget(_row(app, "settings.downloads.quality", "settings.downloads.quality_desc", qual_combo))
    layout.addWidget(_row(app, "settings.downloads.folder", "settings.downloads.folder_desc", _folder_control(app)))
    layout.addStretch()
    return sc


def _set_download_quality(app, fmt, quality: str):
    clean_fmt = str(fmt or "m4a").lower()
    clean_qual = str(quality or "best")
    if clean_fmt != "mp3":
        clean_qual = "best"
    app.dl.set_quality(clean_fmt, clean_qual)
    app._save_dl_settings()
    _notify_saved(app)


def _folder_control(app) -> QWidget:
    wrap = QWidget()
    wrap.setStyleSheet("background:transparent; border:none;")
    layout = QHBoxLayout(wrap)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    label = QLabel(str(getattr(app.dl, "dl_dir", "") or ""))
    label.setMinimumWidth(210)
    label.setMaximumWidth(340)
    label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    label.setWordWrap(False)
    label.setStyleSheet(
        f"background:{BG_ELEVATED}; color:{TEXT_SECONDARY}; border:1px solid {BORDER_COLOR}; "
        "border-radius:10px; padding:8px 10px; font-size:11px;"
    )

    button = QPushButton(app._tr("settings.downloads.folder_choose"))
    button.setCursor(Qt.PointingHandCursor)
    button.setIcon(create_icon("folder", "#061019", 15))
    button.setStyleSheet(_control_button_style())

    def _browse():
        current_dir = str(getattr(app.dl, "dl_dir", "") or os.path.expanduser("~"))
        chosen = QFileDialog.getExistingDirectory(app, app._tr("settings.folder_dialog_title"), current_dir)
        if not chosen:
            return
        os.makedirs(chosen, exist_ok=True)
        app.dl.dl_dir = chosen
        label.setText(chosen)
        app._save_dl_settings()
        _notify_saved(app)

    button.clicked.connect(_browse)
    layout.addWidget(label, 1)
    layout.addWidget(button, 0)
    return wrap


def build_settings_page(app, initial_tab: str = "general") -> QWidget:
    app.current_page = "settings"
    t = app._tr
    acc = get_accent()

    pg = QWidget()
    pg.setObjectName("SettingsPage")
    pg.setStyleSheet(f"background:{BG_BLACK};")

    layout = QVBoxLayout(pg)
    layout.setContentsMargins(36, 36, 36, 0)
    layout.setSpacing(18)
    layout.addWidget(
        _build_page_header(
            app,
            t("settings.page.title"),
            t("settings.page.subtitle"),
            eyebrow=t("settings.page.eyebrow"),
        )
    )

    tabs = QTabWidget()
    tabs.setObjectName("SettingsTabs")
    tabs.setDocumentMode(True)
    tabs.setStyleSheet(f"""
        QTabWidget::pane {{
            background:transparent;
            border:none;
            top:-1px;
        }}
        QTabBar::tab {{
            background:rgba(255,255,255,0.045);
            color:{TEXT_SECONDARY};
            border:1px solid rgba(255,255,255,0.06);
            border-radius:12px;
            padding:9px 16px;
            margin-right:8px;
            font-size:12px;
            font-weight:850;
            min-width:92px;
        }}
        QTabBar::tab:hover {{
            color:{TEXT_PRIMARY};
            border-color:{_rgba(acc, 48)};
        }}
        QTabBar::tab:selected {{
            background:{_rgba(acc, 34)};
            color:{TEXT_PRIMARY};
            border-color:{_rgba(acc, 92)};
        }}
    """)

    tabs.addTab(_general_tab(app), t("settings.tab.general"))
    tabs.addTab(_playback_tab(app), t("settings.tab.playback"))
    tabs.addTab(_shortcuts_tab(app), t("settings.tab.shortcuts"))
    tabs.addTab(_discord_tab(app), t("settings.tab.discord"))
    tabs.addTab(_downloads_tab(app), t("settings.tab.downloads"))

    tab_id = str(initial_tab or "general").strip().lower()
    tabs.setCurrentIndex(_TAB_IDS.index(tab_id) if tab_id in _TAB_IDS else 0)
    layout.addWidget(tabs, 1)
    return pg
