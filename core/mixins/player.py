"""Mixin for Player functionality."""
import logging
import math
import random
import time

log = logging.getLogger("iqtMusic")

from core.constants import TEXT_MUTED
from core.theme import get_accent
from utils.helpers import create_icon

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect
from PySide6.QtCore import QSize, QTimer
import vlc


# ──────────────────────────────────────────────────────────────────────────────
# CROSSFADE / GAPLESS YARDIMCILARI
# ──────────────────────────────────────────────────────────────────────────────

def _ease_in_out(t: float) -> float:
    """Sinüs tabanlı yumuşak geçiş eğrisi (0-1 arası)."""
    return (1 - math.cos(t * math.pi)) / 2


class PlayerMixin:

    def _effective_volume_percent(self, value=None) -> int:
        ui_value = getattr(self, "_volume", 80) if value is None else value
        ui_value = max(0, min(100, int(ui_value)))
        if ui_value <= 0:
            return 0
        # 0 disindaki her slider pozisyonu az da olsa duyulur kalsin.
        # Bu esitlik dusuk degerleri yukari ceker; yine de genel aralik 0-100
        # icinde kalir. Boylece kullanici sesin "bitmesini" ancak sola tam
        # sifira geldiginde hisseder.
        normalized = ui_value / 100.0
        scaled = int(round((normalized ** 0.42) * 92 + 8))
        return max(8, min(100, scaled))

    def _refresh_volume_ui(self):
        ui_value = max(0, min(100, int(getattr(self, "_volume", 80) or 0)))
        is_muted = bool(getattr(self, "_muted", False)) or ui_value <= 0
        if is_muted:
            color = TEXT_MUTED
            tip = self._tr("player.tooltip.volume_unmute", percent=ui_value)
        else:
            color = get_accent()
            tip = self._tr("player.tooltip.volume_mute", percent=ui_value)

        for name, size in (("vol_icon", 14), ("_mini_vol_icon", 10)):
            icon_label = getattr(self, name, None)
            if icon_label is None:
                continue
            try:
                icon_label.setPixmap(create_icon("volume", color, size).pixmap(size, size))
                icon_label.setToolTip(tip)
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
        try:
            mini_vol = getattr(self, "_mini_vol", None)
            if mini_vol is not None:
                mini_vol.blockSignals(True)
                mini_vol.setValue(0 if is_muted else ui_value)
                mini_vol.blockSignals(False)
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)

    def _iter_audio_players(self):
        for pl in (getattr(self, 'player', None), getattr(self, '_player2', None)):
            if pl is not None:
                yield pl

    def _is_collab_guest_active(self) -> bool:
        session = getattr(self, "_collab_session", None)
        if session is None:
            return False
        try:
            return (not session.is_host) and session.state in {session.ST_CONNECTED, session.ST_CONNECTING}
        except Exception:
            return False


    def _compose_audio_filter_chain(self) -> str:
        filters = ["equalizer", "scaletempo"]
        if str(getattr(self, '_loudness_mode', 'light') or 'light').lower() in {"light", "strong"}:
            filters.append("normvol")
        return ":".join(filters)


    def _build_media(self, source_url: str):
        media = self.vlc_inst.media_new(source_url)
        try:
            media.add_option(f":audio-filter={self._compose_audio_filter_chain()}")
            mode = str(getattr(self, '_loudness_mode', 'light') or 'light').lower()
            if mode == 'light':
                media.add_option(':norm-buff-size=20')
                media.add_option(':norm-max-level=1.35')
            elif mode == 'strong':
                media.add_option(':norm-buff-size=30')
                media.add_option(':norm-max-level=1.8')
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        return media


    def _enum_audio_output_devices(self):
        cached = list(getattr(self, '_audio_output_cache', []) or [])
        if cached:
            return cached
        devices = [{"id": "", "name": "Otomatik"}]
        seen = {""}
        player = getattr(self, 'player', None)
        node = None
        try:
            node = player.audio_output_device_enum() if player else None
        except Exception as _e:
            log.debug("Ses cikis cihazi enumerasyonu basarisiz: %s", _e)
            self._audio_output_cache = devices
            return devices

        def _decode(value):
            if value is None:
                return ""
            if isinstance(value, bytes):
                for enc in ('utf-8', 'cp1254', 'latin-1'):
                    try:
                        return value.decode(enc, errors='ignore').strip()
                    except Exception:
                        continue
                return value.decode('utf-8', errors='ignore').strip()
            return str(value).strip()

        cur = node
        guard = 0
        try:
            while cur and guard < 128:
                guard += 1
                try:
                    item = cur.contents
                except Exception:
                    item = cur
                dev_id = _decode(getattr(item, 'device', None) or getattr(item, 'psz_device', None))
                name = _decode(getattr(item, 'description', None) or getattr(item, 'psz_description', None) or dev_id or 'Aygit')
                if dev_id not in seen:
                    devices.append({"id": dev_id, "name": name})
                    seen.add(dev_id)
                cur = getattr(item, 'next', None)
        except Exception as _e:
            log.debug("Ses cikis cihazi listesi okunamadi: %s", _e)
        try:
            releaser = getattr(vlc, 'libvlc_audio_output_device_list_release', None)
            if releaser and node is not None:
                releaser(node)
        except Exception:
            pass
        self._audio_output_cache = devices
        return devices


    def _apply_audio_output_device(self, player=None) -> bool:
        device_id = str(getattr(self, '_audio_output_device', '') or '').strip()
        targets = [player] if player is not None else list(self._iter_audio_players())
        if not device_id:
            applied = False
            for pl in targets:
                if pl is None:
                    continue
                try:
                    pl.audio_output_device_set(None, None)
                    applied = True
                except Exception:
                    pass
            return applied
        applied = False
        for pl in targets:
            if pl is None:
                continue
            try:
                pl.audio_output_device_set(None, device_id)
                applied = True
                continue
            except TypeError:
                pass
            except Exception:
                pass
            try:
                pl.audio_output_device_set(device_id)
                applied = True
            except Exception as _e:
                log.debug("Ses cikis cihazi uygulanamadi: %s", _e)
        return applied


    def _change_volume(self, delta: int):
        target = max(0, min(100, int(getattr(self, '_volume', 80)) + int(delta)))
        self._set_volume(target)
        self._save_settings()


    def toggle_mute(self):
        new_state = not bool(getattr(self, '_muted', False))
        self._muted = new_state
        for pl in self._iter_audio_players():
            try:
                pl.audio_set_mute(new_state)
            except Exception:
                try:
                    pl.audio_toggle_mute()
                except Exception as _e:
                    log.debug("Sessiz hata: %s", _e)
        if not new_state:
            out_volume = self._effective_volume_percent()
            if not getattr(self, '_cf_active', False):
                for pl in self._iter_audio_players():
                    try:
                        pl.audio_set_volume(out_volume)
                    except Exception as _e:
                        log.debug("Sessiz hata: %s", _e)
            self._cf_target_vol = out_volume
        self._refresh_volume_ui()
        try:
            self.sig.notify.emit('Ses kapatildi' if new_state else 'Ses acildi')
        except Exception:
            pass

    def _seek_relative(self, delta_sec: int):
        try:
            delta_ms = int(delta_sec) * 1000
        except Exception:
            return
        if not self.player:
            return
        try:
            current = max(0, int(self.player.get_time()))
        except Exception:
            current = int(getattr(self, '_pending_seek_ms', 0) or 0)
        try:
            length = max(0, int(self.player.get_length()))
        except Exception:
            length = max(0, int(getattr(self, 'total_dur', 0) or 0))
        target = max(0, current + delta_ms)
        if length > 0:
            target = min(target, length)
        self._seek_commit(target)


    def _play(self, track: dict, force_radio=False):
        self._play_request_id += 1
        self._auto_next_token += 1
        self.target_vid = track.get("videoId", "")
        request_id = self._play_request_id
        self.player_bar.show()
        # NOT: _cf_triggered'i burada sıfırlamıyoruz.
        # _update_seek crossfade penceresindeyken tekrar tetiklemeyi
        # engellemek için _cf_active bayrağı kullanılıyor.

        if self.queue and 0 <= self.queue_index < len(self.queue):
            self._shuffle_buf.append(self.queue_index)

        self.lbl_title.setText(track.get("title", "")[:32])
        self._set_player_artist_label(track)
        # Yeni şarkı yüklenene kadar eski süre gösterilmesin
        self.total_dur = 0
        self.lbl_cur.setText("0:00")
        self.lbl_end.setText("0:00")
        self.seek_bar.blockSignals(True)
        self.seek_bar.setRange(0, 1)
        self.seek_bar.setValue(0)
        self.seek_bar.blockSignals(False)
        self._set_main_play_icon(True)
        self._update_fav_btn(track)
        self._reset_listen_session(track)
        self._discord_update(track)
        try:
            toast_vid = str(track.get("videoId", "") or "")
            if toast_vid and toast_vid != getattr(self, "_last_track_toast_vid", ""):
                self._last_track_toast_vid = toast_vid
                self.sig.notify.emit({
                    "title": track.get("title", "") or "?",
                    "message": self._artist_str(track),
                    "icon": "music",
                    "cover_url": self._thumb(track, big=True) or "",
                })
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)

        try:
            self._lyrics_refresh_for_track(track)
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)

        if force_radio:
            self._net_pool.submit(self._fetch_radio, track.get("videoId", ""), request_id)
        # Başlatılacak şarkı için bir sonraki şarkıyı yüklemeyi ve ses akışını
        # arka planda işlemek için yükleme iş parçacığı sıraya alınır.
        self._stream_pool.submit(self._load_audio, track, False, request_id)
        # Güncel parça ve oynatma durumuna bağlı arayüzdeki bileşenleri anında
        # güncellemek için sinyal gönder. Aksi takdirde albüm kapağı ve
        # oynat/duraklat ikonları bir süre eski durumda kalabiliyor.
        try:
            self.sig.player_ui_update.emit()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        try:
            if self.queue and 0 <= self.queue_index < len(self.queue):
                self._prime_stream_urls(
                    self.queue[self.queue_index + 1:self.queue_index + 4],
                    limit=3,
                )
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        try:
            if getattr(self, "current_page", "") == "queue":
                self._queue_refresh_state = None
                QTimer.singleShot(
                    0,
                    lambda rid=request_id: (
                        self._refresh_queue_page_state(force=True)
                        if getattr(self, "current_page", "") == "queue"
                        and rid == self._play_request_id
                        else None
                    )
                )
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)

        # Bir parça çalmaya başlandığında oynatma durumu henüz "player.is_playing()"
        # tarafından doğru şekilde yansıtılmayabilir. Özellikle yeni bir şarkıya
        # geçtiğimizde arayüzdeki "play/pause" ikonunun anında "pause" olarak
        # görünmesi beklenir. Bu yardımcı değişken, `_update_home_now_playing`
        # fonksiyonunda birkaç saniye boyunca oynatma durumunu varsayılan olarak
        # "oynatılıyor" kabul etmek için kullanılır. Değer zaman damgası
        # biçimindedir; süre dolunca gerçek duruma geri döner.
        try:
            import time as _time
            self._assume_playing_until = _time.time() + 5
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)

        # Beraber Dinle: host ise yeni şarkıyı guest'lere bildir
        try:
            self._collab_emit_track(track)
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)


    def _load_audio(self, track: dict, bypass_cache=False, request_id=None):
        vid = track.get("videoId", "")
        if request_id is None:
            request_id = self._play_request_id
        if vid != self.target_vid or request_id != self._play_request_id:
            return
        try:
            thumb = self._thumb(track, big=True)
            if thumb:
                self._load_image(thumb, self.img_cover, (60, 60))
            if not vid:
                raise ValueError("VideoId yok")
            url = self._resolve_stream_url(vid, bypass_cache=bypass_cache)
            if not url:
                raise RuntimeError("URL alınamadı")
            if vid != self.target_vid or request_id != self._play_request_id:
                return
            self.sig.audio_url_ready.emit(dict(track), url, request_id)
        except Exception as e:
            log.error("Ses yüklenemedi (%s): %s", vid, e)
            self.sig.player_ui_update.emit()

    # ══════════════════════════════════════════════════════════════════════════
    # CROSSFADE
    # ══════════════════════════════════════════════════════════════════════════

    def _start_resolved_audio(self, track: dict, url: str, request_id: int):
        vid = str((track or {}).get("videoId", "") or "")
        if not url or not vid or request_id != self._play_request_id or vid != self.target_vid:
            return
        hold_for_host = (
            self._is_collab_guest_active()
            and not bool((track or {}).get("_collab_autoplay", True))
            and getattr(self, "_collab_host_playing", True) is False
        )
        should_autoplay = not hold_for_host

        cf_dur = getattr(self, '_crossfade_duration', 0)
        already_playing = False
        try:
            already_playing = bool(self.player.is_playing())
        except Exception:
            pass

        if should_autoplay and cf_dur > 0 and already_playing:
            self._cf_pending_rid = request_id
            self._cf_pending_vid = vid
            self.sig.crossfade_start.emit(url)
        else:
            with self._state_lock:
                if getattr(self, '_cf_active', False):
                    try:
                        self._cf_timer.stop()
                    except Exception:
                        pass
                    try:
                        self._player2.stop()
                    except Exception:
                        pass
                    self._cf_active = False

                self.player.stop()
                media = self._build_media(url)
                self.player.set_media(media)
                if should_autoplay:
                    self.player.play()
                try:
                    self.player.set_equalizer(self.eq_inst)
                except Exception as _e:
                    log.debug("Sessiz hata: %s", _e)
                try:
                    self.player.audio_set_volume(self._effective_volume_percent())
                    self.player.audio_set_mute(bool(getattr(self, '_muted', False)))
                except Exception as _e:
                    log.debug("Sessiz hata: %s", _e)
                self.sig.audio_output_apply_deferred.emit(220, request_id)

        rate = getattr(self, '_playback_rate', 1.0)
        if rate != 1.0 and not (should_autoplay and cf_dur > 0 and already_playing):
            self.sig.rate_apply_deferred.emit(rate, request_id)
        else:
            self.sig.audio_output_apply_deferred.emit(280, request_id)

        if (
            self._pending_restore_pos is not None
            and vid
            and vid == self._pending_restore_vid
        ):
            self.sig.restore_pos_deferred.emit(vid, request_id)
        pending_collab_seek = int(getattr(self, "_collab_pending_seek_ms", -1) or -1)
        if pending_collab_seek >= 0:
            QTimer.singleShot(
                260,
                lambda pos=pending_collab_seek, rid=request_id, autoplay=should_autoplay: (
                    self.player.set_time(pos)
                    if rid == self._play_request_id and (autoplay or not self.player.is_playing())
                    else None
                ),
            )
        try:
            session = getattr(self, "_collab_session", None)
            if should_autoplay and session is not None and session.is_host and session.is_connected:
                self._collab_pending_host_broadcast_rid = request_id
                QTimer.singleShot(650, lambda rid=request_id: self._collab_emit_host_loaded_play(rid))
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        self.sig.player_ui_update.emit()
        self._prefetch_next()

    def _start_crossfade(self, url: str):
        """İkinci VLC örneğini başlatarak crossfade geçişi başlatır."""
        # Stale-request guard: sinyal gönderildikten sonra farklı bir şarkı
        # başlatılmış olabilir — bu durumda crossfade'i iptal et.
        if (getattr(self, '_cf_pending_rid', None) != self._play_request_id
                or getattr(self, '_cf_pending_vid', None) != self.target_vid):
            return

        cf_dur = getattr(self, '_crossfade_duration', 3)
        self._cf_active      = True
        self._cf_elapsed     = 0
        self._cf_interval    = 60          # ms — timer aralığı
        self._cf_duration_ms = max(500, int(cf_dur * 1000))
        target_vol           = self._effective_volume_percent()

        try:
            # _player2 daha önce kullanılmamış olabilir — stop() güvenli çağrı
            try:
                self._player2.stop()
            except Exception:
                pass
            self._player2.set_media(self._build_media(url))
            try:
                self._player2.set_equalizer(self.eq_inst)
            except Exception:
                pass
            rate = getattr(self, '_playback_rate', 1.0)
            if rate != 1.0:
                try:
                    self._player2.set_rate(rate)
                except Exception:
                    pass
            self._player2.audio_set_volume(0)
            try:
                self._player2.audio_set_mute(bool(getattr(self, '_muted', False)))
            except Exception:
                pass
            self._player2.play()
            try:
                self._apply_audio_output_device(self._player2)
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
        except Exception as e:
            log.error("Crossfade player2 başlatılamadı: %s", e)
            self._cf_active = False
            # Normal şekilde devam et
            with self._state_lock:
                self.player.stop()
                self.player.set_media(self._build_media(url))
                self.player.play()
                try:
                    self.player.audio_set_volume(target_vol)
                except Exception:
                    pass
                try:
                    self.player.audio_set_mute(bool(getattr(self, '_muted', False)))
                except Exception:
                    pass
                try:
                    self._apply_audio_output_device(self.player)
                except Exception as _e:
                    log.debug("Sessiz hata: %s", _e)
            return

        self._cf_target_vol = target_vol
        try:
            self._cf_timer.start(self._cf_interval)
        except Exception as e:
            log.error("Crossfade timer başlatılamadı: %s", e)
            self._cf_active = False

    def _cf_tick(self):
        """Crossfade zamanlayıcı tiki — ses seviyelerini kademeli geçirir."""
        if not getattr(self, '_cf_active', False):
            return

        self._cf_elapsed += self._cf_interval
        progress = min(self._cf_elapsed / max(1, self._cf_duration_ms), 1.0)
        smooth   = _ease_in_out(progress)

        vol1 = int(self._cf_target_vol * (1.0 - smooth))
        vol2 = int(self._cf_target_vol * smooth)

        try:
            self.player.audio_set_volume(max(0, vol1))
        except Exception:
            pass
        try:
            self._player2.audio_set_volume(max(0, vol2))
        except Exception:
            pass

        if progress >= 1.0:
            self._cf_timer.stop()
            # Eski player'ı durdur, player2 ana player olsun
            try:
                self.player.stop()
            except Exception:
                pass
            self.player   = self._player2
            self._player2 = self.vlc_inst.media_player_new()
            try:
                self.player.audio_set_volume(self._cf_target_vol)
            except Exception:
                pass
            try:
                self.player.set_equalizer(self.eq_inst)
            except Exception:
                pass
            try:
                self.player.audio_set_mute(bool(getattr(self, '_muted', False)))
            except Exception:
                pass
            try:
                self._apply_audio_output_device(self.player)
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
            self._cf_active    = False
            self._cf_triggered = False   # bir sonraki şarkı için sıfırla
            try:
                self.sig.player_ui_update.emit()
            except Exception:
                pass

    # ══════════════════════════════════════════════════════════════════════════
    # OYNATMA HIZI (scaletempo)
    # ══════════════════════════════════════════════════════════════════════════

    def _set_playback_rate(self, rate: float):
        """Oynatma hızını ayarlar. Scaletempo filtresi ile pitch korunur."""
        rate = max(0.5, min(2.0, float(rate)))
        self._playback_rate = rate

        # Çalınan player'a uygula (şu an çalıyorsa direkt, yoksa yoksay)
        def _apply():
            try:
                if self.player.is_playing():
                    self.player.set_rate(rate)
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
            # Aktif crossfade varsa player2'ye de uygula
            if getattr(self, '_cf_active', False):
                try:
                    self._player2.set_rate(rate)
                except Exception:
                    pass

        _apply()
        # Bazen VLC rate'i ilk çağrıda reddeder; 200ms sonra tekrar dene
        QTimer.singleShot(200, _apply)

        self._save_settings()
        try:
            if hasattr(self, '_speed_btn'):
                is_fast  = abs(rate - 1.0) > 0.01
                ico_clr  = get_accent() if is_fast else TEXT_MUTED
                self._speed_btn.setIcon(create_icon("settings", ico_clr, 16))
                self._speed_btn.setIconSize(QSize(16, 16))
                self._speed_btn.setToolTip(f"Oynatma ayarlari • {rate:.2g}×")
        except Exception:
            pass


    # ── Ana-thread slot'ları (worker thread'den gelen signal'lar için) ────────

    def _deferred_rate_apply(self, rate: float, request_id: int):
        """Ana thread'de VLC rate'i gecikmeli uygular (signal slot)."""
        def _apply():
            if request_id != self._play_request_id:
                return
            try:
                self.player.set_rate(rate)
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
            try:
                self._apply_audio_output_device(self.player)
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)

        QTimer.singleShot(280, _apply)

    def _deferred_audio_output_apply(self, delay_ms: int, request_id: int):
        """Ana thread'de ses cikis cihazini gecikmeli uygular."""
        def _apply():
            if request_id != self._play_request_id:
                return
            try:
                self._apply_audio_output_device(self.player)
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)

        QTimer.singleShot(max(0, int(delay_ms)), _apply)

    def _deferred_restore_pos(self, vid: str, request_id: int):
        """Ana thread'de seek pozisyonunu gecikmeli geri yükler (signal slot)."""
        QTimer.singleShot(450, lambda v=vid, rid=request_id: self._restore_pos(
            expected_vid=v, request_id=rid
        ))

    def _prefetch_next(self):
        if not self.queue:
            return
        nxt = -1
        if self._is_collab_guest_active():
            if self.queue_index < len(self.queue) - 1:
                nxt = self.queue_index + 1
        elif self.shuffle_on:
            cands = [i for i in range(len(self.queue)) if i not in self._shuffle_buf]
            if cands:
                nxt = random.choice(cands)
        elif self.queue_index < len(self.queue) - 1:
            nxt = self.queue_index + 1
        elif self.repeat_mode == 1:
            nxt = 0
        if nxt == -1:
            return
        nt  = self.queue[nxt]
        self._prefetch_stream(nt)
        if self._is_collab_guest_active():
            return
        if getattr(self, '_next_preload_on', True):
            try:
                self._media_cache.queue(nt, self._ydl_opts)
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)


    def _sync_player_ui(self):
        """Güncel parçaya göre player bar ve mini player arayüzünü senkronize et.

        Bu metod, oynatıcı durumundaki değişiklikleri UI'da yansıtır. Önceden
        yalnızca play/pause ikonunu güncelliyordu; ancak parça değiştirildiğinde
        kapak görselinin yenilenmemesi sorununa yol açıyordu. Artık mevcut
        parçanın küçük resmini hem ana oynatıcı çubuğunda hem de mini
        oynatıcıda yeniden yükleyerek albüm kapağının güncellenmesini
        sağlıyoruz. Ayrıca mini oynatıcı açıksa onun da güncellenmesi
        sürdürülüyor.
        """
        # Güncel parça bilgilerine eriş
        if self.queue and 0 <= self.queue_index < len(self.queue):
            track = self.queue[self.queue_index]
            # Albüm kapağını yükle
            try:
                thumb = self._thumb(track, big=True)
                if thumb:
                    # Yeni resim yüklenirken eski kapak görünmesin diye
                    # geçici olarak varsayılan bir müzik simgesi gösteriyoruz.
                    try:
                        placeholder = create_icon("music", TEXT_MUTED, 48)
                        self.img_cover.setPixmap(placeholder.pixmap(48, 48))
                    except Exception:
                        self.img_cover.clear()
                    # Asenkron yüklemeye başla
                    self._load_image(thumb, self.img_cover, (60, 60))
                else:
                    # Varsayılan müzik simgesi kullan
                    fall_pix = create_icon("music", TEXT_MUTED, 48)
                    self.img_cover.setPixmap(fall_pix.pixmap(48, 48))
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
        # Oynatma düğmesi durumunu güncelle
        # Çalınıyor mu kontrol et ve ikon+boyutu ayarla
        try:
            playing = bool(self.player.is_playing())
        except Exception:
            playing = False
        self._set_main_play_icon(playing)
        # Mini oynatıcı açıksa içeriği senkronize et
        if hasattr(self, "_mini_win") and self._mini_win.isVisible():
            self._update_mini()

        # Ana sayfa "Şu an çalıyor" bileşenini güncelle
        try:
            self._update_home_now_playing()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)

        # Sıradaki şarkılar sayfası açıksa yenile (çalınan şarkı güncellenir)
        if getattr(self, "current_page", "") == "queue":
            try:
                self._queue_refresh_state = None
                self._refresh_queue_page_state(force=True)
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)

    # ══════════════════════════════════════════════════════════════════════════
    # SEEK & VOLUME
    # ══════════════════════════════════════════════════════════════════════════


    def _update_seek(self):
        if self.is_dragging or time.time() < self._seek_cooldown_until:
            return
        try:
            length  = max(0, int(self.player.get_length()))
            current = max(0, int(self.player.get_time()))
        except Exception:
            return
        if length <= 0:
            return
        self.total_dur = length

        if self.seek_bar.maximum() != length:
            self.seek_bar.setRange(0, length)
        self.seek_bar.blockSignals(True)
        self.seek_bar.setValue(min(current, length))
        self.seek_bar.blockSignals(False)
        if hasattr(self, "_mini_seek") and not getattr(self, "_mini_is_dragging", False):
            if self._mini_seek.maximum() != length:
                self._mini_seek.setRange(0, length)
            self._mini_seek.blockSignals(True)
            self._mini_seek.setValue(min(current, length))
            self._mini_seek.blockSignals(False)
        self.lbl_cur.setText(self._fmt(current))
        self.lbl_end.setText(self._fmt(length))


    def _check_state(self):
        with self._state_lock:
            state = self.player.get_state()
        if state != vlc.State.Ended:
            self._ended_transition_active = False
        self._tick_listen_stats(state)
        if state == vlc.State.Playing:
            self._set_main_play_icon(True)
        elif state == vlc.State.Paused:
            self._set_main_play_icon(False)
        if getattr(self, "current_page", "") == "queue":
            try:
                self._queue_refresh_state = None
                self._refresh_queue_page_state(force=True)
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
        if state == vlc.State.Ended:
            if getattr(self, "_ended_transition_active", False):
                return
            # Manuel bir şarkı seçimi 4 sn içindeyse otomatik geçişi atla (yarış koşulu koruması)
            try:
                import time as _t
                if _t.monotonic() - getattr(self, "_manual_play_ts", 0.0) < 4.0:
                    return
            except Exception:
                pass
            self._ended_transition_active = True
            if self._is_collab_guest_active():
                try:
                    self._stop_collab_fast_resync_timer()
                except Exception:
                    pass
                try:
                    self._stop_collab_drift_timer()
                except Exception:
                    pass
                return
            # Crossfade player2 üzerinde fade devam ediyorsa —
            # player1'in Ended sinyalini yoksay, cf_tick yönetiyor.
            if getattr(self, '_cf_active', False):
                return
            # Tekrar modu
            if self.repeat_mode == 2:
                self.force_play(self.queue[self.queue_index])
                return
            # _cf_triggered=True ama _cf_active=False:
            #   → gapless/crossfade şarkı bitene kadar başlayamadı,
            #     _load_audio hâlâ çalışıyor. 1 kez daha geçiş yaptığımızda
            #     çift geçiş olmasın diye triggered'ı sıfırla ve normal devam et.
            self._cf_triggered = False
            self.next_song(auto=True)
        if state == vlc.State.Error:
            if self.queue and 0 <= self.queue_index < len(self.queue):
                vid = self.queue[self.queue_index].get("videoId", "")
                if vid:
                    r = self._retry_guard.get(vid, 0)
                    if r < 2:
                        self._retry_guard[vid] = r + 1
                        self._url_cache.delete(vid)
                        self._stream_pool.submit(
                            self._load_audio,
                            self.queue[self.queue_index], True, self._play_request_id)
                    else:
                        self.next_song(auto=True)


    def _update_visualizer(self):
        # Pencere minimize veya gizliyse CPU harcamadan çık
        try:
            if self.isMinimized() or not self.isVisible():
                return
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        try:
            playing = bool(self.player.is_playing())
        except Exception:
            playing = False

        eff = self.img_cover.graphicsEffect()
        if not playing:
            if eff and self._vis_last_blur:
                next_blur = max(0.0, float(self._vis_last_blur) * 0.72 - 0.35)
                if next_blur <= 0.2:
                    next_blur = 0.0
                eff.setBlurRadius(next_blur)
                self._vis_last_blur = next_blur
            return

        self._vis_phase += 0.065
        wave = (math.sin(self._vis_phase) + 1.0) * 0.5
        target_blur = 7.0 + wave * 10.0
        if eff is None:
            eff = QGraphicsDropShadowEffect(self.img_cover)
            eff.setOffset(0, 0)
            self.img_cover.setGraphicsEffect(eff)
        glow_color = QColor(get_accent())
        glow_color.setAlpha(120 + int(wave * 55))
        eff.setColor(glow_color)
        current_blur = float(self._vis_last_blur or 0.0)
        next_blur = current_blur + (target_blur - current_blur) * 0.28
        eff.setBlurRadius(next_blur)
        self._vis_last_blur = next_blur


    def _seek_start(self):
        self.is_dragging     = True
        self._pending_seek_ms = int(self.seek_bar.value())


    def _seek_end(self):
        self._seek_commit(int(self.seek_bar.value()))
        self.is_dragging = False


    def _seek_move(self, v):
        self._pending_seek_ms = int(v)
        self.lbl_cur.setText(self._fmt(int(v)))


    def _seek_commit(self, v):
        target = int(v)
        try:
            length = max(int(self.player.get_length()), int(self.total_dur or 0))
        except Exception:
            length = int(self.total_dur or 0)
        if length <= 0:
            self.is_dragging = False
            return
        target = max(0, min(target, max(0, length - 250)))
        self._seek_cooldown_until = time.time() + 0.35
        try:
            rc = self.player.set_time(target)
            if rc == -1:
                self.player.set_position(target / max(1, length))
        except Exception:
            try:
                self.player.set_position(target / max(1, length))
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
        self.seek_bar.blockSignals(True)
        self.seek_bar.setRange(0, length)
        self.seek_bar.setValue(target)
        self.seek_bar.blockSignals(False)
        self.lbl_cur.setText(self._fmt(target))
        self.lbl_end.setText(self._fmt(length))
        if hasattr(self, "_mini_seek"):
            self._mini_seek.blockSignals(True)
            self._mini_seek.setRange(0, length)
            self._mini_seek.setValue(target)
            self._mini_seek.blockSignals(False)
        QTimer.singleShot(180, self._update_seek)
        self.is_dragging = False

        # Beraber Dinle: host ise seek olayını guest'lere bildir
        try:
            self._collab_emit_seek(target)
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)

        # Seek sonrası Discord Presence'i senkronize et. Şarkıyı ileri/geri
        # sardıktan sonra zaman çizelgesi güncel kalsın diye Rich Presence'i
        # hemen güncelleriz.
        try:
            if getattr(self, "_discord_connected", False) and self.queue and self.queue_index != -1:
                self._discord_update(self.queue[self.queue_index])
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)


    def _mini_seek_start(self):
        self._mini_is_dragging = True


    def _mini_seek_end(self):
        if hasattr(self, "_mini_seek"):
            self._mini_seek_commit(int(self._mini_seek.value()))
        self._mini_is_dragging = False


    def _mini_seek_move(self, v):
        if hasattr(self, "_mini_status"):
            self._mini_status.setText(
                f"{self._fmt(int(v))} / {self._fmt(int(self.total_dur or 0))}")


    def _mini_seek_commit(self, v):
        self._seek_commit(int(v))
        if hasattr(self, "_mini_seek"):
            self._mini_seek.blockSignals(True)
            self._mini_seek.setValue(int(v))
            self._mini_seek.blockSignals(False)


    def _set_volume(self, v):
        self._last_vol_upd = time.time()
        self._volume = max(0, min(100, int(v)))
        if self._volume > 0 and getattr(self, "_muted", False):
            self._muted = False
        out_volume = self._effective_volume_percent()
        # Crossfade aktifse anlık fade'i bozmayalım; sadece hedef volume'u güncelle.
        if not getattr(self, '_cf_active', False):
            try:
                self.player.audio_set_volume(out_volume)
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
        for pl in self._iter_audio_players():
            try:
                pl.audio_set_mute(bool(getattr(self, '_muted', False)))
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
        self._cf_target_vol = out_volume
        for sl_name in ("vol_slider", "_mini_vol"):
            sl = getattr(self, sl_name, None)
            if sl and sl.value() != self._volume:
                sl.blockSignals(True)
                sl.setValue(self._volume)
                sl.blockSignals(False)
        self._refresh_volume_ui()

    # ══════════════════════════════════════════════════════════════════════════
    # NAVİGASYON (oynatma)
    # ══════════════════════════════════════════════════════════════════════════


    def next_song(self, auto=False):
        # Kullanıcı manuel ileri geçişi: crossfade durumunu temizle
        if not auto:
            self._cf_triggered = False
            if getattr(self, '_cf_active', False):
                try:
                    self._cf_timer.stop()
                    self._player2.stop()
                except Exception:
                    pass
                self._cf_active = False
        if self._is_collab_guest_active():
            if self.queue_index < len(self.queue) - 1:
                self.queue_index += 1
                self._play(self.queue[self.queue_index])
            return
        if self.shuffle_on and self.queue:
            cands = [i for i in range(len(self.queue)) if i not in self._shuffle_buf]
            if not cands:
                cands = list(range(len(self.queue)))
            self.queue_index = random.choice(cands)
            self._play(self.queue[self.queue_index])
        elif self.queue_index < len(self.queue) - 1:
            self.queue_index += 1
            self._play(self.queue[self.queue_index])
        elif auto and self.queue and self.repeat_mode == 1:
            self.queue_index = 0
            self._play(self.queue[0])
        elif auto and self.queue and getattr(self, "_queue_artist_lock", False):
            # Sanatçı kilidi: kuyruk bitti, radio açılmasın; başa dön (tekrar modu gibi)
            self.queue_index = 0
            self._play(self.queue[0])
        elif auto and self.queue:
            self._auto_next_token += 1
            token      = self._auto_next_token
            seed_vid   = self.queue[-1].get("videoId", "")
            request_id = self._play_request_id
            self._net_pool.submit(self._request_auto_next_from_radio, token, seed_vid, request_id)


    def prev_song(self):
        # Kullanıcı geri geçişi: crossfade durumunu temizle
        self._cf_triggered = False
        if getattr(self, '_cf_active', False):
            try:
                self._cf_timer.stop()
                self._player2.stop()
            except Exception:
                pass
            self._cf_active = False
        if self.queue_index > 0:
            self.queue_index -= 1
            self._play(self.queue[self.queue_index])
        elif self.queue:
            self.queue_index = len(self.queue) - 1
            self._play(self.queue[self.queue_index])


    def toggle_play(self):
        # Oynatma / duraklatma durumunu değiştir ve ikonları güncelle
        try:
            currently_playing = bool(self.player.is_playing())
        except Exception:
            currently_playing = False

        current_track = None
        if self.queue and 0 <= self.queue_index < len(self.queue):
            current_track = self.queue[self.queue_index]

        if currently_playing:
            try:
                self.player.pause()
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
            # Oynat düğmesi ikonunu ayarla
            self._set_main_play_icon(False)
        else:
            media = None
            try:
                media = self.player.get_media()
            except Exception:
                media = None

            # Uygulama açılışında son parça bar'da görünürken VLC tarafında
            # henüz media bağlanmamış olabilir. Bu durumda düz `player.play()`
            # sessizce başarısız olur; mevcut kuyruğu gerçek `_play(...)`
            # akışından başlatırız.
            if current_track and (
                media is None
                or not self.target_vid
                or self.target_vid != current_track.get("videoId", "")
            ):
                self._play(current_track, force_radio=False)
            else:
                try:
                    self.player.play()
                except Exception as _e:
                    log.debug("Sessiz hata: %s", _e)
            # Duraklat düğmesi ikonunu ayarla
            self._set_main_play_icon(True)
        # Oynatma durumundaki değişikliğin tüm arayüzde yansıması için sinyal gönder
        try:
            self.sig.player_ui_update.emit()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)

        # Play/pause değişiminden sonra Discord Presence'i güncelle. Böylece
        # küçük ikon ve süre bilgisi hemen güncellenir.
        try:
            if getattr(self, "_discord_connected", False) and self.queue and self.queue_index != -1:
                self._discord_update(self.queue[self.queue_index])
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)

        # Beraber Dinle: host ise play/pause olayını guest'lere bildir
        try:
            if currently_playing:
                self._collab_emit_pause()
            else:
                self._collab_emit_play()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)


    def _play_all(self, tracks: list):
        if not tracks:
            return
        self._queue_artist_lock = False   # radio/autoplay serbest
        self.queue       = list(tracks)
        self.queue_index = 0
        self._radio_queue_vids.clear()
        self._play(self.queue[0])

    def _play_artist_only(self, tracks: list):
        """Sadece bu sanatçının şarkılarını oynat — kuyruk bitince radio yok."""
        if not tracks:
            return
        self._queue_artist_lock = True    # kuyruk bitince dur, radio açılmasın
        self.queue       = list(tracks)
        self.queue_index = 0
        self._radio_queue_vids.clear()
        self._play(self.queue[0])

    # ══════════════════════════════════════════════════════════════════════════
    # KUYRUK
    # ══════════════════════════════════════════════════════════════════════════
