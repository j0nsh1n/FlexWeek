; FlexWeek setup program for Windows (Inno Setup 7). The release workflow builds it
; from the Nuitka folder that desktop/build_windows.ps1 makes:
;
;   ISCC.exe /DAppVersion=0.9.2 /DSourceDir=<repo>\dist\FlexWeek-Windows /DOutputDir=<repo>\dist packaging\windows\flexweek.iss
;
; It installs for the current Windows account by default, so no administrator is
; needed; the setup dialog can still switch to every account. The shortcut paths
; are Inno constants resolved on the user's PC, never paths from the build machine.
; Never change AppId: upgrades and uninstall find the installed copy by it.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\..\dist\FlexWeek-Windows"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\dist"
#endif

[Setup]
AppId={{06CA8084-53C1-43D1-9EF7-971998846AB0}
AppName=FlexWeek
AppVersion={#AppVersion}
AppPublisher=FlexWeek
AppPublisherURL=https://github.com/j0nsh1n/FlexWeek
AppSupportURL=https://github.com/j0nsh1n/FlexWeek/issues
DefaultDirName={autopf}\FlexWeek
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=FlexWeek-Windows-x64-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=FlexWeek
UninstallDisplayIcon={app}\FlexWeek.exe
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\FlexWeek"; Filename: "{app}\FlexWeek.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\FlexWeek"; Filename: "{app}\FlexWeek.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\FlexWeek.exe"; Description: "{cm:LaunchProgram,FlexWeek}"; Flags: nowait postinstall skipifsilent
