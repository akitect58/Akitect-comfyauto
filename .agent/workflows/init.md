---
description: 프로젝트 초기화 (Backend & Frontend 설정)
---

# 프로젝트 환경 설정

이 워크플로우는 백엔드 가상환경 설정과 프론트엔드 패키지 설치를 진행합니다.

## 1. 사전 요구사항 확인

Python 3.12+ 및 Node.js (LTS)가 설치되어 있는지 확인해주세요.

```powershell
python --version
npm --version
```

## 2. 백엔드 설정

백엔드 폴더(`backend`)에서 가상환경을 생성하고 필수 라이브러리를 설치합니다.
(명령어는 `backend` 디렉토리 기준입니다)

// turbo
가상환경(.venv) 생성:
```powershell
python -m venv .venv
```

환경변수 파일(.env) 설정:
```powershell
if (Test-Path ".env.example") { if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" } }
```

구성 파일(config.json) 생성:
```powershell
if (-not (Test-Path "config.json")) {
    $conf = @{ openai_api_key=""; comfyui_path=""; prompts=@{} }
    $conf | ConvertTo-Json | Set-Content "config.json" -Encoding UTF8
}
```

라이브러리 설치:
```powershell
.venv\Scripts\python -m pip install -r requirements.txt
```

## 3. 프론트엔드 설정

프론트엔드 폴더(`frontend`)에서 패키지를 설치합니다.
(명령어는 `frontend` 디렉토리 기준입니다)

// turbo
패키지 설치:
```powershell
npm install
```
