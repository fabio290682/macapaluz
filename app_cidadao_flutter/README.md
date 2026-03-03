# App Cidadao (Flutter - Android)

Aplicativo para o cidadao enviar ocorrencia e abrir O.S. no local (GPS).

## Requisitos (Android)

- Flutter SDK instalado
- Android Studio com SDK Android
- API CIPEMAC ativa (`/app-cidadao/solicitacoes`)

## Gerar plataforma Android

Dentro da pasta `app_cidadao_flutter`:

```bash
flutter create --platforms=android .
```

Ou use o script:

```bat
build_apk.bat
```

## Dependencias

```bash
flutter pub get
```

## Rodar no Android

```bash
flutter run --dart-define=API_BASE=http://SEU_BACKEND:8001
```

Ou use o script (debug):

```bat
run_android_debug.bat http://10.0.2.2:8001
```

Exemplos de `API_BASE`:
- Android emulador: `http://10.0.2.2:8001`
- Dispositivo fisico: `http://IP_DA_MAQUINA:8001`
- Producao: `https://seu-backend.onrender.com`

## AndroidManifest (obrigatorio)

No arquivo `android/app/src/main/AndroidManifest.xml` adicione:

```xml
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION"/>
<uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION"/>
```

Se usar API local em `http://...`, no `<application>` adicione:

```xml
android:usesCleartextTraffic="true"
```

## APK final

Depois de compilar:

`build\app\outputs\flutter-apk\app-release.apk`

## Fluxo

1. Cidadao preenche nome e descricao.
2. App captura GPS atual.
3. Envia para o portal (`POST /app-cidadao/solicitacoes`).
4. Backend abre O.S. no ponto mais proximo ou cria ponto novo no local.
