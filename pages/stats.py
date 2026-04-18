"""İstatistikler sayfası."""



from datetime import datetime, timedelta

from collections import defaultdict

from PySide6.QtWidgets import (

    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QScrollArea,

    QFrame, QProgressBar, QSizePolicy

)

from PySide6.QtCore import Qt, QTimer, QSize, QRect

from PySide6.QtGui import QColor, QPainter, QFont, QLinearGradient, QBrush, QCursor, QPen



from core.constants import (

    BG_BLACK, BG_CARD, BG_CARD_HOVER, BG_ELEVATED, BORDER_COLOR,

    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED

)

from utils.helpers import create_icon

from ui.widgets import ClickableFrame, TrackCoverWidget

from pages.common import _build_page_header


def _stats_truncate(text: str, limit: int) -> str:

    clean = str(text or "")

    return clean[:limit] + ("..." if len(clean) > limit else "")


def _stats_color_dot(color: str, size: int = 8) -> QFrame:

    dot = QFrame()

    dot.setFixedSize(size, size)

    dot.setStyleSheet(

        f"background:{color}; border:none; border-radius:{max(1, size // 2)}px;"

    )

    return dot





# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

# WRAPPED â€” Günlük aktivite ısı haritası (son 30 gün)

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€



class _DailyHeatmap(QWidget):

    """Son 30 günün günlük dinleme sürelerini hücre ısı haritasıyla gösterir."""



    def __init__(self, daily_minutes: dict, accent: str, parent=None):

        super().__init__(parent)

        self._data   = daily_minutes   # {date_str: minutes}

        self._accent = accent

        self._prog   = 0.0

        self._timer  = QTimer(self)

        self._timer.timeout.connect(self._tick)

        self._timer.start(16)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.setFixedHeight(72)



    def _tick(self):

        self._prog = min(self._prog + 0.04, 1.0)

        self.update()

        if self._prog >= 1.0:

            self._timer.stop()



    def paintEvent(self, _):

        if not self._data:

            return

        p  = QPainter(self)

        p.setRenderHint(QPainter.Antialiasing)



        today   = datetime.now().date()

        days    = 30

        cell_w  = max(8, (self.width() - (days - 1) * 4) // days)

        cell_h  = 40

        gap     = 4

        max_v   = max(self._data.values(), default=1) or 1

        acc     = QColor(self._accent)



        for i in range(days):

            d     = today - timedelta(days=days - 1 - i)

            key   = d.isoformat()

            val   = self._data.get(key, 0)

            ratio = (val / max_v) * self._prog

            x     = i * (cell_w + gap)

            y     = self.height() - int(cell_h * max(ratio, 0.08)) - 18



            # Hücre rengi: boÅŸ â†’ koyu; dolu â†’ accent

            alpha = max(30, int(200 * ratio))

            color = QColor(acc)

            color.setAlpha(alpha)

            p.setBrush(color)

            p.setPen(Qt.NoPen)

            p.drawRoundedRect(x, y, cell_w, int(cell_h * max(ratio, 0.08)), 3, 3)



            # Bugün iÅŸareti

            if d == today:

                p.setPen(QPen(QColor(acc), 1.5))

                p.setBrush(Qt.NoBrush)

                p.drawRoundedRect(x - 1, y - 1, cell_w + 2, int(cell_h * max(ratio, 0.08)) + 2, 3, 3)

                p.setPen(Qt.NoPen)



        # Eksen etiketleri (her 7 günde bir tarih)

        p.setPen(QColor(TEXT_MUTED))

        f = QFont()

        f.setPointSize(8)

        p.setFont(f)

        for i in range(0, days, 7):

            d = today - timedelta(days=days - 1 - i)

            x = i * (cell_w + gap)

            p.drawText(x, self.height() - 2, d.strftime("%d/%m"))



        p.end()





def _fmt_hours_minutes(total_min: int, app=None) -> str:

    total_min = max(0, int(total_min))

    hours = total_min // 60

    minutes = total_min % 60

    if app is not None and hasattr(app, "_tr"):

        try:

            return app._tr("stats.time.hours_minutes", hours=hours, minutes=minutes)

        except Exception:

            pass

    return f"{hours}s {minutes}dk"





def _stats_plays_text(app, count: int) -> str:

    if app is not None and hasattr(app, "_tr"):

        try:

            return app._tr("stats.count.plays", count=count)

        except Exception:

            pass

    return f"{count} dinleme"





def _stats_primary_accent() -> str:

    return "#6EA8FF"





def _stats_blue_palette(acc: str) -> list[str]:

    return [acc, "#84BCFF", "#93B5FF", "#9FD0FF", "#4B6FB0"]





def _qss_rgba(color: str, alpha: int) -> str:

    qcolor = QColor(color)

    if not qcolor.isValid():

        return color

    return f"rgba({qcolor.red()}, {qcolor.green()}, {qcolor.blue()}, {max(0, min(255, int(alpha)))})"





def _make_summary_chip(label: str, value: str, icon_name: str, tone: str, detail: str = ""):

    chip = QFrame()

    chip.setObjectName("StatsSummaryChip")

    chip.setStyleSheet(f"""

        QFrame#StatsSummaryChip {{

            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,

                stop:0 {_qss_rgba(tone, 24)}, stop:1 {BG_CARD});

            border-radius: 18px;

            border: 1px solid {_qss_rgba(tone, 66)};

        }}

        QFrame#StatsSummaryChip QLabel {{

            background: transparent;

            border: none;

        }}

    """)

    chip_l = QVBoxLayout(chip)

    chip_l.setContentsMargins(16, 14, 16, 14)

    chip_l.setSpacing(6)



    top_row = QHBoxLayout()

    top_row.setContentsMargins(0, 0, 0, 0)

    top_row.setSpacing(8)



    icon_wrap = QFrame()

    icon_wrap.setFixedSize(30, 30)

    icon_wrap.setStyleSheet(

        f"background:{_qss_rgba(tone, 38)}; border-radius:15px; border:1px solid {_qss_rgba(tone, 64)};"

    )

    icon_l = QHBoxLayout(icon_wrap)

    icon_l.setContentsMargins(0, 0, 0, 0)

    icon_lbl = QLabel()

    icon_lbl.setPixmap(create_icon(icon_name, tone, 16).pixmap(16, 16))

    icon_lbl.setFixedSize(16, 16)

    icon_l.addWidget(icon_lbl, 0, Qt.AlignCenter)



    top_row.addWidget(icon_wrap, 0, Qt.AlignLeft)

    top_row.addStretch(1)

    chip_l.addLayout(top_row)



    val_lbl = QLabel(value)

    val_lbl.setWordWrap(True)

    val_lbl.setStyleSheet(

        f"font-size:15px; font-weight:900; color:{TEXT_PRIMARY};"

    )

    lbl_lbl = QLabel(label)

    lbl_lbl.setStyleSheet(

        f"font-size:10px; font-weight:700; color:{tone}; "

        f"letter-spacing:0.8px; text-transform:uppercase;"

    )

    chip_l.addWidget(val_lbl)

    chip_l.addWidget(lbl_lbl)



    if detail:

        detail_lbl = QLabel(detail)

        detail_lbl.setWordWrap(True)

        detail_lbl.setStyleSheet(

            f"font-size:11px; color:{TEXT_MUTED}; line-height:1.4;"

        )

        chip_l.addWidget(detail_lbl)



    return chip





def _make_stats_panel(app, title: str, subtitle: str, acc: str, icon_name: str = "music", tone: str | None = None):

    tone = tone or acc

    panel = QFrame()

    panel.setObjectName("StatsPanel")

    panel.setStyleSheet(f"""

        QFrame#StatsPanel {{

            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,

                stop:0 rgba(255,255,255,0.028), stop:0.55 {BG_CARD}, stop:1 {BG_ELEVATED});

            border-radius: 26px;

            border: 1px solid {BORDER_COLOR};

        }}

        QFrame#StatsPanel QLabel {{

            background: transparent;

            border: none;

        }}

    """)

    app._add_soft_shadow(panel, 26, QColor(0, 0, 0, 88), 0, 10)



    panel_l = QVBoxLayout(panel)

    panel_l.setContentsMargins(24, 22, 24, 22)

    panel_l.setSpacing(0)



    head = QHBoxLayout()

    head.setContentsMargins(0, 0, 0, 0)

    head.setSpacing(12)



    icon_wrap = QFrame()

    icon_wrap.setFixedSize(40, 40)

    icon_wrap.setStyleSheet(

        f"background:{_qss_rgba(tone, 32)}; border-radius:20px; border:1px solid {_qss_rgba(tone, 64)};"

    )

    icon_l = QHBoxLayout(icon_wrap)

    icon_l.setContentsMargins(0, 0, 0, 0)

    icon_lbl = QLabel()

    icon_lbl.setPixmap(create_icon(icon_name, tone, 18).pixmap(18, 18))

    icon_lbl.setFixedSize(18, 18)

    icon_l.addWidget(icon_lbl, 0, Qt.AlignCenter)



    titles = QVBoxLayout()

    titles.setSpacing(3)

    title_lbl = QLabel(title)

    title_lbl.setStyleSheet(

        f"font-size:18px; font-weight:900; color:{TEXT_PRIMARY};"

    )

    sub_lbl = QLabel(subtitle)

    sub_lbl.setWordWrap(True)

    sub_lbl.setStyleSheet(

        f"font-size:12px; color:{TEXT_SECONDARY}; line-height:1.5;"

    )

    titles.addWidget(title_lbl)

    titles.addWidget(sub_lbl)



    head.addWidget(icon_wrap, 0, Qt.AlignTop)

    head.addLayout(titles, 1)

    panel_l.addLayout(head)

    panel_l.addSpacing(18)



    body = QVBoxLayout()

    body.setContentsMargins(0, 0, 0, 0)

    body.setSpacing(14)

    panel_l.addLayout(body)

    return panel, body



class _MiniBarChart(QWidget):
    """Basit yatay çubuk grafik â€” üst N ÅŸarkıyı vurgular."""



    def __init__(self, items, accent, parent=None):

        """

        items: [(label, value), ...]  â€” büyükten küçüÄŸe sıralı

        accent: hex renk kodu

        """

        super().__init__(parent)

        self._items  = items[:8]

        self._accent = accent

        self._max    = max((v for _, v in self._items), default=1) or 1

        self._progress = 0.0

        self._timer  = QTimer(self)

        self._timer.timeout.connect(self._tick)

        self._timer.start(18)

        from PySide6.QtWidgets import QSizePolicy

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        row_h = 36

        self.setFixedHeight(len(self._items) * row_h + 8)



    def _tick(self):

        self._progress = min(self._progress + 0.045, 1.0)

        self.update()

        if self._progress >= 1.0:

            self._timer.stop()



    def paintEvent(self, _):

        if not self._items:

            return

        p = QPainter(self)

        p.setRenderHint(QPainter.Antialiasing)



        w, h    = self.width(), self.height()

        row_h   = h // max(len(self._items), 1)

        acc     = QColor(self._accent)

        lbl_w   = 140

        bar_gap = 8

        bar_x   = lbl_w + bar_gap

        bar_w   = w - bar_x - 60



        for i, (label, value) in enumerate(self._items):

            y = i * row_h

            cy = y + row_h // 2



            p.setPen(QColor(TEXT_PRIMARY if i < 3 else TEXT_SECONDARY))

            font = QFont()

            font.setPointSize(10)

            font.setBold(i < 3)

            p.setFont(font)

            p.drawText(0, y + 4, lbl_w - 8, row_h - 8,

                       Qt.AlignVCenter | Qt.AlignLeft | Qt.TextWordWrap,

                       label[:22] + ("â€¦" if len(label) > 22 else ""))



            p.setPen(Qt.NoPen)

            p.setBrush(QColor(30, 36, 54))

            bg_h = 8

            p.drawRoundedRect(bar_x, cy - bg_h // 2,

                              bar_w, bg_h, 4, 4)



            ratio  = (value / self._max) * self._progress

            fill_w = max(8, int(bar_w * ratio))



            grad = QLinearGradient(bar_x, 0, bar_x + fill_w, 0)

            grad.setColorAt(0.0, acc)

            lighter = acc.lighter(160)

            lighter.setAlpha(220)

            grad.setColorAt(1.0, lighter)

            p.setBrush(QBrush(grad))

            p.drawRoundedRect(bar_x, cy - bg_h // 2, fill_w, bg_h, 4, 4)



            p.setPen(QColor(acc) if i == 0 else QColor(TEXT_MUTED))

            font2 = QFont()

            font2.setPointSize(10)

            font2.setBold(True)

            p.setFont(font2)

            p.drawText(bar_x + bar_w + 6, y + 4,

                       52, row_h - 8,

                       Qt.AlignVCenter | Qt.AlignRight,

                       f"{int(value * self._progress)}×")

        p.end()









def _stats_period_text(stats: dict, app=None) -> tuple[str, str]:

    raw = str((stats or {}).get("period_start", "")).strip()

    try:

        started_at = datetime.fromisoformat(raw)

    except Exception:

        started_at = datetime.now()



    now = datetime.now(started_at.tzinfo) if started_at.tzinfo else datetime.now()

    delta = max(now - started_at, now - now)

    total_seconds = max(0, int(delta.total_seconds()))

    days = total_seconds // 86400

    hours = (total_seconds % 86400) // 3600



    if days > 0:

        span_text = app._tr("stats.period.days", count=days) if app is not None and hasattr(app, "_tr") else f"{days} gündür"

    elif hours > 0:

        span_text = app._tr("stats.period.hours", count=hours) if app is not None and hasattr(app, "_tr") else f"{hours} saattir"

    else:

        span_text = app._tr("stats.period.today") if app is not None and hasattr(app, "_tr") else "bugün baÅŸladı"



    return started_at.strftime("%d.%m.%Y %H:%M"), span_text









def _make_section_caption(title: str, subtitle: str = ""):

    wrap = QWidget()

    wrap.setStyleSheet("background:transparent;")

    wrap_l = QVBoxLayout(wrap)

    wrap_l.setContentsMargins(0, 0, 0, 0)

    wrap_l.setSpacing(4)



    title_lbl = QLabel(title)

    title_lbl.setStyleSheet(

        f"font-size:14px; font-weight:800; color:{TEXT_PRIMARY};"

    )

    wrap_l.addWidget(title_lbl)



    if subtitle:

        subtitle_lbl = QLabel(subtitle)

        subtitle_lbl.setWordWrap(True)

        subtitle_lbl.setStyleSheet(

            f"font-size:11px; color:{TEXT_SECONDARY}; line-height:1.45;"

        )

        wrap_l.addWidget(subtitle_lbl)



    return wrap





def _make_animated_stat_card(

    app,

    label,

    value_str,

    num_value,

    format_fn,

    acc,

    icon_name="music",

    tone=None,

):

    """Sayaç animasyonlu istatistik kartı."""

    tone = tone or acc

    card = QFrame()

    card.setObjectName("StatsCardV2")

    card.setStyleSheet(f"""

        QFrame#StatsCardV2 {{

            background: qlineargradient(x1:0,y1:0,x2:1,y2:1,

                stop:0 {_qss_rgba(tone, 18)}, stop:0.48 {BG_CARD}, stop:1 {BG_ELEVATED});

            border-radius: 22px;

            border: 1px solid {BORDER_COLOR};

        }}

        QFrame#StatsCardV2:hover {{

            border-color: {_qss_rgba(tone, 85)};

            background: qlineargradient(x1:0,y1:0,x2:1,y2:1,

                stop:0 {_qss_rgba(tone, 24)}, stop:0.48 {BG_CARD_HOVER}, stop:1 {BG_ELEVATED});

        }}

    """)

    app._add_soft_shadow(card, 22, QColor(0, 0, 0, 82), 0, 8)



    cl = QVBoxLayout(card)

    cl.setContentsMargins(20, 18, 20, 18)

    cl.setSpacing(10)



    top = QHBoxLayout()

    top.setContentsMargins(0, 0, 0, 0)



    icon_wrap = QFrame()

    icon_wrap.setFixedSize(34, 34)

    icon_wrap.setStyleSheet(

        f"background:{_qss_rgba(tone, 34)}; border-radius:17px; border:1px solid {_qss_rgba(tone, 64)};"

    )

    icon_l = QHBoxLayout(icon_wrap)

    icon_l.setContentsMargins(0, 0, 0, 0)

    icon_lbl = QLabel()

    icon_lbl.setPixmap(create_icon(icon_name, tone, 16).pixmap(16, 16))

    icon_lbl.setFixedSize(16, 16)

    icon_l.addWidget(icon_lbl, 0, Qt.AlignCenter)



    tag_lbl = QLabel(app._tr("stats.tag.featured"))

    tag_lbl.setStyleSheet(

        f"font-size:10px; font-weight:700; color:{tone}; "

        f"letter-spacing:1px; background:transparent;"

    )



    top.addWidget(icon_wrap, 0, Qt.AlignLeft)

    top.addSpacing(8)

    top.addWidget(tag_lbl, 0, Qt.AlignVCenter)

    top.addStretch(1)

    cl.addLayout(top)



    value_lbl = QLabel("0")

    value_lbl.setStyleSheet(

        f"font-size:32px; font-weight:900; color:{TEXT_PRIMARY}; background:transparent;"

    )

    label_lbl = QLabel(label)

    label_lbl.setStyleSheet(

        f"font-size:11px; font-weight:700; color:{TEXT_MUTED}; "

        f"letter-spacing:1.2px; text-transform:uppercase; background:transparent;"

    )



    cl.addWidget(value_lbl)

    cl.addWidget(label_lbl)



    if num_value > 0:

        steps = 28

        dur_ms = 900

        interval = max(18, dur_ms // steps)

        counter = [0]

        timer = QTimer(card)



        def _tick(t=timer, c=counter, lbl=value_lbl, n=num_value, fmt=format_fn, tgt=value_str):

            c[0] = min(c[0] + max(1, n // steps), n)

            lbl.setText(fmt(c[0]))

            if c[0] >= n:

                t.stop()

                lbl.setText(tgt)



        timer.timeout.connect(_tick)

        timer.start(interval)

        card._anim_timer = timer

    else:

        value_lbl.setText(value_str)



    return card





def _build_wrapped_section(app, vl, stats: dict, hist_map: dict, acc: str, show_header: bool = True):

    """Wrapped bölümü: özet kartlar + günlük aktivite ısı haritası."""

    t = app._tr

    if show_header:

        wrapped_title = QLabel(t("stats.wrapped.title"))

        wrapped_title.setStyleSheet(

            f"font-size:20px; font-weight:900; color:{TEXT_PRIMARY}; "

            f"margin-bottom:6px; background:transparent;"

        )

        wrapped_sub = QLabel(t("stats.wrapped.subtitle"))

        wrapped_sub.setWordWrap(True)

        wrapped_sub.setStyleSheet(

            f"font-size:12px; color:{TEXT_SECONDARY}; margin-bottom:14px; background:transparent;"

        )

        vl.addWidget(wrapped_title)

        vl.addWidget(wrapped_sub)



    plays_map = stats.get("play_count", {})

    total_ms = stats.get("total_ms", 0)

    total_min = total_ms // 60_000

    period_start_raw = str(stats.get("period_start", "")).strip()

    try:

        period_start = datetime.fromisoformat(period_start_raw)

    except Exception:

        period_start = datetime.now() - timedelta(days=30)



    now = datetime.now(period_start.tzinfo) if period_start.tzinfo else datetime.now()

    days_active = max(1, (now - period_start).days + 1)



    artist_plays: dict[str, int] = defaultdict(int)

    for vid, cnt in plays_map.items():

        track = hist_map.get(vid)

        if track:

            artist_name = app._artist_str(track)

            if artist_name and artist_name != "?":

                artist_plays[artist_name] += cnt

    top_artist = max(artist_plays, key=artist_plays.get) if artist_plays else "â€”"

    top_artist_plays = artist_plays.get(top_artist, 0)



    id_count = sorted(plays_map.items(), key=lambda x: x[1], reverse=True)

    top_song = hist_map.get(id_count[0][0], {}).get("title", "â€”") if id_count else "â€”"

    top_song_cnt = id_count[0][1] if id_count else 0

    avg_min = total_min // days_active



    wrapped_cards = QWidget()

    wrapped_cards.setStyleSheet("background:transparent;")

    wc_l = QGridLayout(wrapped_cards)

    wc_l.setContentsMargins(0, 0, 0, 0)

    wc_l.setHorizontalSpacing(12)

    wc_l.setVerticalSpacing(12)

    wc_l.setColumnStretch(0, 1)

    wc_l.setColumnStretch(1, 1)



    palette = _stats_blue_palette(acc)

    cards = [

        _make_summary_chip(

            t("stats.wrapped.loyal_artist"),

            top_artist[:28] + ("â€¦" if len(top_artist) > 28 else ""),

            "music",

            palette[0],

            t("stats.wrapped.loyal_artist_detail", count=top_artist_plays),

        ),

        _make_summary_chip(

            t("stats.wrapped.repeat_favorite"),

            top_song[:28] + ("â€¦" if len(top_song) > 28 else ""),

            "queue",

            palette[1],

            t("stats.wrapped.repeat_favorite_detail", count=top_song_cnt),

        ),

        _make_summary_chip(

            t("stats.wrapped.daily_average"),

            _fmt_hours_minutes(avg_min, app),

            "timer",

            palette[2],

            t("stats.wrapped.daily_average_detail", count=days_active),

        ),

        _make_summary_chip(

            t("stats.wrapped.total_time"),

            _fmt_hours_minutes(total_min, app),

            "headphone",

            palette[3],

            t("stats.wrapped.total_time_detail", count=sum(plays_map.values())),

        ),

    ]

    for idx, card in enumerate(cards):

        wc_l.addWidget(card, idx // 2, idx % 2)



    vl.addWidget(wrapped_cards)

    vl.addSpacing(12)

    vl.addWidget(_make_section_caption(

        t("stats.wrapped.heatmap_title"),

        t("stats.wrapped.heatmap_subtitle"),

    ))



    daily_minutes: dict[str, float] = defaultdict(float)

    daily_ms_raw = stats.get("daily_ms", {})
    if daily_ms_raw:
        for date_str, ms in daily_ms_raw.items():
            daily_minutes[date_str] = ms / 60_000
    else:
        for track in hist_map.values():
            added = track.get("added_at") or track.get("played_at") or ""
            if added:
                try:
                    key = datetime.fromisoformat(str(added)).date().isoformat()
                    cnt = plays_map.get(track.get("videoId", ""), 1)

                    daily_minutes[key] += cnt * 3.0

                except Exception:

                    pass



    heatmap_frame = QFrame()

    heatmap_frame.setObjectName("HeatmapFrameV2")

    heatmap_frame.setStyleSheet(f"""

        QFrame#HeatmapFrameV2 {{

            background: qlineargradient(x1:0,y1:0,x2:1,y2:1,

                stop:0 rgba(255,255,255,0.015), stop:1 {BG_CARD});

            border-radius: 18px;

            border: 1px solid {BORDER_COLOR};

        }}

    """)

    hf_l = QVBoxLayout(heatmap_frame)

    hf_l.setContentsMargins(16, 14, 16, 14)

    hf_l.setSpacing(10)



    legend = QLabel(t("stats.wrapped.legend"))

    legend.setStyleSheet(

        f"font-size:11px; color:{TEXT_MUTED}; background:transparent;"

    )

    hf_l.addWidget(legend)

    hf_l.addWidget(_DailyHeatmap(dict(daily_minutes), acc))



    vl.addWidget(heatmap_frame)





def _build_stats_hero(

    app,

    acc: str,

    start_text: str,

    span_text: str,

    total_min: int,

    total_plays: int,

    favorites_count: int,

    playlists_count: int,

    top_artist: str,

    top_artist_plays: int,

    top_song: str,

    top_song_cnt: int,

    avg_min: int,

):

    t = app._tr

    hero, body = _make_stats_panel(

        app,

        t("stats.hero.title"),

        t("stats.hero.subtitle", start=start_text, span=span_text),

        acc,

        icon_name="headphone",

        tone=acc,

    )



    value_lbl = QLabel(_fmt_hours_minutes(total_min, app))

    value_lbl.setStyleSheet(

        f"font-size:48px; font-weight:950; color:{TEXT_PRIMARY}; letter-spacing:-1px;"

    )

    desc_lbl = QLabel(

        t(

            "stats.hero.description",

            plays=total_plays,

            favorites=favorites_count,

            playlists=playlists_count,

            artist=top_artist,

        )

    )

    desc_lbl.setWordWrap(True)

    desc_lbl.setStyleSheet(

        f"font-size:13px; color:{TEXT_SECONDARY}; line-height:1.6;"

    )

    body.addWidget(value_lbl)

    body.addWidget(desc_lbl)

    body.addSpacing(6)



    chips_wrap = QWidget()

    chips_wrap.setStyleSheet("background:transparent;")

    chips_l = QGridLayout(chips_wrap)

    chips_l.setContentsMargins(0, 0, 0, 0)

    chips_l.setHorizontalSpacing(12)

    chips_l.setVerticalSpacing(12)



    hero_cards = [

        _make_summary_chip(

            t("stats.hero.loyal_artist"),

            top_artist[:26] + ("â€¦" if len(top_artist) > 26 else ""),

            "music",

            "#6FA8FF",

            t("stats.hero.loyal_artist_detail", count=top_artist_plays),

        ),

        _make_summary_chip(

            t("stats.hero.repeat_favorite"),

            top_song[:26] + ("â€¦" if len(top_song) > 26 else ""),

            "queue",

            "#82C6FF",

            t("stats.hero.repeat_favorite_detail", count=top_song_cnt),

        ),

        _make_summary_chip(

            t("stats.hero.daily_pace"),

            _fmt_hours_minutes(avg_min, app),

            "timer",

            "#95B8FF",

            t("stats.hero.daily_pace_detail"),

        ),

    ]

    compact = _is_stats_compact(app)

    if compact:

        chips_l.setColumnStretch(0, 1)

        chips_l.setColumnStretch(1, 1)

        if len(hero_cards) >= 3:

            chips_l.addWidget(hero_cards[0], 0, 0)

            chips_l.addWidget(hero_cards[1], 0, 1)

            chips_l.addWidget(hero_cards[2], 1, 0, 1, 2)

        else:

            for idx, card in enumerate(hero_cards):

                chips_l.addWidget(card, idx, 0, 1, 2)

    else:

        for col in range(3):

            chips_l.setColumnStretch(col, 1)

        for idx, card in enumerate(hero_cards):

            chips_l.addWidget(card, 0, idx)



    body.addWidget(chips_wrap)

    return hero





def _build_artist_spotlight_map(app, plays_map: dict, hist_map: dict, top_artists):

    spotlight: dict[str, tuple[dict, int]] = {}

    targets = {artist for artist, _ in top_artists}

    for vid, cnt in plays_map.items():

        track = hist_map.get(vid)

        if not track:

            continue

        artist_name = app._artist_str(track)

        if artist_name not in targets:

            continue

        prev = spotlight.get(artist_name)

        if prev is None or cnt > prev[1]:

            spotlight[artist_name] = (track, cnt)

    return spotlight





def _build_artist_podium(app, top_artists, artist_spotlights: dict, acc: str):

    wrap = QWidget()

    wrap.setStyleSheet("background:transparent;")

    t = app._tr

    compact = _is_stats_compact(app)

    if compact:

        layout = QVBoxLayout(wrap)

    else:

        layout = QHBoxLayout(wrap)

    layout.setContentsMargins(0, 0, 0, 0)

    layout.setSpacing(12)



    palette = _stats_blue_palette(acc)

    podium_order = [1, 0, 2] if len(top_artists) >= 3 and not compact else list(range(min(3, len(top_artists))))

    heights = {0: 156, 1: 188, 2: 144}



    for display_idx, artist_idx in enumerate(podium_order):

        if artist_idx >= len(top_artists):

            continue

        artist, plays = top_artists[artist_idx]

        tone = palette[min(artist_idx, len(palette) - 1)]

        rank = artist_idx + 1



        card = QFrame()

        card.setObjectName("StatsPodiumCard")

        card.setMinimumHeight(heights.get(rank - 1, 150) if not compact else 128)

        card.setStyleSheet(f"""

            QFrame#StatsPodiumCard {{

                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,

                    stop:0 {_qss_rgba(tone, 22)}, stop:0.6 {BG_CARD}, stop:1 {BG_ELEVATED});

                border-radius: 22px;

                border: 1px solid {_qss_rgba(tone, 64)};

            }}

            QFrame#StatsPodiumCard QLabel {{

                background: transparent;

                border: none;

            }}

        """)

        app._add_soft_shadow(card, 18, QColor(0, 0, 0, 72), 0, 6)



        card_l = QVBoxLayout(card)

        card_l.setContentsMargins(18, 16, 18, 16)

        card_l.setSpacing(8)



        badge = QLabel(f"#{rank}")

        badge.setFixedWidth(34)

        badge.setAlignment(Qt.AlignCenter)

        badge.setStyleSheet(

            f"background:{_qss_rgba(tone, 34)}; color:{tone}; border-radius:11px; "

            f"padding:4px 0; font-size:11px; font-weight:900;"

        )



        icon = QLabel()

        icon.setPixmap(create_icon("music", tone, 18).pixmap(18, 18))

        icon.setFixedSize(18, 18)



        top_row = QHBoxLayout()

        top_row.setContentsMargins(0, 0, 0, 0)

        top_row.addWidget(badge, 0, Qt.AlignLeft)

        top_row.addStretch(1)

        top_row.addWidget(icon, 0, Qt.AlignRight)



        title = QLabel(artist[:26] + ("â€¦" if len(artist) > 26 else ""))

        title.setWordWrap(True)

        title.setStyleSheet(

            f"font-size:{'16' if rank == 1 else '14'}px; font-weight:900; color:{TEXT_PRIMARY};"

        )

        meta = QLabel(_stats_plays_text(app, plays))

        meta.setStyleSheet(

            f"font-size:12px; font-weight:700; color:{tone};"

        )

        spotlight_track, _spotlight_count = artist_spotlights.get(artist, (None, 0))

        media_row = QHBoxLayout()

        media_row.setContentsMargins(0, 0, 0, 0)

        media_row.setSpacing(10)



        art = QLabel()

        art.setFixedSize(44, 44)

        art.setAlignment(Qt.AlignCenter)

        art.setStyleSheet(

            f"background:{BG_ELEVATED}; border-radius:12px; border:1px solid {_qss_rgba(tone, 51)};"

        )

        if spotlight_track:

            thumb = app._thumb(spotlight_track, big=False)

            if thumb:

                app._load_image(thumb, art, (44, 44))

            else:

                art.setPixmap(create_icon("music", tone, 20).pixmap(20, 20))

        else:

            art.setPixmap(create_icon("music", tone, 20).pixmap(20, 20))



        media_text = QVBoxLayout()

        media_text.setSpacing(2)

        if spotlight_track:

            raw_media_title = str(spotlight_track.get("title") or t("stats.podium.default_track"))

            media_title_text = raw_media_title[:22] + ("â€¦" if len(raw_media_title) > 22 else "")

        else:

            media_title_text = t("stats.podium.default_track")

        media_title = QLabel(media_title_text)

        media_title.setStyleSheet(

            f"font-size:11px; font-weight:700; color:{TEXT_PRIMARY};"

        )

        media_label = QLabel(t("stats.podium.highlight_track"))

        media_label.setStyleSheet(

            f"font-size:10px; color:{TEXT_MUTED};"

        )

        media_text.addWidget(media_title)

        media_text.addWidget(media_label)

        media_row.addWidget(art)

        media_row.addLayout(media_text, 1)



        hint = QLabel(t("stats.podium.hint"))

        hint.setWordWrap(True)

        hint.setStyleSheet(

            f"font-size:11px; color:{TEXT_MUTED}; line-height:1.4;"

        )



        card_l.addLayout(top_row)

        card_l.addStretch(1)

        card_l.addWidget(title)

        card_l.addWidget(meta)

        card_l.addLayout(media_row)

        card_l.addWidget(hint)



        if compact:

            layout.addWidget(card)

        else:

            stretch = 5 if rank == 1 else 4

            layout.addWidget(card, stretch)



    return wrap





def _build_quick_insights_panel(app, bar_items, top_artists, artist_spotlights: dict, acc: str):

    t = app._tr

    panel, body = _make_stats_panel(

        app,

        t("stats.quick.title"),

        t("stats.quick.subtitle"),

        acc,

        icon_name="queue",

        tone="#6FA8FF",

    )



    if top_artists:

        body.addWidget(_make_section_caption(

            t("stats.quick.podium_title"),

            t("stats.quick.podium_subtitle"),

        ))

        body.addWidget(_build_artist_podium(app, top_artists[:3], artist_spotlights, acc))

        body.addSpacing(4)



    if bar_items:

        body.addWidget(_make_section_caption(

            t("stats.quick.top_tracks_title"),

            t("stats.quick.top_tracks_subtitle"),

        ))

        chart_wrap = QFrame()

        chart_wrap.setObjectName("StatsInnerBlock")

        chart_wrap.setStyleSheet(f"""

            QFrame#StatsInnerBlock {{

                background: rgba(255,255,255,0.02);

                border-radius: 18px;

                border: 1px solid {BORDER_COLOR};

            }}

        """)

        chart_l = QVBoxLayout(chart_wrap)

        chart_l.setContentsMargins(18, 16, 18, 16)

        chart_l.addWidget(_MiniBarChart(bar_items, acc))

        body.addWidget(chart_wrap)

    else:

        empty = QLabel(t("stats.quick.empty_chart"))

        empty.setWordWrap(True)

        empty.setStyleSheet(f"color:{TEXT_MUTED}; font-size:13px;")

        body.addWidget(empty)



    body.addSpacing(4)

    body.addWidget(_make_section_caption(

        t("stats.quick.top_artists_title"),

        t("stats.quick.top_artists_subtitle"),

    ))



    if top_artists:

        artist_wrap = QFrame()

        artist_wrap.setObjectName("StatsArtistWrap")

        artist_wrap.setStyleSheet(f"""

            QFrame#StatsArtistWrap {{

                background: rgba(255,255,255,0.02);

                border-radius: 18px;

                border: 1px solid {BORDER_COLOR};

            }}

        """)

        artist_l = QVBoxLayout(artist_wrap)

        artist_l.setContentsMargins(18, 16, 18, 16)

        artist_l.setSpacing(12)



        max_plays = top_artists[0][1] if top_artists else 1

        colors = _stats_blue_palette(acc)



        for idx, (artist, plays) in enumerate(top_artists):

            row = QHBoxLayout()

            row.setSpacing(12)



            rank = QLabel(f"#{idx + 1}")

            rank.setFixedWidth(30)

            rank.setAlignment(Qt.AlignCenter)

            rank.setStyleSheet(

                f"color:{colors[idx % len(colors)]}; font-weight:900; font-size:14px;"

            )



            text_wrap = QVBoxLayout()

            text_wrap.setSpacing(2)

            name = QLabel(artist[:30] + ("â€¦" if len(artist) > 30 else ""))

            name.setStyleSheet(

                f"color:{TEXT_PRIMARY}; font-weight:{'800' if idx == 0 else '700'}; font-size:13px;"

            )

            meta = QLabel(_stats_plays_text(app, plays))

            meta.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11px;")

            text_wrap.addWidget(name)

            text_wrap.addWidget(meta)



            bar = QProgressBar()

            bar.setRange(0, max_plays)

            bar.setValue(0)

            bar.setFixedHeight(8)

            color = colors[idx % len(colors)]

            bar.setStyleSheet(

                f"QProgressBar{{background:{BG_ELEVATED}; border-radius:4px; border:none;}}"

                f"QProgressBar::chunk{{background:{color}; border-radius:4px;}}"

            )



            bar_steps = 25

            bar_timer = QTimer(artist_wrap)

            bar_current = [0]

            target_val = plays



            def _bar_tick(t=bar_timer, current=bar_current, target=target_val, widget=bar, steps=bar_steps):

                current[0] = min(current[0] + max(1, target // steps), target)

                widget.setValue(current[0])

                if current[0] >= target:

                    t.stop()



            bar_timer.timeout.connect(_bar_tick)

            bar_timer.start(28)



            value = QLabel(f"{plays}×")

            value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

            value.setStyleSheet(

                f"color:{color}; font-size:12px; font-weight:800; min-width:44px;"

            )



            row.addWidget(rank)

            row.addLayout(text_wrap, 0)

            row.addWidget(bar, 1)

            row.addWidget(value)

            artist_l.addLayout(row)



        body.addWidget(artist_wrap)

    else:

        empty = QLabel(t("stats.quick.empty_artists"))

        empty.setWordWrap(True)

        empty.setStyleSheet(f"color:{TEXT_MUTED}; font-size:13px;")

        body.addWidget(empty)



    return panel





def _build_top_tracks_panel(app, id_count, hist_map: dict, acc: str):

    t = app._tr

    panel, body = _make_stats_panel(

        app,

        t("stats.top_tracks.title"),

        t("stats.top_tracks.subtitle"),

        acc,

        icon_name="play",

        tone="#6FA8FF",

    )



    shown = 0

    max_cnt = id_count[0][1] if id_count else 1

    for vid, cnt in id_count[:12]:

        track = hist_map.get(vid)

        if not track:

            continue



        row = ClickableFrame()

        row.setObjectName("StatsTrackRowV2")

        row.setFixedHeight(80)

        row.setStyleSheet(

            f"QFrame#StatsTrackRowV2{{background:{BG_CARD}; border-radius:18px; border:1px solid {BORDER_COLOR};}}"

            f"QFrame#StatsTrackRowV2:hover{{background:{BG_CARD_HOVER}; border-color:{_qss_rgba(acc, 85)};}}"

        )

        app._add_soft_shadow(row, 18, QColor(0, 0, 0, 72), 0, 4)



        row_l = QHBoxLayout(row)

        row_l.setContentsMargins(16, 12, 16, 12)

        row_l.setSpacing(12)



        medal_color = acc if shown == 0 else "#6FA8FF" if shown == 1 else "#95B8FF" if shown == 2 else TEXT_MUTED

        rank = QLabel(f"#{shown + 1}")

        rank.setFixedWidth(42)

        rank.setAlignment(Qt.AlignCenter)

        rank.setStyleSheet(

            f"color:{medal_color}; font-weight:900; font-size:{'18' if shown < 3 else '15'}px;"

        )



        art = QLabel()

        art.setFixedSize(56, 56)

        art.setAlignment(Qt.AlignCenter)

        art.setStyleSheet(

            f"background:{BG_ELEVATED}; border-radius:12px; border:1px solid {_qss_rgba(acc, 34)};"

        )

        thumb = app._thumb(track, big=False)

        if thumb:

            app._load_image(thumb, art, (56, 56))

        else:

            art.setPixmap(create_icon("music", TEXT_MUTED, 24).pixmap(24, 24))



        text_l = QVBoxLayout()

        text_l.setSpacing(3)

        title = QLabel(track.get("title", "?"))

        title.setMaximumWidth(360)

        title.setStyleSheet(

            f"font-size:14px; font-weight:800; color:{TEXT_PRIMARY};"

        )

        artist = QLabel(app._artist_str(track))

        artist.setStyleSheet(f"font-size:12px; color:{TEXT_SECONDARY};")

        text_l.addWidget(title)

        text_l.addWidget(artist)



        right = QVBoxLayout()

        right.setSpacing(4)

        right.setAlignment(Qt.AlignRight | Qt.AlignVCenter)



        count = QLabel(f"{cnt}×")

        count.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        count.setStyleSheet(

            f"font-size:12px; font-weight:800; color:{acc};"

        )



        bar = QProgressBar()

        bar.setRange(0, max_cnt)

        bar.setValue(cnt)

        bar.setFixedSize(92, 5)

        bar.setStyleSheet(

            f"QProgressBar{{background:{BG_ELEVATED}; border-radius:3px; border:none;}}"

            f"QProgressBar::chunk{{background:{acc}; border-radius:3px;}}"

        )

        right.addWidget(count, alignment=Qt.AlignRight)

        right.addWidget(bar, alignment=Qt.AlignRight)



        row_l.addWidget(rank)

        row_l.addWidget(art)

        row_l.addLayout(text_l, 1)

        row_l.addLayout(right)



        row.clicked.connect(lambda t=track: app.force_play(t))

        body.addWidget(row)

        shown += 1



    if shown == 0:

        empty = QLabel(t("stats.top_tracks.empty"))

        empty.setAlignment(Qt.AlignCenter)

        empty.setWordWrap(True)

        empty.setStyleSheet(

            f"color:{TEXT_MUTED}; font-size:15px; margin:26px 0; line-height:1.6;"

        )

        body.addWidget(empty)



    return panel





def _stats_width(app) -> int:

    try:

        width = int(app.width())

    except Exception:

        width = 0

    return width if width > 0 else 1600





def _is_stats_compact(app) -> bool:

    return _stats_width(app) < 1480





# â”€â”€ Saatlik aktivite çubuk grafiÄŸi â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€



class _HourlyBarChart(QWidget):

    """0-23 arası saat dilimlerine göre dinleme aktivitesi çubuÄŸu."""



    def __init__(self, hourly_counts: list, accent: str, parent=None):

        super().__init__(parent)

        self._data   = list(hourly_counts)

        self._accent = accent

        self._prog   = 0.0

        self._timer  = QTimer(self)

        self._timer.timeout.connect(self._tick)

        self._timer.start(16)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.setFixedHeight(115)



    def _tick(self):

        self._prog = min(self._prog + 0.05, 1.0)

        self.update()

        if self._prog >= 1.0:

            self._timer.stop()



    def paintEvent(self, _):

        p = QPainter(self)

        p.setRenderHint(QPainter.Antialiasing)



        n       = 24

        w       = self.width()

        h       = self.height()

        gap     = 4

        label_h = 18

        chart_h = h - label_h

        bar_w   = max(6, (w - gap * (n - 1)) / n)

        max_v   = max(self._data) if any(self._data) else 1



        TIME_COLORS = {

            "night":     "#3A4A70",

            "morning":   "#7EC8FF",

            "afternoon": self._accent,

            "evening":   "#C287FF",

        }



        for i, val in enumerate(self._data):

            ratio = (val / max_v) * self._prog

            x     = int(i * (bar_w + gap))

            if 6 <= i < 12:

                base = TIME_COLORS["morning"]

            elif 12 <= i < 18:

                base = TIME_COLORS["afternoon"]

            elif 18 <= i < 22:

                base = TIME_COLORS["evening"]

            else:

                base = TIME_COLORS["night"]



            bar_h = max(4, int(chart_h * max(ratio, 0.05)))

            y     = chart_h - bar_h

            color = QColor(base)

            color.setAlpha(max(55, int(220 * max(ratio, 0.14))))

            p.setBrush(color)

            p.setPen(Qt.NoPen)

            p.drawRoundedRect(x, y, max(1, int(bar_w)), bar_h, 3, 3)



        p.setPen(QColor(TEXT_MUTED))

        f = QFont()

        f.setPointSize(8)

        p.setFont(f)

        for hr in [0, 6, 12, 18]:

            x = int(hr * (bar_w + gap))

            p.drawText(x, h - 1, 40, label_h, Qt.AlignLeft | Qt.AlignBottom, f"{hr:02d}:00")



        p.end()





# â”€â”€ Halka (donut) grafiÄŸi â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€



class _DonutChart(QWidget):

    """Sanatçı paylarını gösteren animasyonlu halka grafik."""



    SIZE = 130



    def __init__(self, items: list, colors: list, parent=None):

        super().__init__(parent)

        self._items  = items[:5]

        self._colors = colors

        self._prog   = 0.0

        self._timer  = QTimer(self)

        self._timer.timeout.connect(self._tick)

        self._timer.start(16)

        self.setFixedSize(self.SIZE, self.SIZE)



    def _tick(self):

        self._prog = min(self._prog + 0.045, 1.0)

        self.update()

        if self._prog >= 1.0:

            self._timer.stop()



    def paintEvent(self, _):

        if not self._items:

            return

        p     = QPainter(self)

        p.setRenderHint(QPainter.Antialiasing)

        total = sum(v for _, v in self._items) or 1

        mg    = 8

        w, h  = self.width(), self.height()

        rect  = QRect(mg, mg, w - 2 * mg, h - 2 * mg)

        angle = 90 * 16



        for i, (_, val) in enumerate(self._items):

            span  = int((val / total) * 360 * 16 * self._prog)

            color = QColor(self._colors[i % len(self._colors)])

            p.setBrush(color)

            p.setPen(Qt.NoPen)

            p.drawPie(rect, angle, -span)

            angle -= span



        hole = 32

        p.setBrush(QColor(BG_CARD))

        p.setPen(Qt.NoPen)

        p.drawEllipse(hole, hole, w - 2 * hole, h - 2 * hole)

        p.end()





# â”€â”€ Veri hesaplama yardımcıları â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€



def _track_date(track: dict):

    for key in ("added_at", "played_at"):

        raw = track.get(key)

        if raw:

            try:

                return datetime.fromisoformat(str(raw)).date()

            except Exception:

                pass

    return None





def _calc_hourly_counts(history: list) -> list:

    counts = [0] * 24

    for track in history:

        for key in ("added_at", "played_at"):

            raw = track.get(key)

            if raw:

                try:

                    counts[datetime.fromisoformat(str(raw)).hour] += 1

                    break

                except Exception:

                    pass

    return counts





def _calc_streak(history: list) -> int:

    dates = set()

    for track in history:

        d = _track_date(track)

        if d:

            dates.add(d)

    today  = datetime.now().date()

    streak = 0

    cursor = today

    while cursor in dates:

        streak += 1

        cursor -= timedelta(days=1)

    return streak





def _calc_week_comparison(history: list) -> tuple:
    today      = datetime.now().date()
    this_start = today - timedelta(days=6)
    last_start = today - timedelta(days=13)
    this_week  = 0

    last_week  = 0

    for track in history:

        d = _track_date(track)

        if d is None:

            continue

        if d >= this_start:

            this_week += 1
        elif d >= last_start:
            last_week += 1
    return this_week, last_week


def _stats_started_at(stats: dict):
    raw = str((stats or {}).get("period_start", "")).strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except Exception:
        return None


def _period_cutoff(period: str):
    today = datetime.now().date()
    if period == "week":
        return today - timedelta(days=6)
    if period == "month":
        return today - timedelta(days=29)
    return None


def _stamp_history_item(track: dict, played_at: str) -> dict:
    item = dict(track) if isinstance(track, dict) else {}
    if played_at and not item.get("played_at") and not item.get("added_at"):
        item["played_at"] = played_at
    return item


def _build_recent_history(events: list) -> list:
    recent = []
    seen = set()
    for event in events:
        if not isinstance(event, dict):
            continue
        vid = str(event.get("videoId", "") or "").strip()
        if not vid or vid in seen:
            continue
        recent.append(dict(event))
        seen.add(vid)
    return recent


def _filter_daily_ms(daily_ms_raw, cutoff) -> dict:
    filtered = {}
    if not isinstance(daily_ms_raw, dict):
        return filtered
    for date_str, ms in daily_ms_raw.items():
        try:
            day = datetime.fromisoformat(str(date_str)).date()
        except Exception:
            continue
        if day < cutoff:
            continue
        filtered[day.isoformat()] = int(ms or 0)
    return filtered


def _period_stats_start(stats: dict, period: str) -> datetime:
    started_at = _stats_started_at(stats)
    if started_at is None:
        return datetime.now()
    cutoff = _period_cutoff(period)
    if cutoff is None:
        return started_at
    cutoff_dt = datetime.combine(cutoff, datetime.min.time())
    if started_at.tzinfo is not None:
        cutoff_dt = cutoff_dt.replace(tzinfo=started_at.tzinfo)
    return started_at if started_at > cutoff_dt else cutoff_dt


def _filter_stats_by_period(app, period: str) -> tuple:
    """Selected period as (plays_map, filtered_history, total_ms, daily_ms)."""
    stats = app.stats if isinstance(app.stats, dict) else {}
    all_plays = stats.get("play_count", {})
    all_history = app.history if isinstance(app.history, list) else []
    all_ms = int(stats.get("total_ms", 0) or 0)
    all_daily_ms = stats.get("daily_ms", {})

    if period == "all":
        return all_plays, all_history, all_ms, all_daily_ms if isinstance(all_daily_ms, dict) else {}

    cutoff = _period_cutoff(period)
    if cutoff is None:
        return all_plays, all_history, all_ms, {}

    filtered_daily_ms = _filter_daily_ms(all_daily_ms, cutoff)

    filtered_events = []
    filtered_plays = {}
    raw_events = stats.get("listen_events", [])
    if isinstance(raw_events, list):
        for event in raw_events:
            if not isinstance(event, dict):
                continue
            played_date = _track_date(event)
            if played_date is None or played_date < cutoff:
                continue
            vid = str(event.get("videoId", "") or "").strip()
            if not vid:
                continue
            filtered_events.append(dict(event))
            filtered_plays[vid] = filtered_plays.get(vid, 0) + 1

    if filtered_events:
        total_ms = sum(filtered_daily_ms.values())
        if total_ms <= 0:
            total_all = sum(all_plays.values()) or 1
            total_ms = int(all_ms * sum(filtered_plays.values()) / total_all)
        return filtered_plays, _build_recent_history(filtered_events), total_ms, filtered_daily_ms

    filtered_history = [
        dict(track)
        for track in all_history
        if (_track_date(track) or datetime.min.date()) >= cutoff
    ]
    if filtered_history:
        vid_set = {track.get("videoId", "") for track in filtered_history}
        filtered_plays = {vid: cnt for vid, cnt in all_plays.items() if vid in vid_set}
        total_ms = sum(filtered_daily_ms.values())
        if total_ms <= 0:
            total_all = sum(all_plays.values()) or 1
            total_ms = int(all_ms * sum(filtered_plays.values()) / total_all)
        return filtered_plays, filtered_history, total_ms, filtered_daily_ms

    started_at = _stats_started_at(stats)
    if started_at is not None and started_at.date() >= cutoff:
        fallback_stamp = started_at.isoformat(timespec="seconds")
        fallback_history = [_stamp_history_item(track, fallback_stamp) for track in all_history]
        if not filtered_daily_ms and all_ms > 0:
            filtered_daily_ms = {started_at.date().isoformat(): all_ms}
        return all_plays, fallback_history, all_ms, filtered_daily_ms

    return {}, [], 0, filtered_daily_ms




# â”€â”€ Dönem seçici â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€



def _build_period_selector(app, acc: str) -> QWidget:

    wrap = QWidget()

    wrap.setStyleSheet("background:transparent;")

    hl = QHBoxLayout(wrap)

    hl.setContentsMargins(0, 0, 0, 0)

    hl.setSpacing(8)



    t = app._tr

    current = getattr(app, "_stats_period", "all")

    for label, key in [

        (t("stats.period.week"), "week"),

        (t("stats.period.month"), "month"),

        (t("stats.period.all"), "all"),

    ]:

        active = key == current

        btn = QPushButton(label)

        btn.setCursor(Qt.PointingHandCursor)

        btn.setFocusPolicy(Qt.NoFocus)

        if active:

            btn.setStyleSheet(f"""

                QPushButton {{

                    background:{acc}; color:#081018;

                    border:none; border-radius:14px;

                    padding:7px 18px; font-size:12px; font-weight:800;

                }}

            """)

        else:

            btn.setStyleSheet(f"""

                QPushButton {{

                    background:rgba(255,255,255,0.055);

                    color:{TEXT_SECONDARY};

                    border:1px solid {BORDER_COLOR};

                    border-radius:14px; padding:7px 18px;

                    font-size:12px; font-weight:600;

                }}

                QPushButton:hover {{

                    background:rgba(255,255,255,0.10);

                    color:{TEXT_PRIMARY};

                    border-color:{_qss_rgba(acc, 80)};

                }}

            """)



        def _click(checked=False, k=key):

            app._stats_period = k

            app.page_stats()



        btn.clicked.connect(_click)

        hl.addWidget(btn)



    hl.addStretch()

    return wrap





# â”€â”€ Streak + Bu hafta vs geçen hafta satırı â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€



def _build_streak_week_row(app, streak: int, this_week: int, last_week: int, acc: str) -> QWidget:

    wrap = QWidget()

    wrap.setStyleSheet("background:transparent;")

    hl = QHBoxLayout(wrap)

    hl.setContentsMargins(0, 0, 0, 0)

    hl.setSpacing(14)

    t = app._tr



    # â”€â”€ Streak kartı â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    streak_f = QFrame()

    streak_f.setObjectName("StatsStreakCard")

    streak_f.setStyleSheet(f"""

        QFrame#StatsStreakCard {{

            background: qlineargradient(x1:0,y1:0,x2:1,y2:1,

                stop:0 rgba(255,152,0,0.14), stop:1 {BG_CARD});

            border:1px solid rgba(255,152,0,0.32);

            border-radius:22px;

        }}

        QFrame#StatsStreakCard QLabel {{ background:transparent; border:none; }}

    """)

    app._add_soft_shadow(streak_f, 22, QColor(0, 0, 0, 82), 0, 8)

    sl = QVBoxLayout(streak_f)

    sl.setContentsMargins(22, 20, 22, 20)

    sl.setSpacing(8)



    s_iw = QFrame()

    s_iw.setFixedSize(36, 36)

    s_iw.setStyleSheet("background:rgba(255,152,0,0.18); border-radius:18px; border:1px solid rgba(255,152,0,0.4);")

    s_il = QHBoxLayout(s_iw)

    s_il.setContentsMargins(0, 0, 0, 0)

    s_il_lbl = QLabel()

    s_il_lbl.setPixmap(create_icon("timer", "#FF9800", 18).pixmap(18, 18))

    s_il_lbl.setFixedSize(18, 18)

    s_il.addWidget(s_il_lbl, 0, Qt.AlignCenter)



    s_tag = QLabel(t("stats.tag.featured"))

    s_tag.setStyleSheet("font-size:10px; font-weight:700; color:#FF9800; letter-spacing:1px;")

    s_top = QHBoxLayout()

    s_top.addWidget(s_iw, 0, Qt.AlignLeft)

    s_top.addSpacing(8)

    s_top.addWidget(s_tag, 0, Qt.AlignVCenter)

    s_top.addStretch()

    sl.addLayout(s_top)



    s_val = QLabel(str(streak))

    s_val.setStyleSheet(f"font-size:32px; font-weight:900; color:{TEXT_PRIMARY};")

    s_lbl = QLabel(t("stats.streak.title"))

    s_lbl.setStyleSheet(f"font-size:11px; font-weight:700; color:{TEXT_MUTED}; letter-spacing:1.2px;")

    s_desc = QLabel(

        t("stats.streak.description.many", count=streak) if streak > 1

        else (t("stats.streak.description.one") if streak == 1 else t("stats.streak.description.none"))

    )

    s_desc.setWordWrap(True)

    s_desc.setStyleSheet(f"font-size:11px; color:{TEXT_MUTED};")

    sl.addWidget(s_val)

    sl.addWidget(s_lbl)

    sl.addWidget(s_desc)



    # â”€â”€ Bu hafta vs geçen hafta â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    diff     = this_week - last_week

    diff_pct = int(abs(diff) / max(last_week, 1) * 100)

    trend_c  = "#4CAF50" if diff >= 0 else "#E91E63"

    arrow    = "â–²" if diff >= 0 else "â–¼"



    week_f = QFrame()

    week_f.setObjectName("StatsWeekCard")

    week_f.setStyleSheet(f"""

        QFrame#StatsWeekCard {{

            background: qlineargradient(x1:0,y1:0,x2:1,y2:1,

                stop:0 {_qss_rgba(trend_c, 14)}, stop:1 {BG_CARD});

            border:1px solid {_qss_rgba(trend_c, 48)};

            border-radius:22px;

        }}

        QFrame#StatsWeekCard QLabel {{ background:transparent; border:none; }}

    """)

    app._add_soft_shadow(week_f, 22, QColor(0, 0, 0, 82), 0, 8)

    wl = QVBoxLayout(week_f)

    wl.setContentsMargins(22, 20, 22, 20)

    wl.setSpacing(8)



    w_iw = QFrame()

    w_iw.setFixedSize(36, 36)

    w_iw.setStyleSheet(f"background:{_qss_rgba(trend_c, 22)}; border-radius:18px; border:1px solid {_qss_rgba(trend_c, 55)};")

    w_il = QHBoxLayout(w_iw)

    w_il.setContentsMargins(0, 0, 0, 0)

    w_il_lbl = QLabel()

    w_il_lbl.setPixmap(create_icon("play", trend_c, 18).pixmap(18, 18))

    w_il_lbl.setFixedSize(18, 18)

    w_il.addWidget(w_il_lbl, 0, Qt.AlignCenter)



    w_tag = QLabel(t("stats.tag.featured"))

    w_tag.setStyleSheet(f"font-size:10px; font-weight:700; color:{trend_c}; letter-spacing:1px;")

    w_top = QHBoxLayout()

    w_top.addWidget(w_iw, 0, Qt.AlignLeft)

    w_top.addSpacing(8)

    w_top.addWidget(w_tag, 0, Qt.AlignVCenter)

    w_top.addStretch()

    wl.addLayout(w_top)



    w_val = QLabel(str(this_week))

    w_val.setStyleSheet(f"font-size:32px; font-weight:900; color:{TEXT_PRIMARY};")

    w_lbl = QLabel(t("stats.week.title"))

    w_lbl.setStyleSheet(f"font-size:11px; font-weight:700; color:{TEXT_MUTED}; letter-spacing:1.2px;")

    if last_week > 0:

        trend_key = "stats.week.up" if diff >= 0 else "stats.week.down"

        w_desc = QLabel(t("stats.week.comparison", arrow=arrow, percent=diff_pct, trend=t(trend_key), last_week=last_week))

    else:

        w_desc = QLabel(t("stats.week.first"))

    w_desc.setWordWrap(True)

    w_desc.setStyleSheet(f"font-size:11px; color:{trend_c if last_week > 0 else TEXT_MUTED};")

    wl.addWidget(w_val)

    wl.addWidget(w_lbl)

    wl.addWidget(w_desc)



    hl.addWidget(streak_f, 1)

    hl.addWidget(week_f, 1)

    return wrap





# â”€â”€ Saatlik aktivite paneli â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€



def _build_hourly_panel(app, hourly_counts: list, acc: str):

    t = app._tr

    panel, body = _make_stats_panel(

        app, t("stats.hourly.title"),

        t("stats.hourly.subtitle"),

        acc, icon_name="timer", tone="#7EC8FF",

    )



    if any(hourly_counts):

        body.addWidget(_HourlyBarChart(hourly_counts, acc))

        body.addSpacing(6)



        legend = QWidget()

        legend.setStyleSheet("background:transparent;")

        ll = QHBoxLayout(legend)

        ll.setContentsMargins(0, 0, 0, 0)

        ll.setSpacing(16)

        for color, lbl_text in [

            ("#7EC8FF", t("stats.hourly.morning")),

            (acc,       t("stats.hourly.afternoon")),

            ("#C287FF", t("stats.hourly.evening")),

            ("#3A4A70", t("stats.hourly.night")),

        ]:

            dot = QLabel("â—")

            dot.setStyleSheet(f"color:{color}; font-size:11px; background:transparent;")

            txt = QLabel(lbl_text)

            txt.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11px; background:transparent;")

            row_w = QHBoxLayout()

            row_w.setSpacing(5)

            row_w.addWidget(dot)

            row_w.addWidget(txt)

            ll.addLayout(row_w)

        ll.addStretch()

        body.addWidget(legend)

    else:

        e = QLabel(t("stats.hourly.empty"))

        e.setWordWrap(True)

        e.setStyleSheet(f"color:{TEXT_MUTED}; font-size:13px;")

        body.addWidget(e)



    return panel





# â”€â”€ Sanatçı daÄŸılım paneli â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€



def _build_artist_distribution_panel(app, top_artists, acc: str):

    t = app._tr

    panel, body = _make_stats_panel(

        app, t("stats.distribution.title"),

        t("stats.distribution.subtitle"),

        acc, icon_name="music", tone="#C287FF",

    )



    if not top_artists:

        e = QLabel(t("stats.distribution.empty"))

        e.setStyleSheet(f"color:{TEXT_MUTED}; font-size:13px;")

        body.addWidget(e)

        return panel



    colors = _stats_blue_palette(acc) + ["#67E8F9"]

    total  = sum(p for _, p in top_artists) or 1



    main_row = QHBoxLayout()

    main_row.setContentsMargins(0, 0, 0, 0)

    main_row.setSpacing(20)

    main_row.addWidget(_DonutChart(top_artists[:5], colors), 0, Qt.AlignVCenter)



    legend = QWidget()

    legend.setStyleSheet("background:transparent;")

    lg_l = QVBoxLayout(legend)

    lg_l.setContentsMargins(0, 0, 0, 0)

    lg_l.setSpacing(10)



    for i, (artist, plays) in enumerate(top_artists[:5]):

        color = colors[i % len(colors)]

        pct   = int(plays / total * 100)



        bar = QProgressBar()

        bar.setRange(0, 100)

        bar.setValue(pct)

        bar.setFixedHeight(6)

        bar.setStyleSheet(

            f"QProgressBar{{background:{BG_ELEVATED}; border-radius:3px; border:none;}}"

            f"QProgressBar::chunk{{background:{color}; border-radius:3px;}}"

        )

        top_row = QHBoxLayout()

        top_row.setSpacing(6)

        dot = QLabel("â—")

        dot.setStyleSheet(f"color:{color}; font-size:11px; background:transparent;")

        name = QLabel(artist[:24] + ("â€¦" if len(artist) > 24 else ""))

        name.setStyleSheet(

            f"font-size:13px; font-weight:{'800' if i == 0 else '600'}; "

            f"color:{TEXT_PRIMARY}; background:transparent;"

        )

        pct_lbl = QLabel(f"%{pct}")

        pct_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        pct_lbl.setStyleSheet(

            f"font-size:12px; font-weight:700; color:{color}; background:transparent; min-width:38px;"

        )

        top_row.addWidget(dot)

        top_row.addWidget(name, 1)

        top_row.addWidget(pct_lbl)



        item_w = QVBoxLayout()

        item_w.setSpacing(4)

        item_w.addLayout(top_row)

        item_w.addWidget(bar)

        lg_l.addLayout(item_w)



    main_row.addWidget(legend, 1)

    body.addLayout(main_row)

    return panel





def build_stats_page(app):

    app.current_page = "stats"

    t = app._tr



    page = QWidget()

    page.setStyleSheet(f"background:{BG_BLACK};")



    scroll = QScrollArea()

    scroll.setWidgetResizable(True)

    scroll.setStyleSheet("background:transparent; border:none;")



    page_l = QVBoxLayout(page)

    page_l.setContentsMargins(0, 0, 0, 0)

    page_l.addWidget(scroll)



    content = QWidget()

    content.setObjectName("StatsContentV2")

    content_l = QVBoxLayout(content)

    content_l.setContentsMargins(36, 36, 36, 36)

    content_l.setSpacing(0)

    scroll.setWidget(content)



    acc = _stats_primary_accent()

    compact = _is_stats_compact(app)



    reset_btn = QPushButton(t("stats.reset"))

    reset_btn.setIcon(create_icon("delete", "#FFB4B4", 16))

    reset_btn.setCursor(Qt.PointingHandCursor)

    reset_btn.setStyleSheet(f"""

        QPushButton {{

            background: rgba(255,255,255,0.035);

            color: #FFD7D7;

            border: 1px solid rgba(255,107,107,0.26);

            border-radius: 16px;

            padding: 10px 16px;

            font-size: 12px;

            font-weight: 700;

        }}

        QPushButton:hover {{

            background: rgba(255,107,107,0.10);

            border-color: rgba(255,107,107,0.42);

        }}

    """)

    reset_btn.clicked.connect(app._reset_stats)



    header_actions = QWidget()

    header_actions.setStyleSheet("background:transparent;")

    header_actions_l = QHBoxLayout(header_actions)

    header_actions_l.setContentsMargins(0, 0, 0, 0)

    header_actions_l.addWidget(reset_btn)



    content_l.addWidget(_build_page_header(

        app,

        t("stats.title"),

        t("stats.subtitle"),

        eyebrow=t("stats.eyebrow"),

        right_widget=header_actions,

    ))

    content_l.addSpacing(14)

    content_l.addWidget(_build_period_selector(app, acc))
    content_l.addSpacing(18)

    period = getattr(app, "_stats_period", "all")
    plays_map, period_history, period_ms, period_daily_ms = _filter_stats_by_period(app, period)

    stats = app.stats or {}
    period_stats = dict(stats)
    period_stats["play_count"] = dict(plays_map)
    period_stats["total_ms"] = int(period_ms)
    period_stats["daily_ms"] = dict(period_daily_ms)
    period_stats["period_start"] = _period_stats_start(stats, period).isoformat(timespec="seconds")
    total_ms  = period_ms
    total_min = total_ms // 60_000
    total_plays = sum(plays_map.values())
    id_count = sorted(plays_map.items(), key=lambda x: x[1], reverse=True)
    hist_map = {track["videoId"]: track for track in period_history if "videoId" in track}
    if not hist_map:
        hist_map = {track["videoId"]: track for track in app.history if "videoId" in track}


    artist_plays: dict[str, int] = defaultdict(int)

    for vid, cnt in plays_map.items():

        track = hist_map.get(vid)

        if track:

            artist_name = app._artist_str(track)

            if artist_name and artist_name != "?":

                artist_plays[artist_name] += cnt



    top_artists = sorted(artist_plays.items(), key=lambda x: x[1], reverse=True)[:5]

    artist_spotlights = _build_artist_spotlight_map(app, plays_map, hist_map, top_artists)

    top_artist = top_artists[0][0] if top_artists else "â€”"

    top_artist_plays = top_artists[0][1] if top_artists else 0

    top_song = hist_map.get(id_count[0][0], {}).get("title", "â€”") if id_count else "â€”"

    top_song_cnt = id_count[0][1] if id_count else 0

    start_text, span_text = _stats_period_text(stats, app)
    period_start = _period_stats_start(stats, period)
    now = datetime.now(period_start.tzinfo) if period_start.tzinfo else datetime.now()
    days_active = max(1, (now - period_start).days + 1)
    avg_min = total_min // days_active


    bar_items = []

    for vid, cnt in id_count[:8]:

        track = hist_map.get(vid)

        if track:

            bar_items.append((track.get("title", vid)[:32], cnt))



    hero = _build_stats_hero(

        app,

        acc,

        start_text,

        span_text,

        total_min,

        total_plays,

        len(app.favorites),

        len(app.playlists),

        top_artist,

        top_artist_plays,

        top_song,

        top_song_cnt,

        avg_min,

    )

    content_l.addWidget(hero)

    content_l.addSpacing(18)



    cards_wrap = QWidget()

    cards_wrap.setStyleSheet("background:transparent;")

    cards_l = QGridLayout(cards_wrap)

    cards_l.setContentsMargins(0, 0, 0, 0)

    cards_l.setHorizontalSpacing(14)

    cards_l.setVerticalSpacing(14)



    stat_cards = [

        _make_animated_stat_card(

            app, t("stats.card.total_time"), _fmt_hours_minutes(total_min, app), total_min,

            lambda value, owner=app: _fmt_hours_minutes(value, owner), acc, icon_name="headphone", tone=acc

        ),

        _make_animated_stat_card(

            app, t("stats.card.plays"), str(total_plays), total_plays,

            lambda value: str(value), acc, icon_name="play", tone="#6FA8FF"

        ),

        _make_animated_stat_card(

            app, t("stats.card.likes"), str(len(app.favorites)), len(app.favorites),

            lambda value: str(value), acc, icon_name="heart_on", tone="#82C6FF"

        ),

        _make_animated_stat_card(

            app, t("stats.card.playlists"), str(len(app.playlists)), len(app.playlists),

            lambda value: str(value), acc, icon_name="playlist_add", tone="#95B8FF"

        ),

    ]



    if compact:

        cards_l.setColumnStretch(0, 1)

        cards_l.setColumnStretch(1, 1)

        for idx, card in enumerate(stat_cards):

            cards_l.addWidget(card, idx // 2, idx % 2)

    else:

        for col in range(4):

            cards_l.setColumnStretch(col, 1)

        for idx, card in enumerate(stat_cards):

            cards_l.addWidget(card, 0, idx)



    content_l.addWidget(cards_wrap)

    content_l.addSpacing(16)



    streak     = _calc_streak(period_history)

    this_week, last_week = _calc_week_comparison(period_history)

    content_l.addWidget(_build_streak_week_row(app, streak, this_week, last_week, acc))

    content_l.addSpacing(22)



    dashboard = QWidget()

    dashboard.setStyleSheet("background:transparent;")

    if compact:

        dashboard_l = QVBoxLayout(dashboard)

    else:

        dashboard_l = QHBoxLayout(dashboard)

    dashboard_l.setContentsMargins(0, 0, 0, 0)

    dashboard_l.setSpacing(18)



    wrapped_panel, wrapped_body = _make_stats_panel(
        app,
        t("stats.wrapped.panel_title"),
        t("stats.wrapped.panel_subtitle"),
        acc,
        icon_name="timer",
        tone="#6FA8FF",
    )
    _build_wrapped_section(app, wrapped_body, period_stats, hist_map, "#6FA8FF", show_header=False)
    wrapped_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    insights_panel = _build_quick_insights_panel(app, bar_items, top_artists, artist_spotlights, acc)


    if compact:

        dashboard_l.addWidget(wrapped_panel)

        dashboard_l.addWidget(insights_panel)

    else:

        dashboard_l.addWidget(wrapped_panel, 5)

        dashboard_l.addWidget(insights_panel, 4)



    content_l.addWidget(dashboard)

    content_l.addSpacing(22)



    hourly_counts = _calc_hourly_counts(period_history)

    extra_row = QWidget()

    extra_row.setStyleSheet("background:transparent;")

    if compact:

        extra_row_l = QVBoxLayout(extra_row)

    else:

        extra_row_l = QHBoxLayout(extra_row)

    extra_row_l.setContentsMargins(0, 0, 0, 0)

    extra_row_l.setSpacing(18)



    hourly_panel = _build_hourly_panel(app, hourly_counts, acc)

    dist_panel   = _build_artist_distribution_panel(app, top_artists, acc)



    if compact:

        extra_row_l.addWidget(hourly_panel)

        extra_row_l.addWidget(dist_panel)

    else:

        extra_row_l.addWidget(hourly_panel, 5)

        extra_row_l.addWidget(dist_panel, 4)



    content_l.addWidget(extra_row)

    content_l.addSpacing(22)



    top_tracks_panel = _build_top_tracks_panel(app, id_count, hist_map, acc)

    content_l.addWidget(top_tracks_panel)

    content_l.addStretch()

    return page


def _build_hourly_panel(app, hourly_counts: list, acc: str):

    t = app._tr

    panel, body = _make_stats_panel(

        app, t("stats.hourly.title"),

        t("stats.hourly.subtitle"),

        acc, icon_name="timer", tone="#7EC8FF",

    )



    if any(hourly_counts):

        body.addWidget(_HourlyBarChart(hourly_counts, acc))

        body.addSpacing(6)



        legend = QWidget()

        legend.setStyleSheet("background:transparent;")

        ll = QHBoxLayout(legend)

        ll.setContentsMargins(0, 0, 0, 0)

        ll.setSpacing(16)

        for color, lbl_text in [

            ("#7EC8FF", t("stats.hourly.morning")),

            (acc,       t("stats.hourly.afternoon")),

            ("#C287FF", t("stats.hourly.evening")),

            ("#3A4A70", t("stats.hourly.night")),

        ]:

            row = QWidget()

            row.setStyleSheet("background:transparent;")

            row_l = QHBoxLayout(row)

            row_l.setContentsMargins(0, 0, 0, 0)

            row_l.setSpacing(6)

            row_l.addWidget(_stats_color_dot(color), 0, Qt.AlignVCenter)

            txt = QLabel(lbl_text)

            txt.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11px; background:transparent;")

            row_l.addWidget(txt)

            ll.addWidget(row, 0, Qt.AlignVCenter)

        ll.addStretch()

        body.addWidget(legend)

    else:

        e = QLabel(t("stats.hourly.empty"))

        e.setWordWrap(True)

        e.setStyleSheet(f"color:{TEXT_MUTED}; font-size:13px;")

        body.addWidget(e)



    return panel


def _build_artist_distribution_panel(app, top_artists, acc: str):

    t = app._tr

    panel, body = _make_stats_panel(

        app, t("stats.distribution.title"),

        t("stats.distribution.subtitle"),

        acc, icon_name="music", tone="#C287FF",

    )



    if not top_artists:

        e = QLabel(t("stats.distribution.empty"))

        e.setStyleSheet(f"color:{TEXT_MUTED}; font-size:13px;")

        body.addWidget(e)

        return panel



    colors = _stats_blue_palette(acc) + ["#67E8F9"]

    total  = sum(p for _, p in top_artists) or 1



    main_row = QHBoxLayout()

    main_row.setContentsMargins(0, 0, 0, 0)

    main_row.setSpacing(20)

    main_row.addWidget(_DonutChart(top_artists[:5], colors), 0, Qt.AlignVCenter)



    legend = QWidget()

    legend.setStyleSheet("background:transparent;")

    lg_l = QVBoxLayout(legend)

    lg_l.setContentsMargins(0, 0, 0, 0)

    lg_l.setSpacing(10)



    for i, (artist, plays) in enumerate(top_artists[:5]):

        color = colors[i % len(colors)]

        pct   = int(plays / total * 100)



        bar = QProgressBar()

        bar.setRange(0, 100)

        bar.setValue(pct)

        bar.setFixedHeight(6)

        bar.setStyleSheet(

            f"QProgressBar{{background:{BG_ELEVATED}; border-radius:3px; border:none;}}"

            f"QProgressBar::chunk{{background:{color}; border-radius:3px;}}"

        )

        top_row = QHBoxLayout()

        top_row.setSpacing(6)

        top_row.addWidget(_stats_color_dot(color), 0, Qt.AlignVCenter)

        name = QLabel(_stats_truncate(artist, 24))

        name.setStyleSheet(

            f"font-size:13px; font-weight:{'800' if i == 0 else '600'}; "

            f"color:{TEXT_PRIMARY}; background:transparent;"

        )

        pct_lbl = QLabel(f"%{pct}")

        pct_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        pct_lbl.setStyleSheet(

            f"font-size:12px; font-weight:700; color:{color}; background:transparent; min-width:38px;"

        )

        top_row.addWidget(name, 1)

        top_row.addWidget(pct_lbl)



        row = QVBoxLayout()

        row.setSpacing(5)

        row.addLayout(top_row)

        row.addWidget(bar)

        lg_l.addLayout(row)



    main_row.addWidget(legend, 1)

    body.addLayout(main_row)

    return panel

