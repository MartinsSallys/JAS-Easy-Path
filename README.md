# JAS - Easy Path 

Proposta de uma ferramenta simples para organizar rotas de entrega de pequenos e médios comércios.

## Problema

Lojas com poucas dezenas de entregas por dia costumam organizar as paradas manualmente, usando a memória ou um mapa. Isso pode aumentar a distância percorrida, atrasar entregas com horário combinado, aumentar custos e deixar clientes insatisfeitos. Ferramentas profissionais de roteirização podem ser caras ou complexas para essas operações.

## Solução

O JAS - Easy Path organiza as entregas do dia e sugere uma sequência de paradas. O lojista informa os endereços e, quando necessário, as janelas de entrega e os dados do veículo. A rota pode ser compartilhada com o entregador, que abre as paradas em seu aplicativo de navegação. Ao final, registra entregas concluídas e pendências.

**Exemplo:** uma pizzaria informa 15 pedidos e seus endereços. O JAS - Easy Path sugere a ordem das paradas; o entregador abre a rota no Google Maps ou no Waze e registra os pedidos entregues ou pendentes.

## Escopo inicial

- Cadastro manual ou importação de entregas por planilha.
- Organização das paradas, com suporte a horários e capacidade do veículo.
- Compartilhamento da rota por link e abertura em aplicativo de navegação.
- Registro de entregas e pendências, com resumo diário de distância e tempo.

## Estado atual

O MVP está funcional e em desenvolvimento ativo. O repositório é um monorepo com quatro partes:

- **`route_engine/`** — motor de otimização em Python com Google OR-Tools. Valida o problema (CVRP com janelas de entrega e capacidade) e devolve a sequência de paradas por veículo.
- **`backend/`** — API FastAPI (Python 3.11+). Cadastro, edição e exclusão de entregas, depósitos, veículos e rotas; geocodificação via Nominatim; otimização delegada ao `route_engine`. Persistência em PostgreSQL (asyncpg + Alembic); os testes rodam em SQLite.
- **`apps/frontend/`** — aplicação React + Vite. Telas de entregas (cadastro manual, edição, exclusão, importação CSV), rota no mapa (Leaflet), visão do entregador e dashboard de KPIs.
- **`docs/`** — `api.md` (contrato entre frontend e backend) e `arquitetura-mvp.md` (decisões do MVP).

Os arquivos `index.html` e `app.html` na raiz são a apresentação interna do Hack Brasil, não a aplicação — basta abri-los no navegador para visualizá-los.

## Como rodar

### Opção 1 — Só o frontend (modo demo, sem backend)

```bash
cd apps/frontend
npm install
npm run dev   # http://localhost:5173
```

Com `VITE_USE_MOCK=true` (padrão do `.env.example`) o app usa dados fictícios — não precisa de backend, banco nem serviços externos.

### Opção 2 — Stack completa local

**Banco de dados** — suba o PostgreSQL via Docker:

```bash
docker compose up postgres
```

Ou use SQLite sem instalar nada, definindo a variável antes de subir a API:

```bash
# Linux/macOS
export DATABASE_URL="sqlite+aiosqlite:///./dev.db"
# Windows (PowerShell)
$env:DATABASE_URL = "sqlite+aiosqlite:///./dev.db"
```

As tabelas são criadas automaticamente na inicialização da API.

**Backend:**

```bash
cd backend
pip install -e ".[dev]"          # instala também o route_engine local
uvicorn app.main:app --reload    # http://localhost:8000 — docs em /docs
```

**Frontend** — com o backend de pé, aponte o app para a API real:

```bash
cd apps/frontend
npm install
# em .env.local: VITE_USE_MOCK=false e VITE_API_URL=http://localhost:8000/api/v1
npm run dev
```

Observações:

- `ORS_API_KEY` (OpenRouteService) é opcional: sem ela, a matriz de custos usa distância em linha reta (Haversine).
- O serviço `frontend` do `docker-compose.yml` ainda não possui Dockerfile — rode o app via `npm` como acima.

## Testes e verificação

| Componente | Comando |
| --- | --- |
| Backend | `cd backend && pytest` |
| Route engine | `pytest` na raiz (Python ≥ 3.14, deps via Poetry) |
| Frontend | `cd apps/frontend && npm test` (Vitest) |
| Lint backend | `cd backend && ruff check app tests` |
| Lint frontend | `cd apps/frontend && npm run lint` (oxlint) |
| Typecheck | `cd apps/frontend && npx tsc -b` |
