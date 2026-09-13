; Perchlings installer. Built by Inno Setup 6 (preinstalled on GitHub's Windows machines):
;   ISCC.exe /DAppVersion=0.3.0 tools\installer.iss
; after tools/build_exe.py has made dist\Perchlings\. Installs for the current user only, no admin password.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{7C2E5B1A-9D4F-4B7E-8A63-2F1C0D5E9B11}
AppName=Perchlings
AppVersion={#AppVersion}
AppVerName=Perchlings {#AppVersion}
AppPublisher=Perchlings
DefaultDirName={localappdata}\Programs\Perchlings
DefaultGroupName=Perchlings
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=PerchlingsSetup-{#AppVersion}
SetupIconFile=..\build\perchlings.ico
UninstallDisplayIcon={app}\Perchlings.exe
UninstallDisplayName=Perchlings
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Put a Perchlings icon on the desktop"; GroupDescription: "Shortcuts"
Name: "startup"; Description: "Start my pet when Windows starts"; GroupDescription: "Every day"

[Files]
Source: "..\dist\Perchlings\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Perchlings"; Filename: "{app}\Perchlings.exe"
Name: "{group}\Uninstall Perchlings"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Perchlings"; Filename: "{app}\Perchlings.exe"; Tasks: desktopicon
Name: "{userstartup}\Perchlings"; Filename: "{app}\Perchlings.exe"; Tasks: startup

[Run]
Filename: "{app}\Perchlings.exe"; Description: "Meet your pet now"; Flags: nowait postinstall skipifsilent

[Messages]
WelcomeLabel1=Welcome to Perchlings
WelcomeLabel2=This puts a little pet on your desktop.%n%nClick Next. It takes about ten seconds and needs no password.
FinishedHeadingLabel=All done
FinishedLabel=Perchlings is installed. The first time it opens, it asks which pet you adopted, what to call it, and which 5 things it can do.
