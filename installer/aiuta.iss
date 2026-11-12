; Aiuta one-click Windows installer (Inno Setup 6).
;
; Double-click Aiuta-Setup.exe and it installs: no questions, no admin password,
; no folder to choose. It puts an Aiuta icon on the desktop, starts Aiuta every
; time the computer starts, and opens it straight away.
;
; Built automatically by .github/workflows/windows.yml. To build by hand on
; Windows, after PyInstaller has made dist\Aiuta:
;   iscc /DAppVersion=0.2.0 installer\aiuta.iss

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6F3C2B1E-8A4D-4E57-9C2A-1B7D3E5F9A40}
AppName=Aiuta
AppVersion={#AppVersion}
AppVerName=Aiuta
AppPublisher=Aiuta
AppPublisherURL=https://github.com/harrycatanzariti-oss/Auita
DefaultDirName={localappdata}\Programs\Aiuta
; Installs just for this Windows user, so no administrator password is needed.
PrivilegesRequired=lowest
; One click: skip every question.
DisableWelcomePage=yes
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
DisableFinishedPage=yes
AllowNoIcons=yes
ShowLanguageDialog=no
LanguageDetectionMethod=uilanguage
CloseApplications=force
RestartApplications=no
SetupIconFile=aiuta.ico
UninstallDisplayIcon={app}\Aiuta.exe
UninstallDisplayName=Aiuta
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
OutputDir=..\dist
OutputBaseFilename=Aiuta-Setup
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "it"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "de"; MessagesFile: "compiler:Languages\German.isl"
Name: "pt"; MessagesFile: "compiler:Languages\Portuguese.isl"
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "nl"; MessagesFile: "compiler:Languages\Dutch.isl"
Name: "pl"; MessagesFile: "compiler:Languages\Polish.isl"
Name: "ja"; MessagesFile: "compiler:Languages\Japanese.isl"
Name: "uk"; MessagesFile: "compiler:Languages\Ukrainian.isl"

[Files]
Source: "..\dist\Aiuta\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userdesktop}\Aiuta"; Filename: "{app}\Aiuta.exe"
Name: "{userprograms}\Aiuta"; Filename: "{app}\Aiuta.exe"
Name: "{userprograms}\Aiuta setup (for family)"; Filename: "{app}\Aiuta.exe"; Parameters: "setup"
Name: "{userstartup}\Aiuta"; Filename: "{app}\Aiuta.exe"

[Run]
; Open Aiuta as soon as it's installed (not during silent installs).
Filename: "{app}\Aiuta.exe"; Flags: nowait skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/f /im Aiuta.exe"; Flags: runhidden; RunOnceId: "StopAiuta"

[Code]
// Stop a running copy before installing an update over it.
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/f /im Aiuta.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := '';
end;
