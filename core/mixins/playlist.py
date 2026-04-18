"""Mixin for Playlist functionality."""
import logging
import random

log = logging.getLogger("iqtMusic")

from core.constants import BG_CARD, BG_ELEVATED, BORDER_COLOR, TEXT_MUTED, TEXT_SECONDARY
from core.theme import get_accent, get_accent_hover
from utils.helpers import safe_save_json

from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QDialog, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMenu, QMessageBox, QPushButton, QVBoxLayout, QWidget
from PySide6.QtCore import Qt

class PlaylistMixin:

    def _mix_playlist_name(self) -> str:
        return self._tr("nav.mix")

    def _resolve_mix_playlist_name(self) -> str:
        preferred = self._mix_playlist_name()
        for name in (preferred, "Senin Icin Mix", "Senin İçin Mix", "Made For You"):
            if name in self.playlists:
                return name
        return preferred

    def _store_mix_playlist(self, tracks: list) -> str:
        preferred = self._mix_playlist_name()
        for name in ("Senin Icin Mix", "Senin İçin Mix", "Made For You"):
            if name != preferred:
                self.playlists.pop(name, None)
        self.playlists[preferred] = list(tracks or [])
        return preferred

    def _dlg_new_playlist(self):
        """Tema uyumlu özel 'Yeni Liste' diyaloğu."""

        from ui.titlebar import TitleBar

        acc = get_accent()
        t = self._tr
        dlg = QDialog(self)
        dlg._tr = self._tr
        dlg.setWindowFlags(dlg.windowFlags() | Qt.FramelessWindowHint)
        dlg.setFixedSize(380, 185)
        dlg.setStyleSheet(f"background:{BG_CARD}; color:white;")

        vl = QVBoxLayout(dlg)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)

        tb = TitleBar(dlg, title=t("playlists.dialog.new.title"))
        tb.setStyleSheet(f"background:{BG_CARD}; color:white;")
        vl.addWidget(tb)

        body = QWidget()
        body.setStyleSheet(f"background:{BG_CARD};")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(24, 16, 24, 20)
        bl.setSpacing(14)

        lbl = QLabel(t("playlists.dialog.new.label"))
        lbl.setStyleSheet(f"font-size:12px; color:{TEXT_MUTED}; background:transparent;")
        edit = QLineEdit()
        edit.setPlaceholderText(t("playlists.dialog.new.placeholder"))
        edit.setFixedHeight(42)
        edit.setStyleSheet(f"""
            QLineEdit {{
                background:{BG_ELEVATED}; color:white;
                border:1px solid {BORDER_COLOR}; border-radius:10px;
                padding:0 12px; font-size:14px;
            }}
            QLineEdit:focus {{ border-color:{acc}; }}
        """)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        cancel_btn = QPushButton(t("playlists.dialog.new.cancel"))
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setFixedHeight(38)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent; color:{TEXT_SECONDARY};
                border:1px solid {BORDER_COLOR}; border-radius:10px;
                font-size:13px; font-weight:600;
            }}
            QPushButton:hover {{ border-color:{acc}55; color:{acc}; }}
        """)
        cancel_btn.clicked.connect(dlg.reject)

        create_btn = QPushButton(t("playlists.dialog.new.create"))
        create_btn.setCursor(Qt.PointingHandCursor)
        create_btn.setFixedHeight(38)
        create_btn.setStyleSheet(f"""
            QPushButton {{
                background:{acc}; color:#08120b;
                border:none; border-radius:10px;
                font-size:13px; font-weight:800;
            }}
            QPushButton:hover {{ background:{get_accent_hover()}; }}
        """)
        create_btn.clicked.connect(dlg.accept)
        edit.returnPressed.connect(dlg.accept)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(create_btn)
        bl.addWidget(lbl)
        bl.addWidget(edit)
        bl.addLayout(btn_row)
        vl.addWidget(body, 1)

        dlg.exec()
        if dlg.result() != QDialog.Accepted:
            return
        text = edit.text()
        if not text:
            return
        import re as _re
        clean = _re.sub(r'[\\/*?:"<>|]', "_", text.strip()).strip("_").strip()
        if not clean:
            return
        if clean in self.playlists:
            self.sig.notify.emit(t("playlists.toast.exists", name=clean))
            return
        self.playlists[clean] = []
        safe_save_json(self.playlist_file, self.playlists)
        self._update_pl_sidebar()
        self.sig.notify.emit(t("playlists.toast.created", name=clean))

    def _update_pl_sidebar(self):
        """Playlist listesi artık ayrı bir sayfada (Listelerim); sidebar güncelleme gerekmez."""
        current = str(getattr(self, "current_page", "") or "")
        try:
            if current == "playlists":
                self.page_playlists()
                return
            if current.startswith("playlist_"):
                playlist_name = current[len("playlist_"):]
                if playlist_name in self.playlists:
                    self.page_playlist(playlist_name)
                else:
                    self.page_playlists()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)

    def _pl_ctx(self, name):
        m = QMenu(self)
        m.addAction(f"📂 {name}").setEnabled(False)
        m.addSeparator()
        m.addAction(self._tr("playlists.menu.rename"), lambda: self._pl_rename(name))
        m.addAction(self._tr("playlists.menu.delete"), lambda: self._pl_delete(name))
        m.exec(QCursor.pos())

    def _pl_rename(self, old):
        text, ok = QInputDialog.getText(
            self,
            self._tr("playlists.dialog.rename.title"),
            self._tr("playlists.dialog.rename.label"),
            text=old,
        )
        if ok and text and text != old:
            import re as _re
            clean = _re.sub(r'[\\/*?:"<>|]', "_", text.strip()).strip("_").strip()
            if clean and clean not in self.playlists:
                self.playlists[clean] = self.playlists.pop(old)
                safe_save_json(self.playlist_file, self.playlists)
                manual = list(getattr(self, "_playlist_manual_order", None) or [])
                if old in manual:
                    manual[manual.index(old)] = clean
                    self._playlist_manual_order = manual
                self._update_pl_sidebar()
                if self.current_page == f"playlist_{old}":
                    self.page_playlist(clean)

    def _pl_delete(self, name):
        if QMessageBox.question(
                self,
                self._tr("playlists.dialog.delete.title"),
                self._tr("playlists.dialog.delete.message", name=name),
                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            del self.playlists[name]
            safe_save_json(self.playlist_file, self.playlists)
            manual = list(getattr(self, "_playlist_manual_order", None) or [])
            if name in manual:
                manual.remove(name)
                self._playlist_manual_order = manual
            self._update_pl_sidebar()
            if self.current_page == f"playlist_{name}":
                self.page_home()

    def _add_to_pl(self, name, track):
        if name not in self.playlists:
            self.playlists[name] = []
        vid = track.get("videoId", "")
        if not any(t.get("videoId") == vid for t in self.playlists[name]):
            self.playlists[name].append(track)
            safe_save_json(self.playlist_file, self.playlists)
            self._update_pl_sidebar()
            self.sig.notify.emit(self._tr("playlists.toast.added", name=name))

    def _remove_from_pl(self, name, track):
        tracks = self.playlists.get(name)
        if not tracks:
            return
        vid = track.get("videoId", "")
        before = len(tracks)
        if vid:
            self.playlists[name] = [t for t in tracks if t.get("videoId", "") != vid]
        else:
            self.playlists[name] = [t for t in tracks if t is not track]
        if len(self.playlists[name]) == before:
            return
        safe_save_json(self.playlist_file, self.playlists)
        self._update_pl_sidebar()
        self.sig.notify.emit(self._tr("playlists.toast.removed", name=name))
        if self.current_page == f"playlist_{name}":
            self.page_playlist(name)

    # ══════════════════════════════════════════════════════════════════════════
    # MİX
    # ══════════════════════════════════════════════════════════════════════════

    def _build_mix(self):
        pool = list(self.favorites[:50]) + list(self.history[:50])
        if not pool:
            pool = self._yt_search("Global Top 100", filter="songs", limit=50)
        random.shuffle(pool)
        seen, uniq = set(), []
        for t in pool:
            vid = t.get("videoId", "")
            if vid and vid not in seen:
                seen.add(vid)
                uniq.append(t)
        mix = uniq[:50]
        if mix:
            mix_name = self._store_mix_playlist(mix)
            safe_save_json(self.playlist_file, self.playlists)
            self._update_pl_sidebar()
            self.page_playlist(mix_name)
            self.sig.notify.emit(self._tr("playlists.toast.mix_ready", count=len(mix)))
        else:
            self.sig.notify.emit(self._tr("playlists.toast.mix_insufficient"))

    def _gen_mix(self):
        sources = []
        try: sources.extend(list(self.history[:30]))
        except Exception as _e: log.debug("Sessiz hata: %s", _e)
        try: sources.extend(list(self.favorites[:30]))
        except Exception as _e: log.debug("Sessiz hata: %s", _e)
        try: sources.extend(list(self.dl.all_tracks()[:30]))
        except Exception as _e: log.debug("Sessiz hata: %s", _e)

        mix, seen = [], set()
        for track in sources:
            if not isinstance(track, dict):
                continue
            vid    = str(track.get("videoId", "")).strip()
            title  = str(track.get("title", "")).strip().lower()
            artist = str(track.get("artist", "") or track.get("artists", "") or "").strip().lower()
            key    = vid or f"{title}|{artist}"
            if not key or key in seen:
                continue
            seen.add(key)
            mix.append(dict(track))
            if len(mix) >= 50:
                break

        if not mix:
            QMessageBox.information(
                self,
                self._tr("playlists.mix.error.title"),
                self._tr("playlists.mix.error.body"),
            )
            return
        mix_name = self._store_mix_playlist(mix)
        try:
            safe_save_json(self.playlist_file, self.playlists)
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        self.page_playlist(mix_name)

    # ══════════════════════════════════════════════════════════════════════════
    # BAĞLAM MENÜSÜ
    # ══════════════════════════════════════════════════════════════════════════
