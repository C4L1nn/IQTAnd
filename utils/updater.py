"""iqtMusic — Otomatik Güncelleme Sistemi







Asset öncelik sırası (GitHub Release):



  1. *patch*.zip  → sadece değişen dosyalar, PowerShell ile yerinde yazar (küçük)



  2. *Kurulum*.exe / *Setup*.exe  → tam kurulum (yeni kullanıcılar / fallback)



"""



from __future__ import annotations







import hashlib



import json



import logging



import os



import sys



import tempfile



import threading



import time



import urllib.request



from typing import Optional







from PySide6.QtCore import Qt, QThread, Signal



from PySide6.QtWidgets import (



    QApplication, QDialog, QFrame, QHBoxLayout,



    QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget,



)







log = logging.getLogger("iqtMusic.updater")







GITHUB_OWNER = "C4L1nn"



GITHUB_REPO  = "iqtMusic"



_PATCH_MANIFEST_NAME = "__iqtm_patch_manifest__.json"



_UPDATE_HEADERS = {



    "User-Agent": "iqtMusic-Updater/1.0",



    "Accept": "application/vnd.github+json",



}











# â”€â”€ Versiyon karşılaştırma â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€







def _version_tuple(v: str) -> tuple[int, ...]:



    try:



        return tuple(int(x) for x in v.strip().lstrip("v").split("."))



    except Exception:



        return (0,)











def _asset_sha256(asset: dict) -> str:



    digest = str(asset.get("digest", "") or "").strip()



    if not digest:



        return ""



    if ":" in digest:



        algo, _, digest = digest.partition(":")



        if algo.strip().lower() != "sha256":



            return ""



    value = digest.strip().lower()



    if len(value) != 64:



        return ""



    if any(ch not in "0123456789abcdef" for ch in value):



        return ""



    return value











def _release_asset_info(asset: dict, version: str, notes: str, mode: str) -> Optional[dict]:



    sha256 = _asset_sha256(asset)



    if not sha256:



        log.warning(



            "SHA-256 digest bulunamadi, update asset atlandi: %s",



            asset.get("name", ""),



        )



        return None



    return {



        "version": version,



        "asset_name": str(asset.get("name", "") or "").strip(),



        "download_url": asset["browser_download_url"],



        "size": int(asset.get("size", 0) or 0),



        "notes": notes,



        "mode": mode,



        "sha256": sha256,



    }











# â”€â”€ GitHub API kontrolü â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€







def check_for_update(current_version: str, timeout: float = 4.0) -> Optional[dict]:



    """



    GitHub Releases API'den son sürümü kontrol eder.



    Yeni sürüm varsa bilgi dict'i döner, yoksa None.







    Asset önceliği:



      1. *patch*.zip  → hızlı yerinde güncelleme



      2. *.exe        → tam kurulum (fallback)



    """



    try:



        url = (



            f"https://api.github.com/repos/"



            f"{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"



        )



        req = urllib.request.Request(url, headers=_UPDATE_HEADERS)



        with urllib.request.urlopen(req, timeout=timeout) as resp:



            data = json.loads(resp.read())







        latest = data.get("tag_name", "").lstrip("v").strip()



        if not latest or _version_tuple(latest) <= _version_tuple(current_version):



            return None







        assets = data.get("assets", [])



        notes = data.get("body", "")







        # Önce patch.zip ara



        for asset in assets:



            name = asset.get("name", "").lower()



            if "patch" in name and name.endswith(".zip"):



                info = _release_asset_info(asset, latest, notes, "patch")



                if info is not None:



                    return info







        # Yoksa tam kurulum exe



        for asset in assets:



            name = asset.get("name", "").lower()



            if name.endswith(".exe"):



                info = _release_asset_info(asset, latest, notes, "installer")



                if info is not None:



                    return info







        if assets:



            log.warning(



                "Yeni surum bulundu ama dogrulanabilir update asset yok: v%s",



                latest,



            )







    except Exception as exc:



        log.debug("Guncelleme kontrolu basarisiz: %s", exc)



    return None











def check_for_update_async(current_version: str, timeout: float = 4.0) -> Optional[dict]:



    """



    Arka planda kontrol eder; Qt event döngüsünü bloke etmez.



    Splash animasyonu devam ederken güvenle çağrılabilir.



    """



    result: list[Optional[dict]] = [None]



    done = threading.Event()







    def _worker():



        result[0] = check_for_update(current_version, timeout)



        done.set()







    threading.Thread(target=_worker, daemon=True).start()



    deadline = time.monotonic() + timeout + 0.5



    while not done.is_set() and time.monotonic() < deadline:



        QApplication.processEvents()



        time.sleep(0.05)



    return result[0]











# â”€â”€ İndirme thread'i â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€







class _DownloadThread(QThread):



    progress = Signal(int, int)   # (indirilen_byte, toplam_byte)



    finished = Signal(str, str)   # (temp dosya yolu, sha256)



    error    = Signal(str)







    def __init__(self, url: str, parent=None):



        super().__init__(parent)



        self._url = url







    def run(self):



        tmp_path = ""



        try:



            req = urllib.request.Request(



                self._url, headers={"User-Agent": "iqtMusic-Updater/1.0"}



            )



            with urllib.request.urlopen(req, timeout=180) as resp:



                total = int(resp.headers.get("Content-Length", 0))



                suffix = ".zip" if self._url.lower().endswith(".zip") else ".exe"



                hasher = hashlib.sha256()



                tmp = tempfile.NamedTemporaryFile(



                    suffix=f"_iqtMusic_update{suffix}", delete=False



                )



                tmp_path = tmp.name



                downloaded = 0



                while True:



                    chunk = resp.read(65536)



                    if not chunk:



                        break



                    tmp.write(chunk)



                    hasher.update(chunk)



                    downloaded += len(chunk)



                    self.progress.emit(downloaded, total)



                tmp.close()



            if total and downloaded != total:



                raise IOError("Indirme boyutu beklenen dosya boyutuyla eslesmiyor.")



            self.finished.emit(tmp.name, hasher.hexdigest())



        except Exception as exc:



            if tmp_path and os.path.exists(tmp_path):



                try:



                    os.remove(tmp_path)



                except Exception:



                    pass



            self.error.emit(str(exc))











def _verify_download(path: str, actual_sha256: str, info: dict) -> Optional[str]:



    expected_sha256 = str(info.get("sha256", "") or "").strip().lower()



    if not expected_sha256:



        return "SHA-256 bilgisi eksik oldugu icin guncelleme dogrulanamadi."







    actual_sha256 = str(actual_sha256 or "").strip().lower()



    if actual_sha256 != expected_sha256:



        return "Indirilen dosyanin SHA-256 dogrulamasi basarisiz oldu."







    expected_size = int(info.get("size", 0) or 0)



    if expected_size > 0:



        try:



            actual_size = os.path.getsize(path)



        except OSError as exc:



            return f"Indirilen dosya okunamadi: {exc}"



        if actual_size != expected_size:



            return "Indirilen dosya boyutu release verisiyle eslesmiyor."







    return None











# â”€â”€ Patch uygulama — PowerShell helper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€







# Tek tırnak ile çevrilmiş yollarda ' → '' kaçış kuralı



_PS1_TEMPLATE = """\



$ErrorActionPreference = 'Stop'



$zipPath    = '{zip_path}'



$installDir = [System.IO.Path]::GetFullPath('{install_dir}')



$appExe     = '{app_exe}'



$patchManifestEntry = '{patch_manifest_entry}'







$installRoot = $installDir



if (-not $installRoot.EndsWith([System.IO.Path]::DirectorySeparatorChar)) {{



    $installRoot += [System.IO.Path]::DirectorySeparatorChar



}}







function Resolve-InInstallDir([string]$relativePath) {{



    $clean = [string]$relativePath



    if ([string]::IsNullOrWhiteSpace($clean)) {{



        throw 'Patch yolu bos.'



    }}



    $clean = $clean -replace '/', [System.IO.Path]::DirectorySeparatorChar



    $resolved = [System.IO.Path]::GetFullPath((Join-Path $installDir $clean))



    if (



        $resolved -ne $installDir -and



        -not $resolved.StartsWith($installRoot, [System.StringComparison]::OrdinalIgnoreCase)



    ) {{



        throw "Patch yolu kurulum klasorunden disari cikiyor: $relativePath"



    }}



    return $resolved



}}







function Remove-EmptyParents([string]$path) {{



    $cursor = [System.IO.Path]::GetDirectoryName($path)



    while ($cursor -and $cursor -ne $installDir) {{



        if (-not $cursor.StartsWith($installRoot, [System.StringComparison]::OrdinalIgnoreCase)) {{



            break



        }}



        try {{



            $children = @(Get-ChildItem -LiteralPath $cursor -Force -ErrorAction Stop)



            if ($children.Count -gt 0) {{



                break



            }}



            Remove-Item -LiteralPath $cursor -Force -ErrorAction SilentlyContinue



            $cursor = [System.IO.Path]::GetDirectoryName($cursor)



        }} catch {{



            break



        }}



    }}



}}







# Uygulamanın tamamen kapanmasını bekle (sabit süre yerine process kontrolü)



$exeName = [System.IO.Path]::GetFileNameWithoutExtension($appExe)



$waited  = 0



while ($waited -lt 20000) {{



    $running = Get-Process -Name $exeName -ErrorAction SilentlyContinue



    if (-not $running) {{ break }}



    Start-Sleep -Milliseconds 300



    $waited += 300



}}



Start-Sleep -Milliseconds 600







Add-Type -AssemblyName System.IO.Compression.FileSystem



try {{



    $zip = [System.IO.Compression.ZipFile]::OpenRead($zipPath)



    $manifest = $null



    $manifestEntry = $zip.GetEntry($patchManifestEntry)



    if ($manifestEntry -ne $null) {{



        $reader = New-Object System.IO.StreamReader($manifestEntry.Open(), [System.Text.Encoding]::UTF8)



        try {{



            $manifestJson = $reader.ReadToEnd()



        }} finally {{



            $reader.Dispose()



        }}



        if (-not [string]::IsNullOrWhiteSpace($manifestJson)) {{



            $manifest = $manifestJson | ConvertFrom-Json



        }}



    }}



    $deletedFiles = @()



    if ($manifest -and $manifest.deleted_files) {{



        $deletedFiles = @($manifest.deleted_files)



    }}



    foreach ($deleted in $deletedFiles) {{



        $target = Resolve-InInstallDir ([string]$deleted)



        if (Test-Path -LiteralPath $target) {{



            Remove-Item -LiteralPath $target -Force -Recurse -ErrorAction Stop



            Remove-EmptyParents $target



        }}



    }}



    foreach ($entry in $zip.Entries) {{



        if ($entry.FullName -eq $patchManifestEntry) {{ continue }}



        if ($entry.Name -eq '') {{ continue }}



        $dest = Resolve-InInstallDir $entry.FullName



        $dir  = [System.IO.Path]::GetDirectoryName($dest)



        if (-not (Test-Path -LiteralPath $dir)) {{



            New-Item -ItemType Directory -Force -Path $dir | Out-Null



        }}



        [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $dest, $true)



    }}



    $zip.Dispose()



    Write-Host 'Guncelleme basariyla uygulandi.' -ForegroundColor Green



}} catch {{



    Write-Host "Hata: $_" -ForegroundColor Red



    Start-Sleep -Milliseconds 4000



    exit 1



}} finally {{



    Remove-Item $zipPath -Force -ErrorAction SilentlyContinue



}}







if (Test-Path $appExe) {{ Start-Process $appExe }}



"""











def _apply_patch(zip_path: str) -> bool:



    """



    patch.zip içindeki dosyaları kurulum dizinine yazar.







    Adımlar:



      1. PowerShell betiği temp klasöre yazar



      2. ShellExecute runas ile yükseltilmiş yetki ister



      3. Betik: 2.5 sn bekler → zip'i açar → exe'yi başlatır



      4. Mevcut uygulama QApplication.quit() ile kapanır



    """



    import ctypes







    if getattr(sys, "frozen", False):



        install_dir = os.path.dirname(sys.executable)



        app_exe     = sys.executable



    else:



        install_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))



        app_exe     = sys.executable







    def _esc(p: str) -> str:



        return p.replace("'", "''")







    ps1_content = _PS1_TEMPLATE.format(



        zip_path    = _esc(zip_path),



        install_dir = _esc(install_dir),



        app_exe     = _esc(app_exe),



        patch_manifest_entry = _esc(_PATCH_MANIFEST_NAME),



    )







    ps1_path = os.path.join(tempfile.gettempdir(), "iqtMusic_patch_helper.ps1")



    with open(ps1_path, "w", encoding="utf-8-sig") as f:  # BOM: PS Türkçe path okur



        f.write(ps1_content)







    ps_args = f'-WindowStyle Hidden -ExecutionPolicy Bypass -File "{ps1_path}"'



    ret = ctypes.windll.shell32.ShellExecuteW(



        None, "runas", "powershell.exe", ps_args, None, 0



    )



    if ret <= 32:



        log.error("ShellExecute başarısız, kod: %s", ret)



        return False



    # PowerShell başlatıldı. UAC onayına yetecek kadar bekleyip



    # süreci öldür. Qt event loop'una güvenmiyoruz — os._exit garantili.



    def _force_exit():



        time.sleep(1.2)



        os._exit(0)



    threading.Thread(target=_force_exit, daemon=True, name="updater-exit").start()



    return True











# â”€â”€ Güncelleme diyaloğu â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€







def _build_stylesheet(acc: str) -> str:



    return f"""



    QDialog {{



        background-color: #0B1120;



        border: 1px solid #1a2a40;



    }}



    QLabel {{



        background-color: transparent;



        color: #BAC6DA;



        font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;



    }}



    QLabel#lbl_title {{



        color: #FFFFFF;



        font-size: 16px;



        font-weight: bold;



    }}



    QLabel#lbl_ver {{



        font-size: 13px;



        color: #BAC6DA;



    }}



    QLabel#lbl_meta {{



        font-size: 12px;



        color: #4a6080;



    }}



    QLabel#lbl_notes {{



        font-size: 12px;



        color: #7D8CA5;



        background-color: #0d1828;



        border: 1px solid #192840;



        border-radius: 6px;



        padding: 10px 12px;



    }}



    QLabel#lbl_status {{



        font-size: 12px;



        color: #5a7090;



    }}



    QLabel#lbl_pct {{



        font-size: 12px;



        font-weight: bold;



        color: {acc};



    }}



    QLabel#lbl_done {{



        font-size: 12px;



        font-weight: bold;



        color: {acc};



    }}



    QFrame#sep {{



        background-color: #141f30;



        max-height: 1px;



        border: none;



    }}



    QWidget#progress_area {{



        background-color: transparent;



    }}



    QProgressBar {{



        background-color: #141f30;



        border: none;



        border-radius: 5px;



        min-height: 10px;



        max-height: 10px;



        text-align: center;



    }}



    QProgressBar::chunk {{



        background: qlineargradient(



            x1:0, y1:0, x2:1, y2:0,



            stop:0 {acc}aa, stop:1 {acc}



        );



        border-radius: 5px;



    }}



    QPushButton {{



        background-color: #111c2e;



        border: 1px solid #1e2f48;



        border-radius: 8px;



        padding: 9px 24px;



        color: #FFFFFF;



        font-size: 13px;



        font-weight: 600;



        font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;



        min-width: 120px;



    }}



    QPushButton:hover {{



        background-color: #1a2840;



        border-color: {acc};



    }}



    QPushButton:disabled {{



        background-color: #0c1520;



        color: #2a3a50;



        border-color: #111d2e;



    }}



    QPushButton#btn_update {{



        background-color: {acc};



        border-color: {acc};



        color: #000000;



        font-weight: bold;



    }}



    QPushButton#btn_update:hover {{



        background-color: #ffffff;



        border-color: #ffffff;



        color: #000000;



    }}



    QPushButton#btn_update:disabled {{



        background-color: #0f2e1a;



        border-color: #0f2e1a;



        color: #1e4028;



    }}



    """











class UpdateDialog(QDialog):







    def __init__(self, info: dict, accent: str = "#1DB954", parent=None, lang: str = "tr"):



        super().__init__(parent)



        self._info           = info
        _is_en = str(lang or "tr").lower().startswith("en")
        self._s = {
            "title":       "New Update Available!" if _is_en else "Yeni Güncelleme Mevcut!",
            "cur_ver":     "Current version" if _is_en else "Mevcut sürüm",
            "skip":        "Not Now" if _is_en else "Şimdi Değil",
            "update":      "Update" if _is_en else "Güncelle",
            "downloading": "Downloading…" if _is_en else "İndiriliyor…",
            "connecting":  "Connecting…" if _is_en else "Sunucuya bağlanıyor…",
            "preparing":   "Preparing…" if _is_en else "Hazırlanıyor…",
            "verified":    "Download verified." if _is_en else "İndirme doğrulandı.",
            "applying":    "Applying update, restarting…" if _is_en else "Güncelleme uygulanıyor, yeniden başlatılıyor…",
            "installing":  "Starting installation…" if _is_en else "Kurulum başlatılıyor…",
            "retry":       "Try Again" if _is_en else "Tekrar Dene",
            "error":       "Error" if _is_en else "Hata",
            "ps_fail":     ("Could not start PowerShell. Try running as administrator."
                            if _is_en else
                            "PowerShell başlatılamadı. Yönetici olarak çalıştırmayı deneyin."),
        }



        self._accent         = accent



        self._thread: Optional[_DownloadThread] = None



        self._update_started = False







        self.setWindowTitle("iqtMusic — Update" if _is_en else "iqtMusic — Güncelleme")



        self.setWindowFlags(



            Qt.Dialog | Qt.WindowCloseButtonHint | Qt.WindowStaysOnTopHint



        )



        self.setFixedWidth(500)



        self.setModal(True)



        self.setStyleSheet(_build_stylesheet(accent))







        root = QVBoxLayout(self)



        root.setContentsMargins(30, 28, 30, 26)



        root.setSpacing(0)







        # â”€â”€ Başlık â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€



        lbl_title = QLabel(self._s["title"])



        lbl_title.setObjectName("lbl_title")



        root.addWidget(lbl_title)



        root.addSpacing(14)







        # â”€â”€ Versiyon satırı â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€



        from core.constants import APP_VERSION



        lbl_ver = QLabel(



            f"{self._s['cur_ver']}:&nbsp;<b>v{APP_VERSION}</b>"



            f"&nbsp;&nbsp;→&nbsp;&nbsp;"



            f"<span style='color:{accent};font-weight:bold;'>"



            f"v{info['version']}</span>"



        )



        lbl_ver.setObjectName("lbl_ver")



        lbl_ver.setTextFormat(Qt.RichText)



        root.addWidget(lbl_ver)



        root.addSpacing(8)







        # â”€â”€ Meta bilgi (boyut + mod) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€



        self._progress_area = QWidget()



        self._progress_area.setObjectName("progress_area")



        self._progress_area.setVisible(False)



        pa = QVBoxLayout(self._progress_area)



        pa.setContentsMargins(0, 0, 0, 0)



        pa.setSpacing(8)







        self._bar = QProgressBar()



        self._bar.setRange(0, 100)



        self._bar.setValue(0)



        self._bar.setTextVisible(False)



        pa.addWidget(self._bar)







        # Bilgi satırı: "118.5 / 260.5 MB" sol  ·  "%45" sağ



        info_row = QHBoxLayout()



        info_row.setContentsMargins(0, 0, 0, 0)



        info_row.setSpacing(0)



        self._lbl_status = QLabel(self._s['preparing'])



        self._lbl_status.setObjectName("lbl_status")



        self._lbl_pct = QLabel("0%")



        self._lbl_pct.setObjectName("lbl_pct")



        info_row.addWidget(self._lbl_status)



        info_row.addStretch()



        info_row.addWidget(self._lbl_pct)



        pa.addLayout(info_row)







        root.addWidget(self._progress_area)







        # Tamamlandı mesajı



        self._lbl_done = QLabel("")



        self._lbl_done.setObjectName("lbl_done")



        self._lbl_done.setVisible(False)



        root.addWidget(self._lbl_done)







        root.addSpacing(20)







        # â”€â”€ Butonlar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€



        btn_row = QHBoxLayout()



        btn_row.setSpacing(10)







        self._btn_skip = QPushButton(self._s['skip'])



        self._btn_skip.clicked.connect(self.reject)







        self._btn_update = QPushButton(self._s['update'])



        self._btn_update.setObjectName("btn_update")



        self._btn_update.clicked.connect(self._start_download)







        btn_row.addWidget(self._btn_skip)



        btn_row.addStretch()



        btn_row.addWidget(self._btn_update)



        root.addLayout(btn_row)







    # â”€â”€ İndirme â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€







    def _start_download(self):



        self._btn_update.setEnabled(False)



        self._btn_update.setText(self._s['downloading'])



        self._btn_skip.setEnabled(False)



        self._progress_area.setVisible(True)



        self._lbl_status.setText(self._s['connecting'])



        self.adjustSize()







        self._thread = _DownloadThread(self._info["download_url"], self)



        self._thread.progress.connect(self._on_progress)



        self._thread.finished.connect(self._on_finished)



        self._thread.error.connect(self._on_error)



        self._thread.start()







    def _on_progress(self, done: int, total: int):



        if total > 0:



            pct = int(done / total * 100)



            self._bar.setValue(pct)



            self._lbl_pct.setText(f"%{pct}")



            self._lbl_status.setText(



                f"{self._s['downloading']}  {done/1_048_576:.1f} / {total/1_048_576:.1f} MB"



            )



        else:



            self._lbl_status.setText(f"{self._s['downloading']}  {done/1_048_576:.1f} MB")







    def _on_finished(self, path: str, actual_sha256: str):



        verify_error = _verify_download(path, actual_sha256, self._info)



        if verify_error:



            try:



                os.remove(path)



            except OSError:



                pass



            self._on_error(verify_error)



            return







        self._bar.setValue(100)



        self._lbl_pct.setText("%100")



        self._lbl_status.setText(self._s['verified'])



        QApplication.processEvents()







        if self._info.get("mode") == "patch":



            self._run_patch(path)



        else:



            self._run_installer(path)







    def _on_error(self, msg: str):



        self._lbl_status.setStyleSheet("color: #E91E63; font-size: 12px;")



        self._lbl_status.setText(f"{self._s['error']}: {msg}")



        self._btn_update.setText(self._s['retry'])



        self._btn_update.setEnabled(True)



        self._btn_skip.setEnabled(True)







    # â”€â”€ Patch modu â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€







    def _run_patch(self, zip_path: str):



        self._lbl_done.setText(self._s['applying'])



        self._lbl_done.setVisible(True)



        self._btn_skip.setEnabled(False)



        self._btn_update.setEnabled(False)



        QApplication.processEvents()



        if _apply_patch(zip_path):



            self._update_started = True



            self.accept()



        else:



            self._on_error(self._s['ps_fail'])







    # â”€â”€ Tam kurulum modu â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€







    def _run_installer(self, exe_path: str):



        import ctypes



        self._lbl_done.setText(self._s['installing'])



        self._lbl_done.setVisible(True)



        self._btn_skip.setEnabled(False)



        self._btn_update.setEnabled(False)



        QApplication.processEvents()



        try:



            ret = ctypes.windll.shell32.ShellExecuteW(



                None, "runas", exe_path, None, None, 1



            )



            if ret <= 32:



                raise OSError(f"ShellExecute kodu: {ret}")



            self._update_started = True



            self.accept()



        except Exception as exc:



            self._on_error(str(exc))











# â”€â”€ Ana giriş noktası â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€







def run_update_check(



    current_version: str,



    accent: str = "#1DB954",



    parent=None,



    lang: str = "tr",



) -> bool:



    """



    Güncelleme kontrolü yapar; bulunursa diyaloğu gösterir.



    main.py'de splash gösterildikten hemen sonra çağrılmalıdır.







    Returns:



        True  → güncelleme başlatıldı, QApplication.quit() çağrıldı.



        False → güncelleme yok ya da kullanıcı erteledi.



    """



    if not GITHUB_OWNER or GITHUB_OWNER == "KULLANICI_ADI":



        log.debug("GitHub ayarları eksik, güncelleme atlanıyor.")



        return False







    info = check_for_update_async(current_version)



    if not info:



        return False




    dlg = UpdateDialog(info, accent=accent, parent=parent, lang=lang)



    dlg.exec()



    return dlg._update_started



