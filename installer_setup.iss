#define MyAppName "Auto Homework Sender"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Auto Homework Team"
#define MyAppURL "https://github.com/NB-Group/auto_homework"
#define MyAppExeName "AutoHomework.exe"
#define MyAppDescription "作业发送助手"

[Setup]
; 注意: AppId的值唯一标识此应用程序
AppId={{B8F7D9C1-8E4A-4B5C-9F2E-1A3B5C7D9E0F}
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
LicenseFile=LICENSE.txt
OutputDir=installer
OutputBaseFilename=AutoHomework_Setup_v{#MyAppVersion}
SetupIconFile=icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
VersionInfoVersion={#MyAppVersion}
VersionInfoDescription={#MyAppDescription}
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"

[Files]
; 固定使用规范化目录 dist\main.dist（workflow已保证生成）
Source: "dist\main.dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion; DestName: "README.txt"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Registry]
; 不再提供安装时开机自启动选项，交由应用内部设置

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; 卸载时停止可能正在运行的程序
Filename: "{cmd}"; Parameters: "/C taskkill /f /im AutoHomework.exe"; Flags: runhidden; RunOnceId: "KillApp"

[Code]
// 自定义页面和功能
procedure InitializeWizard;
begin
  // 这里可以添加自定义的安装向导页面
  WizardForm.WelcomeLabel1.Caption := '欢迎使用 Auto Homework Sender 安装向导';
  WizardForm.WelcomeLabel2.Caption := 
    '这将在您的计算机上安装智能作业自动发送助手。' + #13#13 +
    '该软件具有以下特色功能：' + #13 +
    '• 智能PPT内容解析' + #13 +
    '• 自动定时发送作业' + #13 +
    '• 精美的现代化界面' + #13 +
    '• 支持浅色/深色主题切换' + #13#13 +
    '点击"下一步"继续，或点击"取消"退出安装程序。';
end;

// 检查应用是否正在运行
function InitializeSetup(): Boolean;
var
  ErrorCode: Integer;
begin
  Result := True;
  // 尝试关闭正在运行的应用
  if CheckForMutexes('AutoHomeworkMutex') then
  begin
    if MsgBox('检测到 Auto Homework Sender 正在运行。安装程序需要关闭它才能继续。' + #13#13 + '是否继续？', 
              mbConfirmation, MB_YESNO) = IDYES then
    begin
      Exec('taskkill', '/f /im AutoHomework.exe', '', SW_HIDE, ewWaitUntilTerminated, ErrorCode);
    end
    else
    begin
      Result := False;
    end;
  end;
end;

// 卸载前确认
function InitializeUninstall(): Boolean;
var
  ErrorCode: Integer;
begin
  Result := True;
  if MsgBox('确定要完全移除 Auto Homework Sender 及其所有组件吗？', mbConfirmation, MB_YESNO) = IDYES then
  begin
    // 关闭可能正在运行的程序
    Exec('taskkill', '/f /im AutoHomework.exe', '', SW_HIDE, ewWaitUntilTerminated, ErrorCode);
  end
  else
    Result := False;
end;
