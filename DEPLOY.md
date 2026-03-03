# Deploy checklist

## 1) Validar local

```powershell
python scripts/build_robust_db.py
python api/server.py
```

Verifique:
- `GET /health`
- `GET /dashboard/summary`
- abertura de `http://127.0.0.1:8001/`

## 2) Configurar ambiente

Copie `.env.example` e ajuste:
- `GOOGLE_MAPS_API_KEY`
- `MACAPALUZ_API_BASE` (se frontend e backend ficarem em dominios diferentes)

## 3) Render (Blueprint)

Arquivo pronto: `render.yaml`.

No Render:
1. New + Blueprint
2. Selecionar repositorio/projeto
3. Confirmar variaveis
4. Deploy

## 4) Pos-deploy

Testes minimos:
- `GET /health`
- `GET /pontos-ilp?limit=5`
- `GET /config.js`
- carregar pagina inicial `/`
