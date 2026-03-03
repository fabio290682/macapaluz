@echo off
setlocal
cd /d "%~dp0"

where flutter >nul 2>nul
if errorlevel 1 (
  echo [ERRO] Flutter nao encontrado no PATH.
  pause
  exit /b 1
)

if "%~1"=="" (
  set API_BASE=http://10.0.2.2:8001
) else (
  set API_BASE=%~1
)

if not exist "android" (
  flutter create --platforms=android .
  if errorlevel 1 (
    echo [ERRO] Falha ao criar estrutura Android.
    pause
    exit /b 1
  )
)

flutter pub get
if errorlevel 1 (
  echo [ERRO] Falha no flutter pub get.
  pause
  exit /b 1
)

echo Executando app com API_BASE=%API_BASE%
flutter run --dart-define=API_BASE=%API_BASE%
endlocal
