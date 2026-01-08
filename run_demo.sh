#!/bin/bash

# Kill ports 3500 and 3501 if already in use (Mac/Linux)
lsof -ti:3500 | xargs kill -9 2>/dev/null
lsof -ti:3501 | xargs kill -9 2>/dev/null

echo "백엔드 (FastAPI) 시작 중... (포트 3501)"
source backend/.venv/bin/activate
# Run with uvicorn directly for better control and reloading
uvicorn backend.main:app --host 0.0.0.0 --port 3501 --reload &
BACKEND_PID=$!

echo "프론트엔드 (Next.js) 시작 중... (포트 3500)"
cd frontend
# Using nice to give backend a head start, though not strictly necessary
npm run dev -- -p 3500 &
FRONTEND_PID=$!

echo "🚀 데모가 실행되었습니다!"
echo "👉 접속 주소: http://localhost:3500"

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
