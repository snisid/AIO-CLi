; MA-CLI Windows installer
#define AppName "MA-CLI"
#define AppVersion "1.0.0"
#define AppExeName "ma-cli.exe"

[Setup]
AppId={{B7E3D0A1-6D5D-4D2A-9F2A-6A1E7D8A4C10}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\MA-CLI
DefaultGroupName=MA-CLI
OutputDir=dist\windows
OutputBaseFilename=MA-CLI-Setup-v{#AppVersion}
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UninstallDisplayName=MA-CLI

[Files]
Source: "dist\ma-cli.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\MA-CLI\MA-CLI"; Filename: "{app}\ma-cli.exe"
