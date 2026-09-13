$ErrorActionPreference = 'Stop'

$ProjectDir = $PSScriptRoot
$DistDir = Join-Path $ProjectDir 'outputs'
$WorkDir = Join-Path $ProjectDir 'build\pyinstaller-work'
$SpecDir = Join-Path $ProjectDir 'build\pyinstaller-spec'

New-Item -ItemType Directory -Force -Path $DistDir, $SpecDir | Out-Null

$FontPath = Join-Path $ProjectDir 'assets\NotoSansCJKsc-Regular.otf'
if (-not (Test-Path -LiteralPath $FontPath)) {
    Write-Host '正在获取开源中文字体…'
    python -c "from urllib.request import urlretrieve; urlretrieve('https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf', r'$FontPath')"
}

python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --name '帧影 FrameCraft' `
    --distpath $DistDir `
    --workpath $WorkDir `
    --specpath $SpecDir `
    --collect-all cv2 `
    --hidden-import PySide6.QtCore `
    --hidden-import PySide6.QtGui `
    --hidden-import PySide6.QtWidgets `
    --add-data "$FontPath;assets" `
    (Join-Path $ProjectDir 'framecraft.py')

Copy-Item -LiteralPath (Join-Path $ProjectDir 'README.md') -Destination (Join-Path $DistDir '帧影 FrameCraft\使用说明.md') -Force
Copy-Item -LiteralPath (Join-Path $ProjectDir 'assets\Noto-CJK-LICENSE.txt') -Destination (Join-Path $DistDir '帧影 FrameCraft\Noto-CJK-LICENSE.txt') -Force

$ZipPath = Join-Path $DistDir 'FrameCraft-Windows-Portable-v1.1.0.zip'
if (Test-Path -LiteralPath $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}
Compress-Archive -LiteralPath (Join-Path $DistDir '帧影 FrameCraft') -DestinationPath $ZipPath -CompressionLevel Optimal
Write-Host "构建完成：$ZipPath"
