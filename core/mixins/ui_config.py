"""Mixin for UiConfig functionality."""
import logging

log = logging.getLogger("iqtMusic")

from core.constants import (
    EQ_PRESETS, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
    THEMES, BG_CARD, BG_ELEVATED, BORDER_COLOR, BG_BLACK
)
from core.theme import get_accent, get_accent_hover
from ui.dialogs import show_toast
from utils.helpers import create_icon

from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QMenu, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QPushButton, QFrame, QComboBox
from PySide6.QtCore import Qt, QPoint
import core.constants as _C
from ui.dialogs import open_eq_dialog, open_sleep_dialog


class UiConfigMixin:

    def _open_settings_dialog(self):
        self.page_settings()

    def _open_eq(self):
        open_eq_dialog(self)


    def _eq_change(self, idx: int, val: int):
        while len(self._eq_vals) <= idx:
            self._eq_vals.append(0)
        self._eq_vals[idx] = val
        self.eq_inst.set_amp_at_index(val, idx)
        try:
            self.player.set_equalizer(self.eq_inst)
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)


    def _apply_eq_preset(self, name: str):
        vals = EQ_PRESETS.get(name, [0]*10)
        self._eq_vals = list(vals)
        for i, v in enumerate(vals):
            self.eq_inst.set_amp_at_index(v, i)
            if hasattr(self, "_eq_sliders") and i < len(self._eq_sliders):
                self._eq_sliders[i].setValue(v)
        try:
            self.player.set_equalizer(self.eq_inst)
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        self._save_settings()
        labels = {
            "Düz": self._tr("equalizer.preset.flat"),
            "Bass": self._tr("equalizer.preset.bass"),
            "Rock": self._tr("equalizer.preset.rock"),
            "Pop": self._tr("equalizer.preset.pop"),
            "Jazz": self._tr("equalizer.preset.jazz"),
            "Klasik": self._tr("equalizer.preset.classical"),
        }
        self.sig.notify.emit(f"{self._tr('equalizer.title')}: {labels.get(name, name)}")

    # ══════════════════════════════════════════════════════════════════════════
    # TEMA
    # ══════════════════════════════════════════════════════════════════════════


    def _dlg_theme(self):
        m = QMenu(self)
        for name in THEMES:
            def _set(n=name):
                _C.CURRENT_THEME = n
                self._save_settings()
                self._apply_styles()
                self.sig.notify.emit(f"Tema: {n}")
            m.addAction(name).triggered.connect(_set)
        m.exec(QCursor.pos())

    # ══════════════════════════════════════════════════════════════════════════
    # UYKU ZAMANLAYICI
    # ══════════════════════════════════════════════════════════════════════════


    def _dlg_sleep(self):
        open_sleep_dialog(self)


    def _sleep_stop(self):
        self.player.stop()
        self._sleep_remaining = 0
        self.lbl_sleep.hide()
        self._set_main_play_icon(False)
        self.sig.notify.emit(self._tr("sleep.stopped"))


    def _update_sleep_display(self):
        if self._sleep_timer.isActive():
            rem = self._sleep_timer.remainingTime() // 1000
            m   = rem // 60
            s   = rem % 60
            self.lbl_sleep.setText(f"⏱ {m}:{s:02d}")
            self.lbl_sleep.show()
        else:
            self.lbl_sleep.hide()

    # ══════════════════════════════════════════════════════════════════════════
    # SHUFFLE & REPEAT
    # ══════════════════════════════════════════════════════════════════════════


    def _toggle_shuffle(self):
        self.shuffle_on = not self.shuffle_on
        self.btn_shuffle.setIcon(create_icon(
            "shuffle", get_accent() if self.shuffle_on else TEXT_MUTED, 20))


    def _toggle_repeat(self):
        self.repeat_mode = (self.repeat_mode + 1) % 3
        icon  = "repeat_one" if self.repeat_mode == 2 else "repeat"
        color = get_accent() if self.repeat_mode > 0 else TEXT_MUTED
        self.btn_repeat.setIcon(create_icon(icon, color, 20))

    # ══════════════════════════════════════════════════════════════════════════
    # DISCORD
    # ══════════════════════════════════════════════════════════════════════════


    def _show_toast(self, msg: str):
        show_toast(self, msg)

    # ══════════════════════════════════════════════════════════════════════════
    # OYNATMA AYARLARI (Hız, Crossfade, Gapless)
    # ══════════════════════════════════════════════════════════════════════════

    def _open_playback_settings(self):
        """Hız, ses cikis cihazi ve ses dengeleme ayarlarini gösterir."""
        acc  = get_accent()
        t = self._tr

        dlg = QDialog(self)
        dlg.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        dlg.setAttribute(Qt.WA_TranslucentBackground, True)
        dlg.setFixedWidth(340)

        outer = QVBoxLayout(dlg)
        outer.setContentsMargins(0, 0, 0, 0)

        shell = QFrame()
        shell.setObjectName("PlaybackSettingsPopup")
        shell.setStyleSheet(f"""
            QFrame#PlaybackSettingsPopup {{
                background: {BG_CARD};
                border: 1px solid {acc}55;
                border-radius: 18px;
            }}
            QLabel {{ background: transparent; border: none; }}
            QComboBox {{
                background:{BG_ELEVATED};
                color:{TEXT_PRIMARY};
                border:1px solid {BORDER_COLOR};
                border-radius:10px;
                padding:8px 10px;
                font-size:12px;
                font-weight:600;
            }}
            QComboBox::drop-down {{ border:none; width:20px; }}
        """)
        outer.addWidget(shell)

        vl = QVBoxLayout(shell)
        vl.setContentsMargins(20, 16, 20, 16)
        vl.setSpacing(14)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title_icon = QLabel()
        title_icon.setPixmap(create_icon("settings", acc, 16).pixmap(16, 16))
        title_icon.setFixedSize(18, 18)
        title_lbl = QLabel(t("playback.title"))
        title_lbl.setStyleSheet(f"font-size:14px; font-weight:900; color:{TEXT_PRIMARY};")
        title_row.addWidget(title_icon)
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        vl.addLayout(title_row)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{acc}33; border:none;")
        vl.addWidget(sep)

        speed_title = QLabel(t("playback.speed"))
        speed_title.setStyleSheet(f"font-size:12px; font-weight:800; color:{TEXT_SECONDARY}; letter-spacing:0.8px;")
        vl.addWidget(speed_title)

        speed_row = QHBoxLayout()
        speed_row.setSpacing(10)
        speed_lbl = QLabel(f"{self._playback_rate:.2g}×")
        speed_lbl.setFixedWidth(40)
        speed_lbl.setAlignment(Qt.AlignCenter)
        speed_lbl.setStyleSheet(f"font-size:15px; font-weight:900; color:{acc};")

        speed_slider = QSlider(Qt.Horizontal)
        speed_slider.setRange(50, 200)
        speed_slider.setValue(int(self._playback_rate * 100))
        speed_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{ background:{BG_ELEVATED}; height:6px; border-radius:3px; }}
            QSlider::handle:horizontal {{ background:{acc}; width:14px; height:14px; margin:-4px 0; border-radius:7px; }}
            QSlider::sub-page:horizontal {{ background:{acc}; border-radius:3px; }}
        """)

        def _on_speed(v):
            rate = v / 100.0
            speed_lbl.setText(f"{rate:.2g}×")
            self._set_playback_rate(rate)

        speed_slider.valueChanged.connect(_on_speed)
        speed_row.addWidget(speed_lbl)
        speed_row.addWidget(speed_slider, 1)
        vl.addLayout(speed_row)

        quick_row = QHBoxLayout()
        quick_row.setSpacing(6)
        for label, val in [("0.75×", 75), ("1×", 100), ("1.25×", 125), ("1.5×", 150)]:
            qb = QPushButton(label)
            qb.setFixedHeight(26)
            qb.setCursor(Qt.PointingHandCursor)
            qb.setFocusPolicy(Qt.NoFocus)
            is_cur = abs(self._playback_rate * 100 - val) < 1
            qb.setStyleSheet(
                f"QPushButton{{background:{'%s33' % acc if is_cur else BG_ELEVATED}; color:{acc if is_cur else TEXT_SECONDARY}; border:1px solid {acc if is_cur else BORDER_COLOR}; border-radius:8px; font-size:11px; font-weight:700; padding:0 8px;}}"
                f"QPushButton:hover{{background:{acc}22; color:{acc}; border-color:{acc}88;}}"
            )
            qb.clicked.connect(lambda _checked=False, v=val: speed_slider.setValue(v))
            quick_row.addWidget(qb)
        vl.addLayout(quick_row)

        sep2 = QFrame()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background:{BORDER_COLOR}; border:none;")
        vl.addWidget(sep2)

        out_title = QLabel(t("playback.output_device"))
        out_title.setStyleSheet(f"font-size:12px; font-weight:800; color:{TEXT_SECONDARY}; letter-spacing:0.8px;")
        vl.addWidget(out_title)

        device_row = QHBoxLayout()
        device_row.setSpacing(8)
        device_combo = QComboBox()
        refresh_btn = QPushButton(t("playback.refresh"))
        refresh_btn.setFixedHeight(34)
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setFocusPolicy(Qt.NoFocus)
        refresh_btn.setStyleSheet(
            f"QPushButton{{background:{BG_ELEVATED}; color:{TEXT_PRIMARY}; border:1px solid {BORDER_COLOR}; border-radius:10px; padding:0 12px; font-size:11px; font-weight:700;}}"
            f"QPushButton:hover{{background:{acc}18; border-color:{acc}66; color:{acc};}}"
        )

        def _fill_devices():
            current_id = str(getattr(self, '_audio_output_device', '') or '')
            current_name = str(getattr(self, '_audio_output_name', '') or '')
            devices = list(self._enum_audio_output_devices())
            device_combo.blockSignals(True)
            device_combo.clear()
            chosen_idx = 0
            for idx, item in enumerate(devices):
                name = str(item.get('name', '') or t("playback.automatic"))
                dev_id = str(item.get('id', '') or '')
                device_combo.addItem(name, dev_id)
                if dev_id and dev_id == current_id:
                    chosen_idx = idx
                elif not dev_id and not current_id and (current_name == name or not current_name):
                    chosen_idx = idx
            device_combo.setCurrentIndex(chosen_idx)
            device_combo.blockSignals(False)

        def _on_device_changed(_index):
            dev_id = str(device_combo.currentData() or '')
            dev_name = str(device_combo.currentText() or t("playback.automatic"))
            self._audio_output_device = dev_id
            self._audio_output_name = '' if not dev_id else dev_name
            self._apply_audio_output_device()
            self._save_settings()

        refresh_btn.clicked.connect(lambda: (setattr(self, '_audio_output_cache', []), _fill_devices()))
        device_combo.currentIndexChanged.connect(_on_device_changed)
        _fill_devices()
        device_row.addWidget(device_combo, 1)
        device_row.addWidget(refresh_btn)
        vl.addLayout(device_row)

        device_hint = QLabel(t("playback.output_device_hint"))
        device_hint.setStyleSheet(f"font-size:11px; color:{TEXT_MUTED};")
        device_hint.setWordWrap(True)
        vl.addWidget(device_hint)

        sep3 = QFrame()
        sep3.setFixedHeight(1)
        sep3.setStyleSheet(f"background:{BORDER_COLOR}; border:none;")
        vl.addWidget(sep3)

        loud_title = QLabel(t("playback.loudness"))
        loud_title.setStyleSheet(f"font-size:12px; font-weight:800; color:{TEXT_SECONDARY}; letter-spacing:0.8px;")
        vl.addWidget(loud_title)

        loud_desc = QLabel(t("playback.loudness_desc"))
        loud_desc.setWordWrap(True)
        loud_desc.setStyleSheet(f"font-size:11px; color:{TEXT_MUTED};")
        vl.addWidget(loud_desc)

        loud_row = QHBoxLayout()
        loud_row.setSpacing(6)
        current_mode = str(getattr(self, '_loudness_mode', 'light') or 'light')
        for mode_key, label in [("off", t("playback.off")), ("light", "Light"), ("strong", "Strong")]:
            btn = QPushButton(label)
            btn.setFixedHeight(28)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFocusPolicy(Qt.NoFocus)
            active = current_mode == mode_key
            btn.setStyleSheet(
                f"QPushButton{{background:{'%s33' % acc if active else BG_ELEVATED}; color:{acc if active else TEXT_SECONDARY}; border:1px solid {acc if active else BORDER_COLOR}; border-radius:9px; padding:0 10px; font-size:11px; font-weight:800;}}"
                f"QPushButton:hover{{background:{acc}22; color:{acc}; border-color:{acc}88;}}"
            )
            def _set_mode(_checked=False, mk=mode_key):
                self._loudness_mode = mk
                self._save_settings()
                dlg.close()
            btn.clicked.connect(_set_mode)
            loud_row.addWidget(btn)
        vl.addLayout(loud_row)

        try:
            btn_pos = self._speed_btn.mapToGlobal(QPoint(0, 0))
            dlg_h = dlg.sizeHint().height() or 360
            x = btn_pos.x() - dlg.width() // 2
            y = btn_pos.y() - dlg_h - 8
            from PySide6.QtWidgets import QApplication as _QApp
            screen = _QApp.primaryScreen().geometry()
            x = max(8, min(x, screen.width()  - dlg.width()  - 8))
            y = max(8, min(y, screen.height() - dlg_h - 8))
            dlg.move(x, y)
        except Exception:
            pass

        dlg.exec()
