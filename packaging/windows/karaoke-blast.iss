; Inno Setup script for Karaoke Blast (Windows).
; Build: iscc packaging\windows\karaoke-blast.iss

#define AppName "Karaoke Blast"
#define AppExeName "launcher.bat"
#define AppPublisher "Karaoke Blast"
#define AppURL "https://github.com/edbecnel/Karaoke-Blast"
#define StagingDir "staging"

#ifndef AppVersion
  #define AppVersion "0.3.0"
#endif

[Setup]
AppId={{A4F9D2E1-8C3B-4F5A-9D1E-2B7C8A9F0E1D}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=KaraokeBlast-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked
Name: "installvlc"; Description: "Install VLC if it is not already on this computer (required for local file playback)"; GroupDescription: "Optional components:"; Flags: checkedonce

[Files]
Source: "{#StagingDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\icon.ico"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Run]
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\detect-deps.ps1"" -AppDir ""{app}"" -InstallVlc {code:GetInstallVlcFlag}"; Description: "Install missing dependencies (VLC, ffmpeg)"; Flags: nowait postinstall skipifsilent
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent unchecked

[Code]
var
  InstallVlcTask: Boolean;

function GetInstallVlcFlag(Param: string): string;
begin
  if InstallVlcTask then
    Result := '$true'
  else
    Result := '$false';
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    InstallVlcTask := WizardIsTaskSelected('installvlc');
end;

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
