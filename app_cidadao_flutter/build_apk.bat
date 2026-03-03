@echo off
setlocal
cd /d "%~dp0"

where flutter >nul 2>nul
if errorlevel 1 (
  echo [ERRO] Flutter nao encontrado no PATH.
  echo Instale o Flutter: https://docs.flutter.dev/get-started/install/windows
  pause
  exit /b 1
)

echo [1/4] Verificando estrutura Android...
if not exist "android" (
  flutter create --platforms=android .
  if errorlevel 1 (
    echo [ERRO] Falha ao criar estrutura Android.
    pause
    exit /b 1
  )
)

echo [2/4] Instalando dependencias...
flutter pub get
if errorlevel 1 (
  echo [ERRO] Falha no flutter pub get.
  pause
  exit /b 1
)

echo [3/4] Compilando APK (release)...
flutter build apk --release
if errorlevel 1 (
  echo [ERRO] Falha ao compilar APK.
  pause
  exit /b 1
)

echo [4/4] APK gerado com sucesso:
echo %cd%\build\app\outputs\flutter-apk\app-release.apk
pause
endlocal
