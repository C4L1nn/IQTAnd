"""Custom delegate for the lyrics list."""
import html as _html
import re

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QFont, QTextDocument
from PySide6.QtWidgets import QStyledItemDelegate

from core.constants import TEXT_MUTED
from core.theme import get_accent


class LyricsDelegate(QStyledItemDelegate):
    MARGIN_H = 12
    MARGIN_V = 12
    _VOWELS = set("aeiioouuAEIIOOUUaeiioouu")

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._doc_cache = {}
        self._size_cache = {}

    def clear_cache(self):
        self._doc_cache.clear()
        self._size_cache.clear()

    def _font_size(self, active: bool) -> int:
        base = int(getattr(self.app, "_lyr_font_size", 15) or 15)
        return max(12, min(base + (1 if active else 0), 26))

    def _make_font(self, active: bool) -> QFont:
        font = QFont()
        font.setPointSize(self._font_size(active))
        font.setBold(bool(active))
        return font

    def _word_weight(self, word: str) -> int:
        if not word:
            return 1
        vowels = sum(1 for ch in word if ch in self._VOWELS)
        return max(1, vowels)

    def _transparent(self) -> str:
        return "rgba(0,0,0,0)"

    def _glow_rgba(self, alpha: float) -> str:
        color = QColor(get_accent())
        level = max(0, min(int(alpha * 255), 255))
        return f"rgba({color.red()},{color.green()},{color.blue()},{level})"

    def _lerp_css(self, a: QColor, b: QColor, t: float) -> str:
        t = max(0.0, min(t, 1.0))
        r = int(a.red() + (b.red() - a.red()) * t)
        g = int(a.green() + (b.green() - a.green()) * t)
        bl = int(a.blue() + (b.blue() - a.blue()) * t)
        return f"rgb({r},{g},{bl})"

    def _build_doc(self, text: str, font: QFont, width: int, html: str | None = None, color: str | None = None) -> QTextDocument:
        doc = QTextDocument()
        doc.setDefaultFont(font)
        doc.setDocumentMargin(0)
        doc.setTextWidth(max(width, 160))
        if html is None:
            safe = _html.escape(text or "")
            css_color = color or TEXT_MUTED
            doc.setHtml(
                "<div style='text-align:center; line-height:1.22; white-space:pre-wrap; "
                f"color:{css_color};'>{safe}</div>"
            )
        else:
            doc.setHtml(
                "<div style='text-align:center; line-height:1.22; white-space:pre-wrap;'>"
                f"{html}</div>"
            )
        return doc

    def _doc_cache_key(self, row: int, width: int, mode: str, is_active: bool, progress: float = 0.0) -> tuple:
        bucket = int(max(0.0, min(progress, 1.0)) * 100)
        return (
            int(row),
            int(width),
            mode,
            bool(is_active),
            int(self._font_size(is_active)),
            bucket,
        )

    def _get_cached_doc(self, row: int, text: str, width: int, *, is_active: bool, mode: str, html: str | None = None, color: str | None = None, progress: float = 0.0) -> QTextDocument:
        key = self._doc_cache_key(row, width, mode, is_active, progress=progress)
        doc = self._doc_cache.get(key)
        if doc is not None:
            return doc
        if len(self._doc_cache) > 900:
            self._doc_cache.clear()
        doc = self._build_doc(text, self._make_font(is_active), width, html=html, color=color)
        self._doc_cache[key] = doc
        return doc

    def _karaoke_html(self, text: str, accent: str, muted: str, progress: float, glow_only: bool = False) -> str:
        tokens = re.findall(r"\S+|\s+", text)
        words = [token for token in tokens if not token.isspace()]
        weights = [
            self._word_weight(re.sub(r"[^\w]+", "", word, flags=re.UNICODE))
            for word in words
        ]
        total = sum(weights) or 1
        target = max(0.0, min(progress, 1.0)) * total

        cumulative = 0
        active_word_index = 0
        intra = 0.0
        for idx, weight in enumerate(weights):
            if target <= cumulative + weight:
                active_word_index = idx
                intra = 0.0 if weight == 0 else (target - cumulative) / weight
                break
            cumulative += weight
        else:
            active_word_index = max(0, len(weights) - 1)
            intra = 1.0

        out = []
        word_index = -1
        for token in tokens:
            if token.isspace():
                out.append(token.replace(" ", "&nbsp;"))
                continue

            word_index += 1
            safe = _html.escape(token)
            if word_index < active_word_index:
                color = accent if not glow_only else self._transparent()
                out.append(f'<span style="color:{color}">{safe}</span>')
                continue
            if word_index > active_word_index:
                color = muted if not glow_only else self._transparent()
                out.append(f'<span style="color:{color}">{safe}</span>')
                continue

            accent_q = QColor(accent)
            muted_q = QColor(muted)
            count = max(1, len(token))
            cut = max(0.0, min(intra, 1.0)) * count
            fade = 4.0
            segments = []
            for char_index, char in enumerate(token):
                if glow_only:
                    color = self._glow_rgba(0.34) if char_index <= cut else self._transparent()
                else:
                    if char_index < cut - fade:
                        color = accent
                    elif char_index > cut + fade:
                        color = muted
                    else:
                        t = (char_index - (cut - fade)) / (2.0 * fade)
                        color = self._lerp_css(accent_q, muted_q, t)
                if segments and segments[-1][0] == color:
                    segments[-1] = (color, segments[-1][1] + char)
                else:
                    segments.append((color, char))

            for color, chunk in segments:
                safe_chunk = _html.escape(chunk)
                if glow_only:
                    out.append(f'<span style="color:{color}; font-weight:700">{safe_chunk}</span>')
                else:
                    out.append(f'<span style="color:{color}; text-decoration:underline">{safe_chunk}</span>')

        return "".join(out)

    def sizeHint(self, option, index):
        row = index.row()
        current_idx = int(getattr(self.app, "_lyr_current_idx", -1) or -1)
        is_active = row == current_idx
        text = index.data() or ""
        view_width = option.widget.viewport().width() if option.widget else 420
        text_width = max(view_width - self.MARGIN_H * 2 - 6, 160)
        size_key = (row, text_width, is_active, self._font_size(is_active))
        cached = self._size_cache.get(size_key)
        if cached is not None:
            return cached
        if len(self._size_cache) > 500:
            self._size_cache.clear()

        doc = self._get_cached_doc(
            row,
            text,
            text_width,
            is_active=is_active,
            mode="measure",
            color=TEXT_MUTED,
        )
        size = doc.size().toSize()
        hint = QSize(text_width, size.height() + self.MARGIN_V * 2 + 6)
        self._size_cache[size_key] = hint
        return hint

    def paint(self, painter, option, index):
        painter.save()
        rect = option.rect
        text = index.data() or ""
        row = index.row()
        current_idx = int(getattr(self.app, "_lyr_current_idx", -1) or -1)
        progress = float(getattr(self.app, "_lyr_progress", 0.0) or 0.0)
        is_active = row == current_idx
        effect_enabled = bool(getattr(self.app, "_lyr_effect_enabled", True))
        text_rect = rect.adjusted(self.MARGIN_H, self.MARGIN_V, -self.MARGIN_H, -self.MARGIN_V)

        if is_active and effect_enabled:
            accent = get_accent()
            muted = TEXT_MUTED
            html = self._karaoke_html(text, accent, muted, progress)
            doc = self._get_cached_doc(
                row,
                text,
                text_rect.width(),
                is_active=True,
                mode="active-effect",
                html=html,
                progress=progress,
            )
            painter.translate(text_rect.topLeft())
            for dx, dy, opacity in ((0, 0, 0.22), (-1, 0, 0.10), (1, 0, 0.10), (0, -1, 0.08), (0, 1, 0.08)):
                painter.save()
                painter.translate(dx, dy)
                painter.setOpacity(opacity)
                doc.drawContents(painter)
                painter.restore()
            painter.setOpacity(1.0)
            doc.drawContents(painter)
        else:
            doc = self._get_cached_doc(
                row,
                text,
                text_rect.width(),
                is_active=is_active,
                mode="plain",
                color=(get_accent() if is_active else TEXT_MUTED),
            )
            painter.translate(text_rect.topLeft())
            doc.drawContents(painter)
        painter.restore()
