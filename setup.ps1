# DQ Video - cài đặt trên Windows (chạy một lần, chạy lại cũng không sao)
#   powershell -ExecutionPolicy Bypass -File setup.ps1
# Tuỳ chọn: đặt $env:DQ_PYTHON = "đường\dẫn\python.exe" để chỉ định Python x64.

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root
Write-Host "== DQ Video setup ==" -ForegroundColor Cyan

function Install-Winget($id, $extra) {
    $wargs = @("install", "--id", $id, "-e", "--accept-source-agreements", "--accept-package-agreements", "--silent") + $extra
    & winget @wargs
}

# 1. ffmpeg -----------------------------------------------------------------
$hasFfmpeg = (Get-Command ffmpeg -ErrorAction SilentlyContinue) -or
    (Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Filter "Gyan.FFmpeg*" -ErrorAction SilentlyContinue)
if (-not $hasFfmpeg) {
    Write-Host "Cài ffmpeg..."
    Install-Winget "Gyan.FFmpeg" @()
} else { Write-Host "ffmpeg: đã có" }

# 2. Python x64 3.10-3.12 (faster-whisper chưa có bản cho Python ARM64) -------
function Get-PyInfo($exe) {
    try {
        $o = & $exe -c "import sys,sysconfig;print(sysconfig.get_platform(), sys.version_info[0]*100+sys.version_info[1])" 2>$null
        return "$o".Trim()
    } catch { return "" }
}
function Find-Python {
    $c = @()
    if ($env:DQ_PYTHON) { $c += $env:DQ_PYTHON }
    $c += Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe", "$env:USERPROFILE\python3*\python.exe",
        "C:\Program Files\Python3*\python.exe" -ErrorAction SilentlyContinue | ForEach-Object FullName
    $c += Get-Command python -All -ErrorAction SilentlyContinue | Where-Object { $_.Source -notmatch "WindowsApps" } |
        ForEach-Object Source
    foreach ($p in $c) {
        $i = Get-PyInfo $p
        if ($i -match '^win-amd64 (\d+)$' -and [int]$Matches[1] -ge 310 -and [int]$Matches[1] -le 312) { return $p }
    }
    return $null
}
$py = Find-Python
if (-not $py) {
    Write-Host "Cài Python 3.12 (x64)..."
    Install-Winget "Python.Python.3.12" @("--architecture", "x64", "--scope", "user")
    $py = Find-Python
}
if (-not $py) { throw "Không tìm thấy Python x64 3.10-3.12. Cài từ python.org (bản 64-bit x86) rồi chạy lại, hoặc đặt `$env:DQ_PYTHON." }
Write-Host "Python: $py"

# 3. Môi trường Python của dự án ---------------------------------------------
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "Tạo .venv..."
    & $py -m venv (Join-Path $root ".venv")
}
& $venvPy -m pip install -q --upgrade pip
& $venvPy -m pip install -q -r (Join-Path $root "requirements.txt")

# 4. Nhạc nền mặc định --------------------------------------------------------
New-Item -ItemType Directory -Force (Join-Path $root "MUSIC") | Out-Null
if (-not (Get-ChildItem (Join-Path $root "MUSIC") -Include *.wav, *.mp3, *.m4a -Recurse -ErrorAction SilentlyContinue)) {
    Write-Host "Tạo nhạc nền..."
    & $venvPy (Join-Path $root "tools\make_music.py")
}

# 5. Kiểm tra -----------------------------------------------------------------
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"
& $venvPy -W ignore (Join-Path $root "tools\doctor.py")
