; MA-CLI Windows 11 installer
#define AppName "MA-CLI"
#define AppVersion "1.0.0"

[Setup]
AppId={{B7E3D0A1-6D5D-4D2A-9F2A-6A1E7D8A4C10}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=MA-CLI Core Team
AppPublisherURL=https://github.com/snisid/AIO-CLi
DefaultDirName={autopf}\MA-CLI
DefaultGroupName=MA-CLI
OutputDir=dist\windows
OutputBaseFilename=MA-CLI-Setup-v{#AppVersion}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UninstallDisplayName=MA-CLI
DisableProgramGroupPage=yes
WizardStyle=modern

[Files]
Source: "dist\ma-cli.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\MA-CLI\MA-CLI"; Filename: "{app}\ma-cli.exe"
Name: "{autodesktop}\MA-CLI"; Filename: "{app}\ma-cli.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\ma-cli.exe"; Parameters: "--version"; StatusMsg: "Verifying MA-CLI installation..."; Flags: runhidden waituntilterminated
