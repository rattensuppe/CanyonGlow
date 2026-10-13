; Compile through build_windows.py so the version matches canyonglow.py.
#ifndef AppVersion
  #error AppVersion missing. Run build_windows.bat instead.
#endif
#ifndef ReleaseTag
  #error ReleaseTag missing. Run build_windows.bat instead.
#endif
#ifndef BundleDir
  #error BundleDir missing. Run build_windows.bat instead.
#endif
#ifndef ReleaseDir
  #error ReleaseDir missing. Run build_windows.bat instead.
#endif
#define AppName "CanyonGlow"
#define AppExe "CanyonGlow.exe"

[Setup]
; Keep this ID stable so a new setup updates the existing installation.
AppId={{BB107A1E-9A50-4CB9-AAF7-7B068B2223FE}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#ReleaseTag}
VersionInfoVersion={#AppVersion}.0
DefaultDirName={localappdata}\Programs\CanyonGlow
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
DisableProgramGroupPage=yes
UsePreviousLanguage=yes
LanguageDetectionMethod=none
ShowLanguageDialog=yes
UsePreviousAppDir=yes
UsePreviousTasks=yes
OutputDir={#ReleaseDir}
OutputBaseFilename=CanyonGlow-{#ReleaseTag}-Setup-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile={#BundleDir}\_internal\picture\CanyonGlow.ico
UninstallDisplayIcon={app}\{#AppExe}
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; Remove only obsolete files and shortcuts from the previous application name.
Type: files; Name: "{app}\NucLedGui.exe"
Type: files; Name: "{app}\_internal\picture\NucLedGui.ico"
Type: files; Name: "{userprograms}\NUC Beast-Dragon RGB.lnk"
Type: files; Name: "{userdesktop}\NUC Beast-Dragon RGB.lnk"

[Icons]
Name: "{userprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{userdocs}"; IconFilename: "{app}\{#AppExe}"; IconIndex: 0
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{userdocs}"; IconFilename: "{app}\{#AppExe}"; IconIndex: 0; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

; Deliberately no broad UninstallDelete: user-created profiles are retained.
