# Contrato da API — JAS Easy Path (Front-end ↔ Back-end)

> **Status:** Proposta de contrato para alinhamento entre front-end e back-end (issues #6, #7 e #8).  
> Os pontos marcados com **(a confirmar)** são sugestões iniciais do front-end e podem ser ajustados conforme o modelo do servidor. Todos os payloads de exemplo abaixo já foram validados com o tradutor (`mappers.ts`).

## 1. Decisões de Integração

Para manter o front-end desacoplado das estruturas internas do solver (OR-Tools), a API atua como camada de tradução. Abaixo está o resumo do que definimos para cada ponto da integração:

| Tópico | Decisão proposta | Absorvido em |
|---|---|---|
| **IDs** (texto no front vs. inteiro no motor) | A API usa **inteiro** em todo `id` e `delivery_id`, devolvendo sempre o ID real da entidade (nunca o índice na matriz do motor). O front-end converte para texto no mapeador **(a confirmar)** | `mappers.ts` |
| **Localização** (`lat`/`lng` vs. `location.latitude/longitude`) | Objeto estruturado `location: { latitude, longitude }`. Quando ainda não houver coordenadas, retorna `location: null` acompanhado de `geocoding_status` (`pending` ou `failed`) e `geocoding_message` | `dto.ts`, `mappers.ts` |
| **Carga** (demanda e capacidade) | `demand` inteiro por entrega e `capacity` inteiro por veículo, **na mesma unidade** (a definir, ex.: volumes). Enquanto o formulário não tiver esse campo, o front-end envia **1** por pedido (`DEFAULT_DEMAND`) e os veículos ficam configurados no back-end **(a confirmar)** | `dto.ts`, `mappers.ts` |
| **Horários e Janelas** | `time_window: { start, end }` em **minutos desde 00:00** (`0` a `1440`, onde `1440 = 24:00`). No cadastro, `time_window: null` indica ausência de janela própria (vale o expediente do servidor). Nas respostas, `time_window` já vem resolvida e `has_explicit_time_window` indica se foi informada | `dto.ts`, `mappers.ts` |
| **Unidades de Medida** | Distância em **metros inteiros** (`distance_m`), horários do dia em `*_minute_of_day` e durações em `*_min`, com `total_min = travel_min + wait_min + service_min` **(a confirmar)**. O front-end converte metros para km | `mappers.ts` |
| **Resultado da Otimização** | `routes` retorna uma lista (uma rota por veículo) e `unassigned` lista entregas não atendidas com o motivo. Solução parcial retorna HTTP `200` com `solution_status: "partial"`; entrada inválida ou rota inviável retornam HTTP `422` com corpo `error` **(a confirmar)** | `dto.ts`, `mappers.ts` |
| **Exemplos Compartilhados** | Payloads completos na Seção 5 validados diretamente contra o tradutor do front-end | `mappers.ts` |

## 2. Convenções

- **Base URL:** O front-end monta as requisições a partir de `VITE_API_URL` (ex.: `http://localhost:8000/v1`), permitindo versionar a API sem alterar código.
- **Formato e Fuso:** Payloads em `snake_case`, considerando o fuso horário local do estabelecimento.
- **Horário do dia:** Inteiro de `0` a `1440` representando minutos desde `00:00` (ex.: `19:00` = `1140`, `19:30` = `1170`, `24:00` = `1440`).
- **Durações:** Minutos decorridos em campos terminados em `*_min`.
- **Timestamps de eventos:** ISO 8601 com fuso (`completed_at`, `history[].at`), como `"2026-11-19T19:50:00-03:00"`. O front-end exibe o horário literal (`19:50`) sem conversão de fuso.
- **Regras de janela de entrega:**
  - Janela ausente (`null`) herda o expediente padrão do estabelecimento.
  - Janela explícita precisa comportar o tempo fixo de atendimento de 8 minutos (`end - start >= 8`).
  - O atendimento precisa encerrar dentro da janela (`departure_minute_of_day <= end`).
  - Limites válidos: `start >= 0`, `end <= 1440` e `start < end`.
- Entregas sem coordenadas (`location: null`) nunca entram em `stops` de uma rota.

## 3. Endpoints

| Método | Caminho | Corpo | Resposta |
|---|---|---|---|
| `GET` | `/deliveries` | — | `200` com lista de `Delivery` |
| `POST` | `/deliveries` | `NewDelivery` | `201` com `Delivery` |
| `POST` | `/deliveries/bulk` | lista de `NewDelivery` | `201` com lista de `Delivery` (mesma ordem) |
| `DELETE` | `/deliveries/{id}` | — | `204` (sem conteúdo) |
| `POST` | `/deliveries/{id}/complete` | `{ "at": "HH:mm" }` | `200` com `Delivery` atualizada |
| `POST` | `/deliveries/{id}/issue` | `{ "reason", "note", "at" }` | `200` com `Delivery` atualizada |
| `GET` | `/routes/today` | — | `200` com `RoutePlan` |
| `POST` | `/routes/today/optimize` | — | `200` com `RoutePlan` |
| `POST` | `/routes/today/share` | — | `200` com `{ "url": "..." }` |

**Notas de comportamento:**
- O campo `at` em `complete` e `issue` é informativo (hora local exibida no app); o servidor deve registrar o próprio relógio como fonte oficial.
- `GET /routes/today` e `POST /routes/today/optimize` retornam exatamente a mesma estrutura (`RoutePlan`).
- Falhas na geocodificação não bloqueiam o cadastro: o pedido é salvo com `geocoding_status: "failed"` para que o lojista possa corrigir o endereço na tela.

## 4. Estruturas e Valores Permitidos

- **`Delivery` (resposta):** `id`, `order_code`, `customer_name`, `phone`, `address`, `location` (ou `null`), `geocoding_status`, `geocoding_message`, `demand`, `time_window` (efetiva), `has_explicit_time_window`, `priority`, `status`, `notes`, `issue_reason`, `completed_at`, `history`.
- **`NewDelivery` (entrada):** `order_code`, `customer_name`, `phone`, `address`, `demand`, `time_window` (ou `null`), `priority`, `notes` (não envia coordenadas).
- **`RoutePlan`:** `id`, `status`, `solution_status`, `origin`, `routes`, `unassigned`, `matrix_source`.

**Domínio de valores (Enums):**
- `status` da entrega: `waiting_departure`, `in_progress`, `completed`, `issue` *(o status "atrasada" é calculado dinamicamente pelo front-end)*.
- `priority`: `low`, `normal`, `high`.
- `issue_reason`: `customer_absent`, `address_not_found`, `customer_refused`, `operational`, `other`.
- `geocoding_status`: `ok`, `pending`, `failed`.
- `solution_status`: `solved` (todas atendidas) ou `partial` (há itens em `unassigned`).
- `unassigned[].reason`: `time_window`, `capacity`, `geocoding_failed`, `other`.
- `matrix_source`: `manual` (matriz informada manualmente / estimativa) ou `road_network` (distâncias e tempos reais por malha viária).

## 5. Exemplos de Requisição e Resposta

### 5.1 Cadastrar entrega com janela própria (`POST /deliveries`)

**Requisição:**
```json
{
  "order_code": null,
  "customer_name": "Maria Souza",
  "phone": "(71) 98888-1234",
  "address": "Rua das Flores, 10 - Centro",
  "demand": 1,
  "time_window": { "start": 1140, "end": 1170 },
  "priority": "normal",
  "notes": "Portão azul"
}
```

**Resposta `201`:**
```json
{
  "id": 101,
  "order_code": "#1001",
  "customer_name": "Maria Souza",
  "phone": "(71) 98888-1234",
  "address": "Rua das Flores, 10 - Centro",
  "location": { "latitude": -12.969, "longitude": -38.499 },
  "geocoding_status": "ok",
  "geocoding_message": null,
  "demand": 2,
  "time_window": { "start": 1140, "end": 1170 },
  "has_explicit_time_window": true,
  "priority": "normal",
  "status": "waiting_departure",
  "notes": "Portão azul",
  "issue_reason": null,
  "completed_at": null,
  "history": [{ "at": "2026-11-19T18:00:00-03:00", "text": "Pedido cadastrado" }]
}
```

### 5.2 Cadastrar entrega sem janela (`POST /deliveries`)

**Requisição (`time_window: null`):**
```json
{
  "order_code": null,
  "customer_name": "João Pedro Reis",
  "phone": null,
  "address": "Av. J, 21 - Pituba",
  "demand": 1,
  "time_window": null,
  "priority": "normal",
  "notes": null
}
```

**Resposta `201` (janela efetiva resolvida pelo expediente, `18:00` às `24:00`):**
```json
{
  "id": 107,
  "order_code": "#1007",
  "customer_name": "João Pedro Reis",
  "phone": null,
  "address": "Av. J, 21 - Pituba",
  "location": {
    "latitude": -13.002,
    "longitude": -38.465
  },
  "geocoding_status": "ok",
  "geocoding_message": null,
  "demand": 1,
  "time_window": {
    "start": 1080,
    "end": 1440
  },
  "has_explicit_time_window": false,
  "priority": "normal",
  "status": "waiting_departure",
  "notes": null,
  "issue_reason": null,
  "completed_at": null,
  "history": [
    {
      "at": "2026-11-19T18:10:00-03:00",
      "text": "Pedido cadastrado"
    }
  ]
}
```

### 5.3 Listar entregas (`GET /deliveries`)

**Resposta `200` (com uma entrega geocodificada e outra com falha de localização):**
```json
[
  {
    "id": 101,
    "order_code": "#1001",
    "customer_name": "Maria Souza",
    "phone": "(71) 98888-1234",
    "address": "Rua das Flores, 10 - Centro",
    "location": {
      "latitude": -12.969,
      "longitude": -38.499
    },
    "geocoding_status": "ok",
    "geocoding_message": null,
    "demand": 2,
    "time_window": {
      "start": 1140,
      "end": 1170
    },
    "has_explicit_time_window": true,
    "priority": "normal",
    "status": "waiting_departure",
    "notes": "Portão azul",
    "issue_reason": null,
    "completed_at": null,
    "history": [
      {
        "at": "2026-11-19T18:00:00-03:00",
        "text": "Pedido cadastrado"
      }
    ]
  },
  {
    "id": 106,
    "order_code": "#1006",
    "customer_name": "Olívia Campos",
    "phone": "(71) 98888-5555",
    "address": "Travessa sem nome, s/n",
    "location": null,
    "geocoding_status": "failed",
    "geocoding_message": "Endereço não encontrado.",
    "demand": 1,
    "time_window": {
      "start": 1080,
      "end": 1440
    },
    "has_explicit_time_window": false,
    "priority": "low",
    "status": "waiting_departure",
    "notes": "Casa de esquina",
    "issue_reason": null,
    "completed_at": null,
    "history": [
      {
        "at": "2026-11-19T18:05:00-03:00",
        "text": "Pedido cadastrado"
      }
    ]
  }
]
```

### 5.4 Cadastro em lote (`POST /deliveries/bulk`)

**Requisição:**
```json
[
  {
    "order_code": null,
    "customer_name": "Maria Souza",
    "phone": "(71) 98888-1234",
    "address": "Rua das Flores, 10 - Centro",
    "demand": 1,
    "time_window": {
      "start": 1140,
      "end": 1170
    },
    "priority": "normal",
    "notes": "Portão azul"
  },
  {
    "order_code": null,
    "customer_name": "João Pedro Reis",
    "phone": null,
    "address": "Av. J, 21 - Pituba",
    "demand": 1,
    "time_window": null,
    "priority": "normal",
    "notes": null
  }
]
```

**Resposta `201` (preservando a ordem de envio):**
```json
[
  {
    "id": 101,
    "order_code": "#1001",
    "customer_name": "Maria Souza",
    "phone": "(71) 98888-1234",
    "address": "Rua das Flores, 10 - Centro",
    "location": {
      "latitude": -12.969,
      "longitude": -38.499
    },
    "geocoding_status": "ok",
    "geocoding_message": null,
    "demand": 2,
    "time_window": {
      "start": 1140,
      "end": 1170
    },
    "has_explicit_time_window": true,
    "priority": "normal",
    "status": "waiting_departure",
    "notes": "Portão azul",
    "issue_reason": null,
    "completed_at": null,
    "history": [
      {
        "at": "2026-11-19T18:00:00-03:00",
        "text": "Pedido cadastrado"
      }
    ]
  },
  {
    "id": 107,
    "order_code": "#1007",
    "customer_name": "João Pedro Reis",
    "phone": null,
    "address": "Av. J, 21 - Pituba",
    "location": {
      "latitude": -13.002,
      "longitude": -38.465
    },
    "geocoding_status": "ok",
    "geocoding_message": null,
    "demand": 1,
    "time_window": {
      "start": 1080,
      "end": 1440
    },
    "has_explicit_time_window": false,
    "priority": "normal",
    "status": "waiting_departure",
    "notes": null,
    "issue_reason": null,
    "completed_at": null,
    "history": [
      {
        "at": "2026-11-19T18:10:00-03:00",
        "text": "Pedido cadastrado"
      }
    ]
  }
]
```

### 5.5 Concluir entrega (`POST /deliveries/103/complete`)

**Requisição:**
```json
{
  "at": "19:50"
}
```

**Resposta `200`:**
```json
{
  "id": 103,
  "order_code": "#1003",
  "customer_name": "João Pedro Reis",
  "phone": null,
  "address": "Av. J, 21 - Pituba",
  "location": { "latitude": -13.002, "longitude": -38.465 },
  "geocoding_status": "ok",
  "geocoding_message": null,
  "demand": 3,
  "time_window": { "start": 1080, "end": 1440 },
  "has_explicit_time_window": false,
  "priority": "normal",
  "status": "completed",
  "notes": null,
  "issue_reason": null,
  "completed_at": "2026-11-19T19:50:00-03:00",
  "history": [
    { "at": "2026-11-19T18:00:00-03:00", "text": "Pedido cadastrado" },
    { "at": "2026-11-19T19:50:00-03:00", "text": "Entrega concluída" }
  ]
}
```

### 5.6 Registrar pendência (`POST /deliveries/101/issue`)

**Requisição:**
```json
{
  "reason": "customer_absent",
  "note": "Ninguém atendeu",
  "at": "19:55"
}
```

**Resposta `200`:**
```json
{
  "id": 101,
  "order_code": "#1001",
  "customer_name": "Maria Souza",
  "phone": "(71) 98888-1234",
  "address": "Rua das Flores, 10 - Centro",
  "location": {
    "latitude": -12.969,
    "longitude": -38.499
  },
  "geocoding_status": "ok",
  "geocoding_message": null,
  "demand": 2,
  "time_window": {
    "start": 1140,
    "end": 1170
  },
  "has_explicit_time_window": true,
  "priority": "normal",
  "status": "issue",
  "notes": "Ninguém atendeu",
  "issue_reason": "customer_absent",
  "completed_at": null,
  "history": [
    {
      "at": "2026-11-19T18:00:00-03:00",
      "text": "Pedido cadastrado"
    },
    {
      "at": "2026-11-19T19:55:00-03:00",
      "text": "Pendência: Cliente ausente"
    }
  ]
}
```

### 5.7 Plano do dia (`GET /routes/today` e `POST /routes/today/optimize`)

O `optimize` não exige corpo na requisição; os veículos e o expediente vêm da configuração do back-end **(a confirmar)**.

**Resposta `200` (solução completa — `total_min = 41 + 25 + 32 = 98`):**
```json
{
  "id": 1,
  "status": "running",
  "solution_status": "solved",
  "origin": {
    "name": "Pizzaria Forno Bom",
    "address": "Rua das Palmeiras, 100 - Centro",
    "location": { "latitude": -12.9714, "longitude": -38.5014 }
  },
  "routes": [
    {
      "vehicle": { "id": 1, "name": "Moto 1", "capacity": 10 },
      "stops": [
        { "delivery_id": 101, "arrival_minute_of_day": 1148, "departure_minute_of_day": 1156 },
        { "delivery_id": 102, "arrival_minute_of_day": 1163, "departure_minute_of_day": 1171 },
        { "delivery_id": 103, "arrival_minute_of_day": 1180, "departure_minute_of_day": 1188 },
        { "delivery_id": 104, "arrival_minute_of_day": 1205, "departure_minute_of_day": 1238 }
      ],
      "load": 8,
      "distance_m": 11800,
      "travel_min": 41,
      "wait_min": 25,
      "service_min": 32,
      "total_min": 98
    }
  ],
  "unassigned": [],
  "matrix_source": "manual"
}
```

**Resposta `200` (solução parcial — entrega `105` fora de janela):**
```json
{
  "id": 1,
  "status": "running",
  "solution_status": "partial",
  "origin": {
    "name": "Pizzaria Forno Bom",
    "address": "Rua das Palmeiras, 100 - Centro",
    "location": {
      "latitude": -12.9714,
      "longitude": -38.5014
    }
  },
  "routes": [
    {
      "vehicle": {
        "id": 1,
        "name": "Moto 1",
        "capacity": 10
      },
      "stops": [
        {
          "delivery_id": 101,
          "arrival_minute_of_day": 1148,
          "departure_minute_of_day": 1156
        },
        {
          "delivery_id": 102,
          "arrival_minute_of_day": 1163,
          "departure_minute_of_day": 1171
        },
        {
          "delivery_id": 103,
          "arrival_minute_of_day": 1180,
          "departure_minute_of_day": 1188
        },
        {
          "delivery_id": 104,
          "arrival_minute_of_day": 1205,
          "departure_minute_of_day": 1238
        }
      ],
      "load": 8,
      "distance_m": 11800,
      "travel_min": 41,
      "wait_min": 25,
      "service_min": 32,
      "total_min": 98
    }
  ],
  "unassigned": [
    {
      "delivery_id": 105,
      "reason": "time_window"
    }
  ],
  "matrix_source": "manual"
}
```

**Resposta `200` (estado inicial, antes da primeira otimização):**
```json
{
  "id": 1,
  "status": "planned",
  "solution_status": "solved",
  "origin": {
    "name": "Pizzaria Forno Bom",
    "address": "Rua das Palmeiras, 100 - Centro",
    "location": {
      "latitude": -12.9714,
      "longitude": -38.5014
    }
  },
  "routes": [],
  "unassigned": [],
  "matrix_source": "manual"
}
```

### 5.8 Compartilhar rota (`POST /routes/today/share`)

**Resposta `200`:**
```json
{
  "url": "https://app.exemplo.com.br/entregador?token=abc123"
}
```

### 5.9 Erros de Validação e Otimização (`HTTP 422`)

**Entrada inválida (ex.: item de índice `2` no lote com janela menor que 8 minutos):**
```json
{
  "error": {
    "code": "validation_error",
    "message": "A requisição tem campos inválidos.",
    "details": [
      {
        "field": "time_window",
        "code": "time_window_too_short",
        "message": "A janela precisa comportar 8 minutos de atendimento (início 1140, fim 1145).",
        "index": 2
      }
    ]
  }
}
```

**Sem solução viável em `POST /routes/today/optimize` (o plano anterior permanece válido):**
```json
{
  "error": {
    "code": "no_feasible_solution",
    "message": "O motor não encontrou rota que atenda as janelas e a capacidade.",
    "details": []
  }
}
```

## 6. Padrão de Erro

```json
{
  "error": {
    "code": "validation_error",
    "message": "Mensagem legível para exibição",
    "details": [{ "field": "campo", "code": "codigo_detalhe", "message": "detalhe", "index": null }]
  }
}
```

- `error.code`: `validation_error` ou `no_feasible_solution` **(a confirmar)**.
- `details[].index`: posição do item em envios em lote (`null` em requisições unitárias).
- Códigos sugeridos em `details[].code`: `required`, `invalid_format`, `time_window_too_short`, `time_window_out_of_range`, `capacity_exceeded`.

## 7. Mapeamento no Front-end (`mappers.ts`)

| Campo na API | Campo no Front (`domain.ts`) | Regra de conversão |
|---|---|---|
| `id` (inteiro) | `id` (texto) | `String(id)` (aplicado também a `delivery_id` em `stops`) |
| `location.latitude/longitude` | `lat` / `lng` | `location: null` assume `0` e nunca entra em `stops` |
| `time_window.start/end` (min) | `windowStart` / `windowEnd` (`"HH:mm"`) | `1440` converte para `"24:00"` |
| `time_window: null` no envio | Campos de janela vazios no formulário | Preencher apenas um dos horários gera erro de validação |
| `demand` | — | Envio padrão com `DEFAULT_DEMAND = 1` |
| `completed_at`, `history[].at` | `"HH:mm"` | Extrai o horário literal sem deslocar fuso |
| `routes[0].distance_m` | `distanceKm` | Divide por `1000` com 1 casa decimal |
| `routes[0].total_min` | `durationMin` | Soma de deslocamento, espera e atendimento |
| `routes[0].vehicle.name` | `driverName` | Quando `routes` está vazio: `"Sem veículo atribuído"` |
| `routes[0].stops[].delivery_id` | `stopIds` | Mantém a ordem exata retornada pelo solver |
| `matrix_source: "manual"` | `isSimulation: true` | Sinaliza na interface que os tempos são estimados |
| `routes.length > 1` | Erro controlado | O MVP exibe apenas uma rota por vez (1 veículo) |

**Adaptações temporárias do MVP:**
- Pedidos com `geocoding_status: "failed"` que ainda não saíram são exibidos como **Pendência** (`address_not_found`) com a mensagem do servidor anexada às observações.
- Campos como `unassigned`, `solution_status`, horário previsto por parada, `demand` e `capacity` ficam prontos no DTO, mas ainda não são renderizados na UI.

## 8. Próximos Ajustes no Front-end (Fora do Contrato)

- `src/utils/csv.ts`: propagar erros estruturais do `Papa.parse` (aspas abertas, colunas extras) para feedback por arquivo ou linha.
- `src/utils/validation.ts`: aceitar janela totalmente vazia, exigir mínimo de 8 minutos (`end - start >= 8`) quando preenchida e aceitar `24:00` como limite final.
- `src/services/http.ts`: extrair `error.message` do corpo das respostas `422` para exibir mensagens claras na interface.
- `src/utils/geo.ts` e `RoutePage.tsx`: igualar o tempo de atendimento do mock para 8 minutos e ajustar o selo de simulação para *"Estimativa: matriz manual"*.
- Testes automatizados: adicionar Vitest e converter os payloads da Seção 5 em testes unitários (`mappers.test.ts`).

## 9. Pontos para Alinharmos Juntos

Para fecharmos a integração sem surpresas no código, vale confirmarmos estes detalhes entre front-end e back-end:

- **Identificadores e Carga:** Usamos IDs inteiros na API (convertidos para texto no front-end)? Qual unidade adotaremos para `demand` e `capacity`, e no MVP cada pedido entra com carga padrão `1`?
- **Expediente e Duração:** Qual será a janela padrão de funcionamento configurada no servidor (ex.: `18:00` às `24:00`) e precisamos expor isso em algum endpoint? O `total_min` já soma deslocamento, espera e os 8 minutos de atendimento?
- **Fluxo de Otimização:** Antes de rodar a primeira otimização, `routes` retorna vazio (`[]`) ou já vem uma sequência inicial por ordem de cadastro? O MVP vai operar com apenas um veículo ou já exibirá múltiplos veículos na tela?
- **Erros e Matriz:** HTTP `422` com `error.code` (`validation_error` e `no_feasible_solution`) atende bem ao back-end? Os valores `manual` e `road_network` em `matrix_source` cobrem os cenários previstos?
- **Geocodificação e Link do Entregador:** Quando um endereço falhar na geocodificação, o próprio lojista corrige pela edição da entrega? O `/routes/today/share` vai gerar uma URL com token público para o entregador acessar sem login?