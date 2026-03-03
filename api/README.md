# MacapaLuz API

API HTTP local/producao baseada em SQLite.

## Banco usado

- padrao: `macapaluz_robusto.db` (se existir)
- fallback: `macapaluz.db`
- override: variavel `MACAPALUZ_DB_PATH`

## Executar

```powershell
python api/server.py
```

Importante:
- nao abra o HTML por `file://`.
- abra sempre por `http://127.0.0.1:8001/`.

Servidor padrao:
- `http://0.0.0.0:8001`

## Variaveis de ambiente

- `HOST` (default `0.0.0.0`)
- `PORT` (default `8001`)
- `MACAPALUZ_DB_PATH` (opcional)
- `MACAPALUZ_FRONTEND_FILE` (default `macapaluz-v3.html`)
- `GOOGLE_MAPS_API_KEY` (opcional)
- `MACAPALUZ_API_BASE` (opcional; usado no `config.js`)

Exemplo PowerShell:

```powershell
$env:HOST="0.0.0.0"
$env:PORT="8001"
$env:MACAPALUZ_DB_PATH="D:\macapáluz\macapaluz_robusto.db"
$env:GOOGLE_MAPS_API_KEY="<sua-chave>"
python api/server.py
```

## Rotas principais

- `GET /` e `GET /app` (frontend)
- `GET /config.js` (injeta `window.GOOGLE_MAPS_API_KEY` e `window.MACAPALUZ_API_BASE`)
- `GET /health`
- `GET /dashboard/summary`
- `GET /qualidade/summary`
- `GET /pontos-ilp`
- `GET /pontos-ilp/{id}`
- `GET /pontos-ilp/map`
- `POST /pontos-ilp`
- `PUT /pontos-ilp/{id}`
- `DELETE /pontos-ilp/{id}`
- `GET /ordens-servico`
- `GET /ordens-servico/{id}`
- `POST /ordens-servico`
- `PUT /ordens-servico/{id}`
- `DELETE /ordens-servico/{id}`
- `POST /import/file` (upload em base64 para KMZ/KML/CSV/XLSX de pontos)

## Exemplo rapido

```powershell
Invoke-RestMethod "http://127.0.0.1:8001/health"
Invoke-RestMethod "http://127.0.0.1:8001/pontos-ilp?limit=5"
```
