# 윈도우용 실행 스크립트 (PowerShell)
# 한글 출력을 위한 인코딩 설정
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$BACKEND_DIR = Join-Path $PSScriptRoot "backend"
$FRONTEND_DIR = Join-Path $PSScriptRoot "frontend"

# 0. 필수 프로그램 확인 및 자동 설치 (Zero-Setup)
function Install-PackageIfMissing {
    param($cmd, $packageId, $name)
    
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Write-Host "⚠️ $name ($cmd)가 설치되어 있지 않습니다." -ForegroundColor Yellow
        Write-Host "⏳ $name 자동 설치를 시작합니다... (관리자 권한 필요할 수 있음)" -ForegroundColor Cyan
        
        # Winget 확인
        if (Get-Command winget -ErrorAction SilentlyContinue) {
            winget install -e --id $packageId --accept-package-agreements --accept-source-agreements
            
            # 설치 후 환경 변수 갱신을 위해 잠시 대기
            Write-Host "설치 완료 대기 중..."
            Start-Sleep -Seconds 5
        }
        else {
            Write-Host "❌ Winget을 찾을 수 없어 자동 설치에 실패했습니다. $name 을(를) 수동으로 설치해주세요." -ForegroundColor Red
            Exit
        }
    }
    else {
        Write-Host "✅ $name 설치 확인됨." -ForegroundColor Green
    }
}

# 시스템 환경 변수(Path) 최신화 함수
function Refresh-EnvVar {
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
}

# 초기 환경 변수 로드
Refresh-EnvVar

# Python 및 Node.js 검사/설치
Install-PackageIfMissing "python" "Python.Python.3.12" "Python 3.12"
Refresh-EnvVar

Install-PackageIfMissing "node" "OpenJS.NodeJS.LTS" "Node.js (LTS)"
Refresh-EnvVar

# 한번 더 명시적 확인 (설치 실패 시 중단)
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { 
    Write-Host "❌ Python 설치 실패. 수동 설치가 필요합니다." -ForegroundColor Red
    Exit 
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { 
    Write-Host "❌ Node.js 설치 실패. 수동 설치가 필요합니다." -ForegroundColor Red
    Exit 
}

Write-Host "환경 변수 최신화 완료." -ForegroundColor Gray

# 1. 백엔드 설정 (가상 환경 및 라이브러리)
Write-Host "--- 백엔드 설정 중 ---" -ForegroundColor Cyan
if (-not (Test-Path (Join-Path $BACKEND_DIR ".venv"))) {
    Write-Host "가상 환경 생성 중..."
    python -m venv (Join-Path $BACKEND_DIR ".venv")
}

if (-not (Test-Path (Join-Path $BACKEND_DIR ".env"))) {
    if (Test-Path (Join-Path $BACKEND_DIR ".env.example")) {
        Write-Host ".env 파일 생성 중..."
        Copy-Item (Join-Path $BACKEND_DIR ".env.example") (Join-Path $BACKEND_DIR ".env")
    }
}

# config.json 설정 (ComfyUI 경로 등)
$CONFIG_PATH = Join-Path $BACKEND_DIR "config.json"
if (-not (Test-Path $CONFIG_PATH)) {
    Write-Host "backend/config.json 생성 중..."
    $defaultConfig = @{
        openai_api_key = ""
        comfyui_path   = ""
        prompts        = @{}
    }
    $defaultConfig | ConvertTo-Json | Set-Content $CONFIG_PATH -Encoding UTF8
    Write-Host "💡 TIP: ComfyUI를 사용하신다면 backend/config.json 파일의 'comfyui_path'에 ComfyUI 설치 경로를 입력하세요." -ForegroundColor Yellow
    Write-Host "   예: C:\ComfyUI_windows_portable\ComfyUI" -ForegroundColor Yellow
}

# 가상 환경 활성화 후 라이브러리 설치
$VENV_PYTHON = Join-Path $BACKEND_DIR ".venv\Scripts\python.exe"
& $VENV_PYTHON -m pip install -r (Join-Path $BACKEND_DIR "requirements.txt")

# 2. 프론트엔드 설정 (패키지 설치)
Write-Host "--- 프론트엔드 설정 중 ---" -ForegroundColor Cyan
Push-Location $FRONTEND_DIR
if (-not (Test-Path "node_modules")) {
    Write-Host "npm 패키지 설치 중..."
    npm install
}
Pop-Location

# 3. 서비스 실행
Write-Host "`n🚀 서비스를 시작합니다..." -ForegroundColor Green

# 백엔드 실행 (새 창)
$refreshEnv = '$env:Path = [System.Environment]::GetEnvironmentVariable(''Path'',''Machine'') + '';'' + [System.Environment]::GetEnvironmentVariable(''Path'',''User'')'
Start-Process powershell -ArgumentList "-NoExit", "-Command", "$refreshEnv; .\backend\.venv\Scripts\activate; uvicorn backend.main:app --host 0.0.0.0 --port 3501 --reload" -WindowStyle Normal

# 프론트엔드 실행 (새 창)
Write-Host "백엔드: http://localhost:3501"
Write-Host "프론트엔드: http://localhost:3500"

Start-Process powershell -ArgumentList "-NoExit", "-Command", "$refreshEnv; cd frontend; npm run dev -- -p 3500" -WindowStyle Normal

Write-Host "`n✅ 실행 완료! 브라우저에서 http://localhost:3500 을 확인하세요." -ForegroundColor Yellow