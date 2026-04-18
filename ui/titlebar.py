"""Custom title bar widget for borderless windows with SVG icons.

This module defines a custom title bar to be used in place of the native
window frame when ``Qt.FramelessWindowHint`` is set on a window. The bar
provides minimise, maximise/restore and close buttons, displays the
application icon and title, and supports dragging the window by click‑and‑dragging
on the bar. Window control buttons are rendered as SVG icons tinted
with the application's accent colour.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QPoint, QByteArray
from PySide6.QtGui import (
    QIcon, QPainter, QPixmap, QColor, QPen
)
# QSvgRenderer lives in the QtSvg module in PySide6. It is imported separately
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QSizePolicy
)

from core.theme import get_accent
from core.constants import ICON_PATHS, BG_BLACK


class TitleBar(QWidget):
    """
    A custom title bar for frameless windows.

    This widget replaces the native window frame when ``Qt.FramelessWindowHint``
    is used. It provides minimise, maximise/restore and close buttons, shows
    the application icon and title, and supports dragging the window by
    click‑and‑dragging on the bar. Window control icons are rendered from
    vector paths defined in :mod:`core.constants` and tinted to the current
    theme accent colour via :mod:`core.theme`.
    """

    def __init__(self, parent: QWidget, title: str = "iqtMusic") -> None:
        """Construct a new title bar for the given ``parent``.

        Parameters
        ----------
        parent : QWidget
            The top‑level window this title bar controls.
        title : str
            The window caption text shown in the centre of the bar.
        """
        super().__init__(parent)
        self._parent = parent
        self._drag_pos: QPoint | None = None
        # Cache the accent colour and icon size once. Accent is looked up
        # via core.theme so icons always reflect the current theme.
        self._accent = QColor(get_accent())
        self._icon_size = 14

        # Layout for the title bar contents
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)

        # Application icon
        icon_label = QLabel()
        icon = parent.windowIcon() if hasattr(parent, "windowIcon") else QIcon()
        icon_label.setPixmap(icon.pixmap(20, 20))
        layout.addWidget(icon_label)

        # Window title label
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-weight: bold;")
        self.title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self.title_label)

        # Minimise button
        self.min_button = QPushButton()
        self.min_button.setFixedSize(24, 24)
        self.min_button.clicked.connect(self._on_minimise)
        layout.addWidget(self.min_button)

        # Maximise/restore button
        self.max_button = QPushButton()
        self.max_button.setFixedSize(24, 24)
        self.max_button.clicked.connect(self._on_maximise_restore)
        layout.addWidget(self.max_button)

        # Close button
        self.close_button = QPushButton()
        self.close_button.setFixedSize(24, 24)
        self.close_button.clicked.connect(self._on_close)
        layout.addWidget(self.close_button)

        # Apply styling and icons after constructing buttons
        self._apply_styles()
        self._apply_icons()
        self.sync_window_state()

    def setTitle(self, title: str) -> None:
        """Update the displayed title text on the title bar.

        Parameters
        ----------
        title : str
            The new title text to display.
        """
        self.title_label.setText(title)

    # Internal helper methods
    def _apply_styles(self) -> None:
        """Apply consistent styling to the title bar and buttons."""
        btn_css = (
            "QPushButton {\n"
            "    background-color: transparent;\n"
            "    border: none;\n"
            "    border-radius: 8px;\n"
            "}\n"
            "QPushButton:hover {\n"
            "    background-color: #333333;\n"
            "}\n"
            "QPushButton:pressed {\n"
            "    background-color: #444444;\n"
            "}\n"
        )
        self.min_button.setStyleSheet(btn_css)
        self.max_button.setStyleSheet(btn_css)
        close_css = btn_css + "QPushButton:hover { background-color: #e81123; }"
        self.close_button.setStyleSheet(close_css)
        # Use the application's darkest background colour for the title bar so it
        # blends with the rest of the app theme. Text colour is kept light.
        self.setStyleSheet(f"background-color: {BG_BLACK}; color: #e0e0e0;")

    def _apply_icons(self) -> None:
        """Generate and assign SVG icons to the window control buttons."""
        # Minimise icon
        if "minus" in ICON_PATHS:
            self.min_button.setIcon(self._create_svg_icon(ICON_PATHS["minus"]))
        # Create maximise and restore icons and assign the maximise icon initially.
        # These are drawn as simple rectangles for a more professional look. A
        # single outline represents the maximise button, while two overlapping
        # outlines represent the restore button. See ``_create_rect_icon`` for
        # implementation details.
        self.max_icon = self._create_rect_icon(restore=False)
        self.restore_icon = self._create_rect_icon(restore=True)
        self.max_button.setIcon(self.max_icon)
        # Close icon
        if "close" in ICON_PATHS:
            self.close_button.setIcon(self._create_svg_icon(ICON_PATHS["close"]))

    def _tr(self, key: str) -> str:
        cb = getattr(self._parent, "_tr", None)
        if callable(cb):
            return str(cb(key))
        fallback = {
            "titlebar.minimize": "Minimize",
            "titlebar.maximize": "Maximize",
            "titlebar.restore": "Restore",
            "titlebar.close": "Close",
        }
        return fallback.get(key, key)

    def refresh_texts(self) -> None:
        expanded = self._window_is_expanded()
        self.min_button.setToolTip(self._tr("titlebar.minimize"))
        self.max_button.setToolTip(
            self._tr("titlebar.restore") if expanded else self._tr("titlebar.maximize")
        )
        self.close_button.setToolTip(self._tr("titlebar.close"))

    def _window_is_expanded(self) -> bool:
        try:
            state = self._parent.windowState()
            return bool(state & Qt.WindowMaximized or state & Qt.WindowFullScreen)
        except Exception:
            return False

    def sync_window_state(self) -> None:
        expanded = self._window_is_expanded()
        self.max_button.setIcon(self.restore_icon if expanded else self.max_icon)
        self.refresh_texts()

    def _create_svg_icon(self, path_str: str) -> QIcon:
        """Return a coloured icon rendered from the given SVG path string."""
        svg = (
            f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>"
            f"<path fill='{self._accent.name()}' d='{path_str}'/></svg>"
        )
        renderer = QSvgRenderer(QByteArray(svg.encode()))
        pixmap = QPixmap(self._icon_size, self._icon_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)

    def _create_rect_icon(self, restore: bool) -> QIcon:
        """Return a maximise or restore icon drawn as one or two rectangles.

        When ``restore`` is False this draws a single thin outline centred
        within the square; when True it draws two overlapping outlines to
        represent restoring down from a maximised state. Using full
        rectangles instead of corner segments produces a cleaner, more
        recognisable control icon consistent with standard window chrome.

        Parameters
        ----------
        restore : bool
            Whether to draw the restore (two rectangles) icon. If False a
            single rectangle for the maximise icon is drawn.

        Returns
        -------
        QIcon
            The generated icon with transparent background.
        """
        size = self._icon_size
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(self._accent)
        pen.setWidth(1)
        painter.setPen(pen)

        margin = 2  # outer margin from the edges of the icon
        if not restore:
            # Draw a single rectangle for the maximise button
            rect_size = size - 2 * margin
            painter.drawRect(margin, margin, rect_size, rect_size)
        else:
            # Draw two overlapping rectangles for the restore button
            offset = 3  # offset between the two rectangles
            rect_size = size - 2 * margin - offset
            # Back rectangle: shifted right
            painter.drawRect(margin + offset, margin, rect_size, rect_size)
            # Front rectangle: shifted down
            painter.drawRect(margin, margin + offset, rect_size, rect_size)

        painter.end()
        return QIcon(pixmap)

    # Slot methods
    def _on_minimise(self) -> None:
        self._parent.showMinimized()

    def _on_maximise_restore(self) -> None:
        if hasattr(self._parent, "toggle_maximize_restore"):
            self._parent.toggle_maximize_restore()
        else:
            if self._window_is_expanded():
                self._parent.showNormal()
            else:
                self._parent.showMaximized()
        self.sync_window_state()

    def _on_close(self) -> None:
        self._parent.close()

    # Mouse events to move the window
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and not self._window_is_expanded():
            self._drag_pos = event.globalPosition().toPoint() - self._parent.frameGeometry().topLeft()
            event.accept()
            return
        self._drag_pos = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._window_is_expanded():
            self._drag_pos = None
            super().mouseMoveEvent(event)
            return
        if event.buttons() & Qt.LeftButton and self._drag_pos is not None:
            self._parent.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._on_maximise_restore()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)
