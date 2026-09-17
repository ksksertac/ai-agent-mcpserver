# Tek komutla kurulum + baslatma.
#   .\setup.ps1            -> her seyi kur/hazirla ve ajani baslat
#   .\setup.ps1 -Check     -> sadece kur/hazirla, ajani baslatma
# Ollama kurulumu, servis baslatma, model indirme ve VS Code ayari ajanin icindeki bootstrap tarafindan yapilir.

param(
    [switch]$Check
)

# Native komutlar (uv, winget) stderr'e bilgi yazar; PS 5.1 bunu hata sanmasin diye Stop kullanmiyoruz.
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Assert-Ok($what) {
    if ($LASTEXITCODE -ne 0) { Write-Host "HATA: $what basarisiz (exit $LASTEXITCODE)" -ForegroundColor Red; exit $LASTEXITCODE }
}

# 1) uv
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Step "uv bulunamadi, winget ile kuruluyor..."
    winget install -e --id astral-sh.uv --accept-package-agreements --accept-source-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "User") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Host "uv kuruldu ama PATH'te degil. Terminali kapatip acin ve tekrar calistirin." -ForegroundColor Yellow
        exit 1
    }
}

# 2) Python + bagimliliklar (.venv)
Write-Step "Bagimliliklar kuruluyor (uv sync)..."
uv sync
Assert-Ok "uv sync"

# 3) Bootstrap: Ollama kur/baslat, model indir, isit, VS Code ayari
Write-Step "Ollama / model / VS Code ayari kontrol ediliyor..."
uv run local-agent --check
Assert-Ok "bootstrap"

if ($Check) {
    Write-Host "`nHazir. Ajani baslatmak icin: uv run local-agent" -ForegroundColor Green
    exit 0
}

# 4) Ajani baslat
Write-Step "Ajan baslatiliyor (http://127.0.0.1:8000). Durdurmak icin Ctrl+C."
Write-Host "VS Code Copilot Chat -> model secici -> 'Local Agent (Ollama + MCP)' secin." -ForegroundColor Green
uv run local-agent
