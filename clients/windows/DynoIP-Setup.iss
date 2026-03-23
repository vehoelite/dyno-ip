; =============================================================================
; DynoIP Dynamic DNS — Inno Setup Installer Script
; Produces a single DynoIP-Setup.exe installer
; =============================================================================

#define MyAppName "DynoIP"
#define MyAppVersion "2.5.0"
#define MyAppPublisher "DynoIP"
#define MyAppURL "https://dyno-ip.com"
#define MyAppExeName "DynoIP.exe"
#define MyServiceExe "dynoip-service.exe"

[Setup]
AppId={{7E4F8D2A-3B1C-4A9E-B5D6-8F2E1C3A4B5D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; Output to dist/ folder
OutputDir=dist
OutputBaseFilename=DynoIP-Setup
; Use the globe icon
SetupIconFile=dynoip.ico
UninstallDisplayIcon={app}\dynoip.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; Require admin for service installation
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
; Minimum Windows 10
MinVersion=10.0
; Branding
WizardSmallImageFile=dynoip_wizard.bmp
LicenseFile=
; Architecture
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Types]
Name: "full"; Description: "Full installation (GUI + Background Service)"
Name: "guionly"; Description: "GUI application only"
Name: "custom"; Description: "Custom installation"; Flags: iscustom

[Components]
Name: "gui"; Description: "DynoIP Desktop Application"; Types: full guionly custom; Flags: fixed
Name: "service"; Description: "DynoIP Background Update Service"; Types: full custom

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "Start DynoIP when Windows starts"; GroupDescription: "Startup:"; Components: gui
Name: "installservice"; Description: "Install and start the background DNS update service"; Components: service

[Files]
; GUI application
Source: "dist\DynoIP.exe"; DestDir: "{app}"; Flags: ignoreversion; Components: gui
; Background service
Source: "dist\dynoip-service.exe"; DestDir: "{app}"; Flags: ignoreversion; Components: service
; Icon file
Source: "dynoip.ico"; DestDir: "{app}"; Flags: ignoreversion
; Logo for About/branding
Source: "..\..\media\globe_only.png"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Start Menu
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\dynoip.ico"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"; IconFilename: "{app}\dynoip.ico"
; Desktop shortcut (optional)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\dynoip.ico"; Tasks: desktopicon
; Startup folder (optional)
Name: "{autostartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon

[Dirs]
Name: "{commonappdata}\DynoIP"; Permissions: users-modify

[Run]
; Install the Windows service after file copy
Filename: "{app}\{#MyServiceExe}"; Parameters: "install"; StatusMsg: "Installing DynoIP service..."; Flags: runhidden waituntilterminated; Tasks: installservice
; Configure auto-start
Filename: "sc.exe"; Parameters: "config DynoIPUpdate start= auto"; StatusMsg: "Configuring auto-start..."; Flags: runhidden waituntilterminated shellexec; Tasks: installservice
; Set recovery policy
Filename: "sc.exe"; Parameters: "failure DynoIPUpdate reset= 86400 actions= restart/5000/restart/10000/restart/30000"; StatusMsg: "Setting recovery policy..."; Flags: runhidden waituntilterminated shellexec; Tasks: installservice
; Start the service
Filename: "net.exe"; Parameters: "start DynoIPUpdate"; StatusMsg: "Starting DynoIP service..."; Flags: runhidden waituntilterminated; Tasks: installservice
; Launch GUI after install
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent unchecked

[UninstallRun]
; Stop and remove service on uninstall
Filename: "net.exe"; Parameters: "stop DynoIPUpdate"; Flags: runhidden; RunOnceId: "StopService"
Filename: "{app}\{#MyServiceExe}"; Parameters: "remove"; Flags: runhidden waituntilterminated; RunOnceId: "RemoveService"

[Code]
// Create default config.ini if it doesn't exist
procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigDir: String;
  ConfigFile: String;
begin
  if CurStep = ssPostInstall then
  begin
    ConfigDir := ExpandConstant('{commonappdata}\DynoIP');
    ConfigFile := ConfigDir + '\config.ini';
    if not FileExists(ConfigFile) then
    begin
      SaveStringToFile(ConfigFile,
        '[dynoip]' + #13#10 +
        '; Your DynoIP API token (get from https://dyno-ip.com dashboard)' + #13#10 +
        'token = YOUR_TOKEN_HERE' + #13#10 +
        '' + #13#10 +
        '; API endpoint' + #13#10 +
        'api_url = https://dyno-ip.com/api' + #13#10 +
        '' + #13#10 +
        '; Update interval in seconds (default: 300 = 5 minutes)' + #13#10 +
        'interval = 300' + #13#10,
        False);
    end;
  end;
end;

// Warn user about service config on first install
function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = wpFinished then
  begin
    if WizardIsTaskSelected('installservice') then
    begin
      MsgBox('The DynoIP service has been installed.' + #13#10 + #13#10 +
             'IMPORTANT: Open the DynoIP app and log in to activate ' +
             'automatic DNS updates, or edit the config file at:' + #13#10 +
             ExpandConstant('{commonappdata}') + '\DynoIP\config.ini',
             mbInformation, MB_OK);
    end;
  end;
end;
