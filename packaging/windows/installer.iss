; Anonimleştirici Windows kurulum sihirbazı (Inno Setup 6)
;   iscc /DAppVersion=0.2.0 packaging\windows\installer.iss
; Yönetici izni istemez; kullanıcının kendi klasörüne kurar.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6B0B4C8E-3D6A-4E9C-9F2A-7A1E2C5D8B41}
AppName=Anonimleştirici
AppVersion={#AppVersion}
AppVerName=Anonimleştirici {#AppVersion}
AppPublisher=Mehmet Enes Parlak
AppPublisherURL=https://meparlak.github.io/anonimlestirici/
AppSupportURL=https://meparlak.github.io/anonimlestirici/destek.html
DefaultDirName={localappdata}\Programs\Anonimlestirici
DefaultGroupName=Anonimleştirici
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\..\dist
OutputBaseFilename=Anonimlestirici-Kurulum
SetupIconFile=Anonimlestirici.ico
UninstallDisplayIcon={app}\Anonimlestirici.exe
UninstallDisplayName=Anonimleştirici
Compression=lzma2/normal
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
LicenseFile=..\..\LICENSE

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaüstüne kısayol ekle"; GroupDescription: "Kısayollar:"

[Files]
Source: "..\..\dist\windows\Anonimlestirici\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Anonimleştirici"; Filename: "{app}\Anonimlestirici.exe"
Name: "{userdesktop}\Anonimleştirici"; Filename: "{app}\Anonimlestirici.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Anonimlestirici.exe"; Description: "Anonimleştirici'yi şimdi aç"; Flags: nowait postinstall skipifsilent

[Code]
// Arayüz Microsoft Edge WebView2 ile gösterilir. Windows 11'de ve güncel Windows 10'da hazır gelir.
function WebView2Installed(): Boolean;
var v: String;
begin
  Result :=
    RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', v) or
    RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', v);
  Result := Result and (v <> '') and (v <> '0.0.0.0');
end;

function InitializeSetup(): Boolean;
var code: Integer;
begin
  Result := True;
  if not WebView2Installed() then
    if MsgBox('Anonimleştirici''nin arayüzü için Microsoft Edge WebView2 gerekiyor ve bu bilgisayarda bulunamadı.' + #13#10#13#10 +
              'Kuruluma devam edebilirsiniz; uygulama açılmazsa Microsoft''un sayfasından "Evergreen Bootstrapper"ı indirip kurun.' + #13#10#13#10 +
              'Sayfa şimdi açılsın mı?', mbConfirmation, MB_YESNO) = IDYES then
      ShellExec('open', 'https://developer.microsoft.com/microsoft-edge/webview2/', '', '', SW_SHOWNORMAL, ewNoWait, code);
end;
