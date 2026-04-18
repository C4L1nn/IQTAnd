# iqtMusic Android Foundation

Bu klasor, masaustu PySide6 uygulamasindan bagimsiz ilerleyecek Android tabanini icerir.

Secilen teknoloji:
- Kotlin
- Jetpack Compose
- Navigation Compose
- Media3 tabanli player service temeli

Bu ilk iskelette hazirlananlar:
- Android Studio ile acilabilecek cok-modullu olmayan temel proje yapisi
- Ana gezinme kabugu
- Home, Search, Playlists, Collab ve Stats ekranlari
- DataStore ustunde saklanan lokal kutuphane state'i
- Playlist detay sayfasi, queue state akisi ve listeye parca ekle-cikar akislari
- Gelecekte arka planda oynatma icin Media3 service temeli

Hedeflenen masaustu esitligi:
- Korunacak: playlist mantigi, favoriler, gecmis, istatistikler, collab protokolu, tema dili
- Android icin yeniden yazilacak: player, download manager, bildirim, background playback, deep link
- Android'de olmayacak: tray, global hotkey, mevcut Discord RPC, frameless pencere davranislari

Ilk acilis:
1. Android Studio ile `android-app` klasorunu ac.
2. Gradle sync calistir.
3. Gerekirse Android Studio'dan Gradle wrapper uret.
4. `app` modulunu emulatorde ya da cihazda calistir.

Sonraki mantikli adimlar:
1. Media3 ile stream playback'i view model state'i ile baglamak
2. MQTT tabanli collab protokolunu Android'a tasimak
3. Downloads icin WorkManager + foreground service kurmak
4. Desktop ile ortaklasabilecek JSON model/DTO katmanini ayirmak
5. Kalici veriyi remote API ve senkronizasyon katmaniyla beslemek
