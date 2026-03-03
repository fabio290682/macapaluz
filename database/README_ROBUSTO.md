# Banco robusto (SQLite)

Arquivos:
- `database/sqlite_schema_robust.sql`: schema robusto com historico, auditoria e indices extras.
- `scripts/build_robust_db.py`: cria `macapaluz_robusto.db` migrando dados do `macapaluz.db`.

## Como criar

```powershell
python scripts/build_robust_db.py
```

Saida esperada:
- arquivo `macapaluz_robusto.db`
- resumo de contagem por tabela

## Diferencas principais

- Integridade:
  - validacoes extras para email, latitude/longitude, potencia, altura.
  - referencias para bairro (`bairro_id`) e novas tabelas relacionais.
- Rastreabilidade:
  - `pontos_ilp_historico` para trilha de alteracoes em pontos.
  - `ordens_servico_eventos` para eventos de ciclo de vida da OS.
  - `import_lotes` para controle de cargas/migracoes.
  - `auditoria_api` para auditoria de chamadas.
- Performance:
  - indices compostos para filtros operacionais.
  - views prontas para dashboard e analise por bairro.

## Observacao

- O historico de exclusao de ponto e preservado sem FK direta para `pontos_ilp`,
  evitando bloqueio de `DELETE` por integridade referencial.
