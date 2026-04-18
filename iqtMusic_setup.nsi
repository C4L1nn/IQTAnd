; =========================================================
; iqtMusic -- NSIS Kurulum Betigi
; =========================================================

Unicode True
!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "LogicLib.nsh"

!define APP_NAME      "IQTMusic"
!define APP_VERSION   "1.1.7"
!define APP_PUBLISHER "Aykut"
!define APP_EXE       "IQTMusic.exe"
!define APP_DIRNAME   "IQTMusic"
!define SOURCE_ROOT   "${__FILEDIR__}"
!define SOURCE_DIST   "${SOURCE_ROOT}\dist\iqtMusic"

Name "${APP_NAME}"
OutFile "IQTMusic_Kurulum.exe"
InstallDir "$PROGRAMFILES64\${APP_DIRNAME}"
InstallDirRegKey HKLM "Software\${APP_NAME}" "KurulumDizini"
RequestExecutionLevel admin
BrandingText "iqtMusic ${APP_PUBLISHER}"

Icon        "iqticon.ico"
UninstallIcon "iqticon.ico"

!define MUI_ABORTWARNING
!define MUI_ABORTWARNING_TEXT "Kurulumdan çıkmak istediğinize emin misiniz?"
!define MUI_ICON   "iqticon.ico"
!define MUI_UNICON "iqticon.ico"

!define MUI_WELCOMEPAGE_TITLE   "iqtMusic Kurulum Sihirbazına Hoş Geldiniz"
!define MUI_WELCOMEPAGE_TEXT    "Bu sihirbaz ${APP_NAME} uygulamasını bilgisayarınıza kuracaktır.$\r$\nDevam etmeden önce açık olan tüm uygulamaları kapatmanız önerilir.$\nDevam etmek için İleri'ye tıklayın."

!define MUI_DIRECTORYPAGE_TEXT_TOP         "${APP_NAME} aşağıdaki klasöre kurulacaktır. Farklı bir klasör seçmek için Gözat'a tıklayın."
!define MUI_DIRECTORYPAGE_TEXT_DESTINATION "Kurulum Klasörü"

!define MUI_INSTFILESPAGE_FINISHHEADER_TEXT    "Kurulum Tamamlandı"
!define MUI_INSTFILESPAGE_FINISHHEADER_SUBTEXT "${APP_NAME} başarıyla kuruldu."
!define MUI_INSTFILESPAGE_ABORTHEADER_TEXT     "Kurulum İptal Edildi"
!define MUI_INSTFILESPAGE_ABORTHEADER_SUBTEXT  "Kurulum yarıda kesildi."

!define MUI_FINISHPAGE_TITLE       "Kurulum Tamamlandı"
!define MUI_FINISHPAGE_TEXT        "${APP_NAME} bilgisayarınıza başarıyla kuruldu.$\r$\nUygulumayı başlatmak için aşağıdaki seçeneği işaretleyebilirsiniz."
!define MUI_FINISHPAGE_RUN         "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT    "${APP_NAME} uygulamasını başlat"
!define MUI_FINISHPAGE_NOAUTOCLOSE

!define MUI_UNCONFIRMPAGE_TEXT_TOP "${APP_NAME} bilgisayarınızdan kaldırılacaktır. Devam etmek için Kaldır düğmesine tıklayın."
!define MUI_UNFINISHPAGE_NOAUTOCLOSE

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "Turkish"

Function .onInstSuccess
    ${If} ${Silent}
        Exec '"$INSTDIR\${APP_EXE}"'
    ${EndIf}
FunctionEnd

Section "Ana Kurulum" BOLUM_ANA
    SetOutPath "$INSTDIR"
    File /r "${SOURCE_DIST}\*"

    WriteRegStr HKLM "Software\${APP_NAME}" "KurulumDizini" "$INSTDIR"

    ; iqtmusic:// URL protokolü — Discord "Beraber Dinle" butonu için
    WriteRegStr HKCR "iqtmusic"                          ""           "URL:iqtMusic Protocol"
    WriteRegStr HKCR "iqtmusic"                          "URL Protocol" ""
    WriteRegStr HKCR "iqtmusic\DefaultIcon"              ""           "$INSTDIR\${APP_EXE},0"
    WriteRegStr HKCR "iqtmusic\shell\open\command"       ""           '"$INSTDIR\${APP_EXE}" "%1"'

    WriteRegStr   HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayName"     "${APP_NAME}"
    WriteRegStr   HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayVersion"  "${APP_VERSION}"
    WriteRegStr   HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "Publisher"       "${APP_PUBLISHER}"
    WriteRegStr   HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "InstallLocation" "$INSTDIR"
    WriteRegStr   HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayIcon"     "$INSTDIR\${APP_EXE}"
    WriteRegStr   HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "UninstallString" '"$INSTDIR\Kaldir.exe"'
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "NoModify"        1
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "NoRepair"        1

    ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "EstimatedSize" "$0"

    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortcut  "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
    CreateShortcut  "$SMPROGRAMS\${APP_NAME}\Kaldir.lnk"      "$INSTDIR\Kaldir.exe"
    CreateShortcut  "$DESKTOP\${APP_NAME}.lnk"                 "$INSTDIR\${APP_EXE}"

    WriteUninstaller "$INSTDIR\Kaldir.exe"
SectionEnd

Section "un.Kaldir"
    nsExec::ExecToLog 'taskkill /IM "${APP_EXE}" /F'

    Delete "$DESKTOP\${APP_NAME}.lnk"
    Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
    Delete "$SMPROGRAMS\${APP_NAME}\Kaldir.lnk"
    RMDir  "$SMPROGRAMS\${APP_NAME}"

    RMDir /r "$INSTDIR"

    DeleteRegKey HKLM "Software\${APP_NAME}"
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
    DeleteRegKey HKCR "iqtmusic"
SectionEnd
