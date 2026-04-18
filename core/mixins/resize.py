"""Mixin for Resize functionality."""
import logging

log = logging.getLogger("iqtMusic")


from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QScrollBar, QWidget


class ResizeMixin:

    def _resize_edges(self, pos):
        """Verilen mouse pozisyonu için aktif kenarları döndür."""
        r = self.rect()
        m = self._RESIZE_MARGIN
        left   = pos.x() <= m
        right  = pos.x() >= r.width()  - m
        top    = pos.y() <= m
        bottom = pos.y() >= r.height() - m
        return left, right, top, bottom


    def _resize_cursor(self, left, right, top, bottom):
        if (top and left) or (bottom and right):
            return Qt.SizeFDiagCursor
        if (top and right) or (bottom and left):
            return Qt.SizeBDiagCursor
        if left or right:
            return Qt.SizeHorCursor
        if top or bottom:
            return Qt.SizeVerCursor
        return Qt.ArrowCursor


    def _clear_resize_cursor(self):
        owner = getattr(self, "_resize_cursor_owner", None)
        if owner is not None:
            try:
                owner.setCursor(self._resize_cursor_backup)
            except Exception:
                try:
                    owner.unsetCursor()
                except Exception as _e:
                    log.debug("Sessiz hata: %s", _e)
        self._resize_cursor_owner = None
        self._resize_cursor_backup = None
        try:
            self.unsetCursor()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)


    def _update_resize_cursor(self, owner, left, right, top, bottom):
        shape = self._resize_cursor(left, right, top, bottom)
        if shape == Qt.ArrowCursor:
            self._clear_resize_cursor()
            return
        if owner is not getattr(self, "_resize_cursor_owner", None):
            self._clear_resize_cursor()
            self._resize_cursor_owner = owner
            try:
                self._resize_cursor_backup = owner.cursor()
            except Exception:
                self._resize_cursor_backup = None
        try:
            owner.setCursor(shape)
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        try:
            self.setCursor(shape)
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)


    def eventFilter(self, obj, event):
        try:
            if isinstance(obj, QWidget) and (obj is self or obj.window() is self):
                et = event.type()
                pending_shadows = getattr(self, "_pending_soft_shadows", None)
                if pending_shadows:
                    if et == QEvent.Show:
                        entry = pending_shadows.get(id(obj))
                        if entry is not None:
                            widget, effect = entry
                            if widget is obj and widget.graphicsEffect() is not effect:
                                widget.setGraphicsEffect(effect)
                            pending_shadows.pop(id(obj), None)
                    elif et == QEvent.Destroy:
                        pending_shadows.pop(id(obj), None)
                if et in (QEvent.MouseButtonPress, QEvent.MouseMove, QEvent.MouseButtonRelease):
                    if self._handle_resize_event(obj, event):
                        return True
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        return super().eventFilter(obj, event)


    def _handle_resize_event(self, owner, event):
        if self.isMaximized() or self.isFullScreen():
            self._clear_resize_cursor()
            return False

        global_pos = event.globalPosition().toPoint()
        local_pos = self.mapFromGlobal(global_pos)
        left, right, top, bottom = self._resize_edges(local_pos)

        if isinstance(owner, QScrollBar) and not self._resize_active:
            edge_band = max(2, self._RESIZE_MARGIN // 2)
            near_outer_edge = (
                (left and local_pos.x() <= edge_band) or
                (right and local_pos.x() >= self.rect().width() - edge_band) or
                (top and local_pos.y() <= edge_band) or
                (bottom and local_pos.y() >= self.rect().height() - edge_band)
            )
            if not near_outer_edge:
                self._clear_resize_cursor()
                return False

        if event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.LeftButton and any((left, right, top, bottom)):
                self._resize_active = True
                self._resize_start = global_pos
                self._resize_geom = self.frameGeometry()
                self._resize_edges_s = (left, right, top, bottom)
                self._update_resize_cursor(owner, left, right, top, bottom)
                return True
            return False

        if event.type() == QEvent.MouseMove:
            if self._resize_active and (event.buttons() & Qt.LeftButton):
                delta = global_pos - self._resize_start
                g = self._resize_geom
                left, right, top, bottom = self._resize_edges_s
                nx, ny, nw, nh = g.x(), g.y(), g.width(), g.height()
                min_w = max(self.minimumWidth(), 800)
                min_h = max(self.minimumHeight(), 500)
                if right:
                    nw = max(min_w, g.width() + delta.x())
                if bottom:
                    nh = max(min_h, g.height() + delta.y())
                if left:
                    nw = max(min_w, g.width() - delta.x())
                    nx = g.x() + (g.width() - nw)
                if top:
                    nh = max(min_h, g.height() - delta.y())
                    ny = g.y() + (g.height() - nh)
                self.setGeometry(nx, ny, nw, nh)
                self._update_resize_cursor(owner, left, right, top, bottom)
                return True
            self._update_resize_cursor(owner, left, right, top, bottom)
            return False

        if event.type() == QEvent.MouseButtonRelease:
            if event.button() == Qt.LeftButton and self._resize_active:
                self._resize_active = False
                self._update_resize_cursor(owner, left, right, top, bottom)
                return True
            return False

        return False


    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            left, right, top, bottom = self._resize_edges(e.position().toPoint())
            if any((left, right, top, bottom)):
                self._resize_active  = True
                self._resize_start   = e.globalPosition().toPoint()
                self._resize_geom    = self.frameGeometry()
                self._resize_edges_s = (left, right, top, bottom)
                e.accept()
                return
        super().mousePressEvent(e)


    def mouseMoveEvent(self, e):
        pos = e.position().toPoint()
        if getattr(self, "_resize_active", False) and (e.buttons() & Qt.LeftButton):
            delta   = e.globalPosition().toPoint() - self._resize_start
            g       = self._resize_geom
            left, right, top, bottom = self._resize_edges_s
            nx, ny, nw, nh = g.x(), g.y(), g.width(), g.height()
            if right:   nw = max(800, g.width()  + delta.x())
            if bottom:  nh = max(500, g.height() + delta.y())
            if left:
                nw = max(800, g.width()  - delta.x())
                nx = g.x() + (g.width() - nw)
            if top:
                nh = max(500, g.height() - delta.y())
                ny = g.y() + (g.height() - nh)
            self.setGeometry(nx, ny, nw, nh)
            e.accept()
            return
        left, right, top, bottom = self._resize_edges(pos)
        self.setCursor(self._resize_cursor(left, right, top, bottom))
        super().mouseMoveEvent(e)


    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and getattr(self, "_resize_active", False):
            self._resize_active = False
            self.setCursor(Qt.ArrowCursor)
            e.accept()
            return
        super().mouseReleaseEvent(e)


    def resizeEvent(self, e):
        super().resizeEvent(e)
        try:
            self._refresh_playerbar_layout()
            self._layout_mini_player()
            if hasattr(self, "_update_window_rounding"):
                self._update_window_rounding()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
