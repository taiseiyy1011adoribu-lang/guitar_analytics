; Inno Setup のスクリプト。PyInstaller で作った dist\GuitarTab\ を setup.exe にまとめる。
; 版はワークフローから渡す: iscc /DAppVersion=0.2.0 packaging\installer.iss

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6A1F3B2E-7C41-4E1B-9B8E-2F6D5A9C3E10}
AppName=ギタータブ譜メーカー
AppVersion={#AppVersion}
AppPublisher=guitar_analytics
DefaultDirName={autopf}\GuitarTab
DefaultGroupName=ギタータブ譜メーカー
; 管理者権限なしで、自分のユーザーにだけインストールする
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=GuitarTab-Setup-{#AppVersion}
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\GuitarTab.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; 新しい版を入れるときは、動いている古いアプリを閉じてから上書きする
CloseApplications=yes

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "desktopicon"; Description: "デスクトップにアイコンを作る"; GroupDescription: "アイコン:"

[Files]
Source: "..\dist\GuitarTab\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; 古い版のファイルが残って混ざらないように
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{group}\ギタータブ譜メーカー"; Filename: "{app}\GuitarTab.exe"
Name: "{group}\ギタータブ譜メーカーをアンインストール"; Filename: "{uninstallexe}"
Name: "{autodesktop}\ギタータブ譜メーカー"; Filename: "{app}\GuitarTab.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\GuitarTab.exe"; Description: "今すぐ起動する"; Flags: nowait postinstall skipifsilent
