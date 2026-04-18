"""Mixin for MiniPlayer functionality."""
import logging

from core.constants import TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY
from core.theme import get_accent
from ui.mini_player import _COVER as _MINI_COVER
from utils.helpers import create_icon, qt_is_valid

log = logging.getLogger("iqtMusic")


from PySide6.QtCore import QSize
from PySide6.QtWidgets import QWidget
from ui.mini_player import open_mini_player


class MiniPlayerMixin:

    def _open_mini(self):
        open_mini_player(self)


    def _hide_mini_player(self):
        try:
            if hasattr(self, "_mini_timer") and qt_is_valid(self._mini_timer):
                self._mini_timer.stop()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        try:
            if hasattr(self, "_mini_win") and qt_is_valid(self._mini_win):
                self._mini_win._drag_active = False
                self._mini_win._resize_active = False
                self._mini_win._resize_edges = set()
                self._mini_win.releaseMouse()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        try:
            if hasattr(self, "_mini_win") and qt_is_valid(self._mini_win):
                self._mini_win.hide()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)


    def _mini_widget_valid(self, name):
        try:
            obj = getattr(self, name, None)
            return obj is not None and qt_is_valid(obj)
        except Exception:
            return False


    def _layout_mini_player(self):
        try:
            if not hasattr(self, "_mini_win") or not qt_is_valid(self._mini_win):
                return
            w = self._mini_win.width()
            h = self._mini_win.height()
            # Kapak sabit 64×64 — cover container ve overlay play btn boyutu
            # ui/mini_player.py'daki _COVER sabitiyle senkron
            _COV = _MINI_COVER
            text_w = max(80, w - _COV - 80)
            if self._mini_widget_valid("_mini_img"):
                self._mini_img.setGeometry(0, 0, _COV, _COV)
            # Overlay play butonu: kapak üstünde 28×28 merkez
            if self._mini_widget_valid("_mini_play_btn"):
                self._mini_play_btn.setFixedSize(28, 28)
                self._mini_play_btn.setIconSize(QSize(12, 12))
            if self._mini_widget_valid("_mini_prev_btn"):
                self._mini_prev_btn.setFixedSize(24, 24)
                self._mini_prev_btn.setIconSize(QSize(12, 12))
            if self._mini_widget_valid("_mini_next_btn"):
                self._mini_next_btn.setFixedSize(24, 24)
                self._mini_next_btn.setIconSize(QSize(12, 12))
            if self._mini_widget_valid("_mini_lyrics_btn"):
                self._mini_lyrics_btn.setFixedSize(24, 24)
                self._mini_lyrics_btn.setIconSize(QSize(12, 12))
            if self._mini_widget_valid("_mini_fav_btn"):
                self._mini_fav_btn.setFixedSize(24, 24)
                self._mini_fav_btn.setIconSize(QSize(14, 14))
            # Başlık: pencere genişliğinden kapak + kenar marjinleri düşülür
            if self._mini_widget_valid("_mini_title"):
                self._mini_title.setMaximumWidth(text_w)
                self._mini_title.setMaximumHeight(34)
                self._mini_title.setWordWrap(True)
                self._mini_title.setStyleSheet(
                    f"font-size:11px; font-weight:700; color:{TEXT_PRIMARY}; background:transparent;")
            if self._mini_widget_valid("_mini_artist"):
                self._mini_artist.setMaximumWidth(text_w)
                self._mini_artist.setStyleSheet(
                    f"font-size:10px; color:{TEXT_SECONDARY}; background:transparent;")
            # Kontrol butonları: sabit 22×22
            if self._mini_widget_valid("_mini_vol"):
                self._mini_vol.setFixedWidth(max(48, min(96, w - 220)))
            if self._mini_widget_valid("_mini_seek"):
                self._mini_seek.setFixedHeight(12)
        except (RuntimeError, Exception):
            return


    def _update_mini(self):
        if not hasattr(self, "_mini_win") or not qt_is_valid(self._mini_win):
            return
        # _layout_mini_player() burada çağrılmaz; yalnızca resizeEvent tetikler.
        # Bu sayede 700ms'deki her timer tetiklemesinde tam layout hesabı önlenir.
        if not (self.queue and self.queue_index != -1):
            if self._mini_widget_valid("_mini_title"):  self._mini_title.setText(self._tr("mini_player.no_track"))
            if self._mini_widget_valid("_mini_artist"): self._mini_artist.setText(self._tr("mini_player.ready"))
            if self._mini_widget_valid("_mini_status"): self._mini_status.setText(self._tr("mini_player.choose_track"))
            if self._mini_widget_valid("_mini_seek"):
                self._mini_seek.setRange(0, 0)
                self._mini_seek.setValue(0)
            self._mini_last_vid = ""
            return
        t = self.queue[self.queue_index]
        vid = t.get("videoId", "")
        if self._mini_widget_valid("_mini_title"):  self._mini_title.setText(t.get("title", ""))
        if self._mini_widget_valid("_mini_artist"): self._mini_artist.setText(self._artist_str(t))
        is_playing = False
        try:
            is_playing = bool(self.player.is_playing())
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        if self._mini_widget_valid("_mini_status"):
            key = "mini_player.now_playing" if is_playing else "mini_player.paused"
            self._mini_status.setText(self._tr(key))
        if self._mini_widget_valid("_mini_play_btn"):
            self._mini_play_btn.setIcon(create_icon("pause" if is_playing else "play", "#FFFFFF", 12))
            self._mini_play_btn.setIconSize(QSize(12, 12))
            if hasattr(self._mini_play_btn, "setIconOffset"):
                self._mini_play_btn.setIconOffset(0 if is_playing else 1, 0)
        # ── Kapak: sadece şarkı değişince yeniden yükle (CPU tasarrufu) ──
        last_vid = getattr(self, "_mini_last_vid", "")
        thumb = self._thumb(t, big=True)
        if self._mini_widget_valid("_mini_img"):
            if vid != last_vid:
                self._mini_last_vid = vid
                if thumb:
                    self._load_image(thumb, self._mini_img, (88, 88))
                else:
                    try:
                        icon_pix = create_icon("music", TEXT_MUTED, 40)
                        self._mini_img.setPixmap(icon_pix.pixmap(40, 40))
                    except Exception as _e:
                        log.debug("Sessiz hata: %s", _e)
        # ── Favori durumu senkronu ──────────────────────────────────────
        is_fav = vid and any(f.get("videoId") == vid for f in self.favorites)
        if self._mini_widget_valid("_mini_fav_btn"):
            icon_name = "heart_on" if is_fav else "heart_off"
            self._mini_fav_btn.setIcon(create_icon(icon_name, get_accent() if is_fav else TEXT_MUTED, 16))
            self._mini_fav_btn.setIconSize(QSize(16, 16))
        try:
            length = max(0, self.player.get_length())
            pos    = max(0, self.player.get_time())
            if self._mini_widget_valid("_mini_seek") and not getattr(self, "_mini_is_dragging", False):
                if self._mini_seek.maximum() != length:
                    self._mini_seek.setRange(0, length)
                self._mini_seek.blockSignals(True)
                self._mini_seek.setValue(max(0, min(pos, length)))
                self._mini_seek.blockSignals(False)
            if self._mini_widget_valid("_mini_vol"):
                self._mini_vol.blockSignals(True)
                effective_vol = 0 if getattr(self, "_muted", False) else int(getattr(self, "_volume", 60))
                self._mini_vol.setValue(effective_vol)
                self._mini_vol.blockSignals(False)
        except Exception:
            if self._mini_widget_valid("_mini_seek"):
                self._mini_seek.setRange(0, 0)
                self._mini_seek.setValue(0)


    def _update_home_now_playing(self):
        """Ana sayfadaki "Şu an çalıyor" bileşenini güncel tutar.

        Bu fonksiyon, ana sayfa oluşturulurken `_add_home_now_playing_widget`
        tarafından saklanan etiket ve resim referanslarını kullanarak
        oynatılan parçaya göre metin ve ikonları senkronize eder. Eğer hiç
        parça çalmıyorsa veya ana sayfadaki widget aktif değilse, herhangi bir
        işlem yapılmaz.
        """
        # Eğer widget referansları tanımlanmadıysa (örneğin ana sayfa hiç
        # açılmadıysa) fonksiyonu sonlandır.
        if not hasattr(self, "_home_now_play_icon"):
            return
        # Çalınan parça mevcut değilse basit bir mesaj göster ve varsayılan
        # ikon/resim kullan
        if not (self.queue and 0 <= self.queue_index < len(self.queue)):
            try:
                self._home_now_play_title.setText(self._tr("mini_player.no_track"))
                self._home_now_play_artist.setText("")
                # ikon ve resim için varsayılan müzik simgesi
                ic = create_icon("music", get_accent(), 20)
                self._home_now_play_icon.setPixmap(ic.pixmap(20, 20))
                img = create_icon("music", TEXT_MUTED, 40)
                self._home_now_play_img.setPixmap(img.pixmap(40, 40))
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
            return
        track = self.queue[self.queue_index]
        # Başlık ve sanatçı adını güncelle
        try:
            title = track.get("title", "") or ""
            self._home_now_play_title.setText(title[:42] + ("…" if len(title) > 42 else ""))
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        try:
            artist = self._artist_str(track) or ""
            self._home_now_play_artist.setText(artist[:32])
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        # Kapak fotoğrafı veya varsayılan simge
        # Daha yüksek çözünürlüklü kare kapak kullanabilmek için `big=True`
        thumb = self._thumb(track, big=True)
        try:
            if thumb:
                # 46x46 boyutunda küçük resim
                self._load_image(thumb, self._home_now_play_img, (46, 46))
            else:
                img = create_icon("music", TEXT_MUTED, 40)
                self._home_now_play_img.setPixmap(img.pixmap(40, 40))
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        # Oynatma/duraklatma ikonunu güncelle
        # Oynatma durumunu belirle. Eğer `_assume_playing_until` gelecekte
        # geçerli bir zaman damgası içeriyorsa, bu yeni şarkı henüz tamamen
        # yüklenmemiş olsa bile "oynatılıyor" durumunu varsayarız. Bu sayede
        # sıradaki şarkıya geçtiğimizde ana sayfadaki ikon hemen "duraklat"
        # görünür. Süre dolduğunda gerçek `player.is_playing()` değerine
        # geri döner.
        try:
            import time as _time
            assume = getattr(self, "_assume_playing_until", 0)
            now    = _time.time()
        except Exception:
            assume = 0
            now    = 0
        if assume and now < assume:
            is_playing = True
        else:
            try:
                is_playing = bool(self.player.is_playing())
            except Exception:
                is_playing = False
        try:
            ico_name = "pause" if is_playing else "play"
            ic = create_icon(ico_name, get_accent(), 20)
            self._home_now_play_icon.setPixmap(ic.pixmap(20, 20))
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
    # ══════════════════════════════════════════════════════════════════════════
    # EQUALİZER
    # ══════════════════════════════════════════════════════════════════════════
