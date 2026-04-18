"""İndirme Ayarları diyaloğu."""
import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QWidget, QButtonGroup, QRadioButton, QLineEdit,
    QFileDialog, QSizePolicy
)
from PySide6.QtCore import Qt

from core.constants import (
    BG_DARK, BG_CARD, BORDER_COLOR,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED
)
from core.theme import get_accent
from ui.titlebar import TitleBar


def open_download_settings_dialog(app):
    """
    İndirme format, kalite ve klasör ayarları diyaloğu.
    Seçimler app.dl üzerinde anında uygulanır ve settings.json'a kaydedilir.
    """
    acc = get_accent()
    t = app._tr

    dlg = QDialog(app)
    dlg._tr = app._tr
    dlg.setWindowFlags(dlg.windowFlags() | Qt.FramelessWindowHint)
    dlg.setFixedSize(500, 620)
    dlg.setStyleSheet(f"background:{BG_DARK}; color:white;")

    host_l = QVBoxLayout(dlg)
    host_l.setContentsMargins(0, 0, 0, 0)
    host_l.setSpacing(0)

    # Başlık çubuğu
    tb = TitleBar(dlg, title=t("settings.download_title"))
    tb.setStyleSheet(f"background:{BG_DARK}; color:white;")
    host_l.addWidget(tb)

    sep = QFrame()
    sep.setFixedHeight(1)
    sep.setStyleSheet(f"background:{acc}44;")
    host_l.addWidget(sep)

    # İçerik alanı
    content = QWidget()
    content.setStyleSheet(f"background:{BG_DARK};")
    host_l.addWidget(content, 1)

    vl = QVBoxLayout(content)
    vl.setContentsMargins(28, 20, 28, 24)
    vl.setSpacing(0)

    # ── Yardımcı: bölüm başlığı ──────────────────────────────────────────
    def _section_lbl(text):
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"font-size:11px; font-weight:700; color:{acc}; "
            f"letter-spacing:1.5px; background:transparent; margin-bottom:10px;")
        return lbl

    # ── Radio buton stili ────────────────────────────────────────────────
    _rb_style = f"""
        QRadioButton {{
            color: {TEXT_SECONDARY};
            font-size: 13px;
            font-weight: 600;
            spacing: 10px;
            background: transparent;
            padding: 4px 0;
        }}
        QRadioButton:checked {{
            color: {TEXT_PRIMARY};
        }}
        QRadioButton::indicator {{
            width: 16px;
            height: 16px;
            border-radius: 8px;
            border: 2px solid {TEXT_MUTED};
            background: transparent;
        }}
        QRadioButton::indicator:checked {{
            border: 2px solid {acc};
            background: {acc};
        }}
    """

    # ──────────────────────────────────────────────────────────────────────
    # FORMAT BÖLÜMÜ
    # ──────────────────────────────────────────────────────────────────────
    vl.addWidget(_section_lbl(t("settings.section.format")))

    fmt_frame = QFrame()
    fmt_frame.setStyleSheet(
        f"background:{BG_CARD}; border-radius:14px; border:1px solid {BORDER_COLOR};")
    fmt_l = QHBoxLayout(fmt_frame)
    fmt_l.setContentsMargins(16, 12, 16, 12)
    fmt_l.setSpacing(0)

    fmt_group = QButtonGroup(dlg)
    _formats = [
        ("M4A",  "m4a",  t("settings.format_hint.m4a")),
        ("MP3",  "mp3",  t("settings.format_hint.mp3")),
        ("FLAC", "flac", t("settings.format_hint.flac")),
        ("WAV",  "wav",  t("settings.format_hint.wav")),
    ]

    current_fmt = getattr(app.dl, "dl_format", "m4a")

    fmt_radios: dict[str, QRadioButton] = {}
    for i, (label, key, hint) in enumerate(_formats):
        col = QVBoxLayout()
        col.setSpacing(2)
        rb = QRadioButton(label)
        rb.setStyleSheet(_rb_style)
        rb.setChecked(key == current_fmt)
        fmt_group.addButton(rb)
        fmt_radios[key] = rb
        hint_lbl = QLabel(hint)
        hint_lbl.setStyleSheet(
            f"color:{TEXT_MUTED}; font-size:10px; background:transparent; padding-left:26px;")
        col.addWidget(rb)
        col.addWidget(hint_lbl)
        fmt_l.addLayout(col)
        if i < len(_formats) - 1:
            fmt_l.addStretch(1)

    vl.addWidget(fmt_frame)
    vl.addSpacing(22)

    # ──────────────────────────────────────────────────────────────────────
    # KALİTE BÖLÜMÜ (yalnızca MP3 için anlamlı)
    # ──────────────────────────────────────────────────────────────────────
    vl.addWidget(_section_lbl(t("settings.section.quality")))

    qual_frame = QFrame()
    qual_frame.setStyleSheet(
        f"background:{BG_CARD}; border-radius:14px; border:1px solid {BORDER_COLOR};")
    qual_l = QHBoxLayout(qual_frame)
    qual_l.setContentsMargins(16, 12, 16, 12)
    qual_l.setSpacing(0)

    qual_group = QButtonGroup(dlg)
    _qualities = [
        ("128 kbps", "128"),
        ("192 kbps", "192"),
        ("320 kbps", "320"),
        (t("downloads.best_quality"), "best"),
    ]

    current_qual = getattr(app.dl, "dl_quality", "best")

    qual_radios: dict[str, QRadioButton] = {}
    for i, (label, key) in enumerate(_qualities):
        rb = QRadioButton(label)
        rb.setStyleSheet(_rb_style)
        rb.setChecked(key == current_qual)
        qual_group.addButton(rb)
        qual_radios[key] = rb
        qual_l.addWidget(rb)
        if i < len(_qualities) - 1:
            qual_l.addStretch(1)

    vl.addWidget(qual_frame)

    # Kalite seçimi, yalnızca MP3 seçiliyken aktif
    def _update_qual_state():
        is_mp3 = fmt_radios["mp3"].isChecked()
        qual_frame.setEnabled(is_mp3)
        qual_frame.setStyleSheet(
            f"background:{BG_CARD}; border-radius:14px; border:1px solid {BORDER_COLOR};"
            if is_mp3 else
            f"background:{BG_CARD}44; border-radius:14px; border:1px solid {BORDER_COLOR}44; opacity:0.4;"
        )
        for rb in qual_radios.values():
            rb.setEnabled(is_mp3)

    for rb in fmt_radios.values():
        rb.toggled.connect(lambda _: _update_qual_state())

    _update_qual_state()

    vl.addSpacing(22)

    # ──────────────────────────────────────────────────────────────────────
    # İNDİRME KLASÖRÜ
    # ──────────────────────────────────────────────────────────────────────
    vl.addWidget(_section_lbl(t("settings.section.folder")))

    folder_frame = QFrame()
    folder_frame.setStyleSheet(
        f"background:{BG_CARD}; border-radius:14px; border:1px solid {BORDER_COLOR};")
    folder_l = QHBoxLayout(folder_frame)
    folder_l.setContentsMargins(14, 10, 10, 10)
    folder_l.setSpacing(8)

    current_dir = getattr(app.dl, "dl_dir", "")
    folder_lbl = QLabel(current_dir or t("settings.folder_placeholder"))
    folder_lbl.setStyleSheet(
        f"color:{TEXT_SECONDARY}; font-size:12px; background:transparent;")
    folder_lbl.setWordWrap(False)
    folder_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    browse_btn = QPushButton(t("settings.change"))
    browse_btn.setFixedHeight(32)
    browse_btn.setCursor(Qt.PointingHandCursor)
    browse_btn.setFocusPolicy(Qt.NoFocus)
    browse_btn.setStyleSheet(
        f"background:{acc}; color:black; border:none; border-radius:10px; "
        f"font-size:12px; font-weight:700; padding:0 14px;")

    _chosen_dir = [current_dir]  # mutable container for closure

    def _browse():
        d = QFileDialog.getExistingDirectory(
            dlg, t("settings.folder_dialog_title"), _chosen_dir[0] or os.path.expanduser("~"))
        if d:
            _chosen_dir[0] = d
            folder_lbl.setText(d)

    browse_btn.clicked.connect(_browse)
    folder_l.addWidget(folder_lbl, 1)
    folder_l.addWidget(browse_btn)
    vl.addWidget(folder_frame)

    vl.addSpacing(22)

    # Dil ayarı ana Ayarlar sayfasına taşındı.

    vl.addSpacing(22)

    # Last.fm API ayari kaldirildi; uygulama icinde gömülü kullaniliyor.

    vl.addStretch(1)

    # ── Butonlar ─────────────────────────────────────────────────────────
    btn_row = QHBoxLayout()
    btn_row.setSpacing(10)

    cancel_btn = QPushButton(t("settings.cancel"))
    cancel_btn.setFixedHeight(40)
    cancel_btn.setCursor(Qt.PointingHandCursor)
    cancel_btn.setFocusPolicy(Qt.NoFocus)
    cancel_btn.setStyleSheet(
        f"background:{BG_CARD}; color:{TEXT_SECONDARY}; border:1px solid {BORDER_COLOR}; "
        f"border-radius:12px; font-size:13px; font-weight:700; padding:0 20px;")
    cancel_btn.clicked.connect(dlg.reject)

    save_btn = QPushButton(t("settings.save"))
    save_btn.setFixedHeight(40)
    save_btn.setCursor(Qt.PointingHandCursor)
    save_btn.setFocusPolicy(Qt.NoFocus)
    save_btn.setStyleSheet(
        f"QPushButton {{ background:{acc}; color:black; border:none; "
        f"border-radius:12px; font-size:13px; font-weight:800; padding:0 28px; }}"
        f"QPushButton:hover {{ background:{acc}DD; }}")

    def _save():
        # Seçilen formatı bul
        chosen_fmt = "m4a"
        for key, rb in fmt_radios.items():
            if rb.isChecked():
                chosen_fmt = key
                break

        # Seçilen kaliteyi bul (sadece mp3 için geçerli)
        chosen_qual = "best"
        for key, rb in qual_radios.items():
            if rb.isChecked():
                chosen_qual = key
                break
        if chosen_fmt != "mp3":
            chosen_qual = "best"

        app.dl.set_quality(chosen_fmt, chosen_qual)

        # Klasörü güncelle (değiştirildiyse)
        new_dir = _chosen_dir[0]
        if new_dir and new_dir != current_dir:
            os.makedirs(new_dir, exist_ok=True)
            app.dl.dl_dir = new_dir

        app._save_dl_settings()
        qual_disp = f"{chosen_qual} kbps" if chosen_qual != "best" else t("downloads.best_quality")
        app.sig.notify.emit(f"{chosen_fmt.upper()} - {qual_disp}")
        dlg.accept()

    save_btn.clicked.connect(_save)
    btn_row.addWidget(cancel_btn)
    btn_row.addWidget(save_btn)
    vl.addLayout(btn_row)

    dlg.exec()
