# Contrato da API — JAS Easy Path (MVP)

Este documento especifica o contrato HTTP/JSON entre o front-end (`apps/frontend`) e o back-end/motor de otimização (`route_engine` / OR-Tools), alinhado às issues **#5**, **#6**, **#7** e **#8**.

> **Nota de arquitetura:** O back-end atua como adaptador entre este contrato REST e os modelos internos do `route_engine`, sem expor estruturas internas do OR-Tools diretamente ao navegador.

---

## 1. Convenções Gerais

| Regra | Padrão adotado | Exemplo |
| :--- | :--- | :--- |
| **Nomenclatura JSON** | `snake_case` em todos os payloads | `customer_name`, `time_window` |
| **Identificadores (`id`)** | Números inteiros positivos (`number`) | `1`, `42` |
| **Coordenadas geográficas** | Objeto `{ latitude, longitude }` | `{ "latitude": -13.3702, "longitude": -39.0731 }` |
| **Horário do dia** | Minutos inteiros desde `00:00` (`0` a `1440`, onde `1440` = `24:00`) | `"19:30"` → `1170` |
| **Durações decorridas** | Minutos inteiros em campos terminados em `_min` | `travel_min: 12`, `service_min: 8` |
| **Distâncias** | Metros inteiros em campos terminados em `_m` | `distance_m: 3450` (`3.5 km`) |
| **Timestamps de evento** | String ISO-8601 com offset local | `"2026-11-20T19:45:00-03:00"` |

---

## 2. Regras de Negócio Acordadas no MVP

### 2.1. Tempo de Atendimento e Janelas de Entrega
* **Tempo fixo de parada (`service_min`):** Cada entrega consome **8 minutos** de atendimento no local.
* **Janela opcional:** Ao cadastrar uma entrega (formulário ou CSV), `time_window` pode ser enviado como `null`. Nesse caso, a entrega herda automaticamente o expediente operacional do dia (ex.: `08:00` às `22:00` → `{ "start": 480, "end": 1320 }`) e retorna com `has_explicit_time_window: false`.
* **Janela explícita:** Quando informada, `start` e `end` devem ser preenchidos em par, respeitando `0 <= start < end <= 1440` e comportando os 8 minutos mínimos de atendimento (`end - start >= 8`).

### 2.2. Capacidade dos Veículos e Demanda *(Pendência de alinhamento com o grupo)*
* **Proposta em discussão para o MVP:** Cada entrega envia `demand = 1` (**1 pedido = 1 unidade**) e o campo `capacity` do veículo representa o **número máximo de pedidos** que ele comporta na saída.
* **Ponto em aberto (issues #7 e #8):** O grupo ainda precisa confirmar se no MVP a capacidade será simplificada por contagem de pedidos (sem modelar peso em kg ou volume em m³) ou se será necessário informar peso/volume real por entrega e por veículo. O campo `demand` já existe como inteiro positivo no contrato para suportar ambas as abordagens sem quebrar a estrutura da API.

### 2.3. Múltiplos Veículos e Obrigatoriedade de Atendimento
* **Frota com 1 ou mais veículos:** O plano retornado (`RoutePlanDTO`) contém uma lista `routes` (`VehicleRouteDTO[]`), permitindo que o front-end exiba um seletor para alternar entre os veículos ativos e visualizar a sequência de paradas de cada um.
* **Sem solução parcial:** Todas as entregas válidas (geocodificadas com sucesso) do dia são **obrigatórias**. A API **não** retorna planos parciais com entregas deixadas para trás como `200 OK`. Caso não seja possível atender 100% das entregas dentro das restrições de janela e capacidade, a API responde com **HTTP 422**.

---

## 3. Endpoints

### 3.1. Listar entregas do dia
`GET /deliveries`

Retorna todas as entregas cadastradas para a operação do dia.

**Resposta `200 OK`:**
```json
[
  {
    "id": 10,
    "order_code": "#2001",
    "customer_name": "Maria Souza",
    "phone": "(71) 98888-1234",
    "address": "Rua das Flores, 10 - Centro",
    "location": {
      "latitude": -13.3712,
      "longitude": -39.0745
    },
    "geocoding_status": "ok",
    "geocoding_message": null,
    "demand": 1,
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
        "at": "2026-11-20T18:10:00-03:00",
        "text": "Pedido cadastrado"
      }
    ]
  },
  {
    "id": 11,
    "order_code": "#2002",
    "customer_name": "Carlos Lima",
    "phone": null,
    "address": "Rua Inexistente, 9999",
    "location": null,
    "geocoding_status": "failed",
    "geocoding_message": "Logradouro não encontrado na base de mapas.",
    "demand": 1,
    "time_window": {
      "start": 480,
      "end": 1320
    },
    "has_explicit_time_window": false,
    "priority": "high",
    "status": "issue",
    "notes": null,
    "issue_reason": "address_not_found",
    "completed_at": null,
    "history": [
      {
        "at": "2026-11-20T18:12:00-03:00",
        "text": "Falha na geocodificação do endereço"
      }
    ]
  }
]
```

---

### 3.2. Cadastrar nova entrega
`POST /deliveries`

Cria uma entrega, executa a geocodificação do endereço e aplica o expediente padrão caso `time_window` seja `null`.

**Corpo da requisição (`NewDeliveryDTO`):**
```json
{
  "order_code": "#2003",
  "customer_name": "Ana Paula",
  "phone": "(71) 97777-2222",
  "address": "Av. ACM, 250 - Centro",
  "demand": 1,
  "time_window": null,
  "priority": "normal",
  "notes": "Deixar na portaria"
}
```

**Resposta `201 Created`:** Retorna o objeto `DeliveryDTO` criado.  
**Resposta `422 Unprocessable Entity`:** Retorna `ApiErrorDTO` com `code: "validation_error"`.

---

### 3.3. Atualizar status / registrar ocorrência de entrega
`PATCH /deliveries/{id}`

Atualiza o estado operacional da entrega (`waiting_departure`, `in_progress`, `completed` ou `issue`).

**Corpo da requisição:**
```json
{
  "status": "issue",
  "issue_reason": "customer_absent",
  "notes": "Interfone sem resposta após 2 tentativas"
}
```

**Resposta `200 OK`:** Retorna o `DeliveryDTO` atualizado com o novo registro em `history`.

---

### 3.4. Editar cadastro da entrega
`PUT /deliveries/{id}`

Substitui os dados cadastrais da entrega. Diferente do `PATCH` (3.3), que muda apenas o estado operacional, aqui o corpo é o `NewDeliveryDTO` completo (mesmo formato do cadastro, 3.2). O backend refaz a geocodificação quando `address` muda e `time_window: null` volta a herdar o expediente do dia.

Edição permitida apenas enquanto a entrega está `waiting_departure`: depois que a rota é otimizada, alterar o cadastro não recalcula a sequência já atribuída aos veículos.

> **Mapeamento para o backend real:** `PUT /api/v1/entregas/{id}` (`EntregaUpdate`). O frontend bloqueia a edição quando `rota_id` está preenchido (a entrega já está atribuída a uma rota) e consulta `GET /api/v1/entregas/{id}` antes do PUT para validar o vínculo e comparar o endereço.
>
> **Dependência pendente (backend):** a mesma validação precisa existir na API — impedir alteração de `endereco`/`janela_*` via `PUT /entregas/{id}` quando `rota_id != null` — para cobrir chamadas diretas fora do app. Alinhar com o responsável pela API em tarefa/PR separado.

**Resposta `200 OK`:** Retorna o `DeliveryDTO` atualizado, com `"Pedido editado"` em `history`.
**Resposta `422 Unprocessable Entity`:** Retorna `ApiErrorDTO` com `code: "validation_error"` (mesmas regras do cadastro).

---

### 3.5. Remover entrega
`DELETE /deliveries/{id}`

> **Mapeamento para o backend real:** `DELETE /api/v1/entregas/{id}` faz soft delete (`status = CANCELADA`). Se a entrega está vinculada a uma rota, a `Parada` correspondente é removida do plano na mesma chamada — `rota_id` é preservado como histórico e a entrega não volta ao solver na próxima reotimização.
>
> **Cancelamento de entrega com falha (issue #32):** uma entrega `FALHA` também pode ser cancelada — ela vira `CANCELADA` com `status_anterior = "FALHA"`, e o motivo da ocorrência permanece em `observacoes`. Assim `status_anterior` distingue "cancelada antes de sair" (`PENDENTE`/`ATRIBUIDA`) de "cancelada após ocorrência" (`FALHA`), e toda mudança de status via `PUT` também grava o status anterior.

**Resposta `204 No Content`:** Entrega removida com sucesso (corpo vazio).
**Resposta `409 Conflict`:** A entrega está em andamento (`EM_ROTA`) ou concluída (`ENTREGUE`) — estados operacionais em curso fazem parte do histórico e não podem ser removidos.

---

### 3.6. Consultar plano de rota atual do dia
`GET /routes/today`

Retorna o plano de rota ativo do dia (`RoutePlanDTO`) ou `404 Not Found` caso nenhuma otimização tenha sido executada ainda.

---

### 3.7. Otimizar rotas do dia
`POST /routes/today/optimize`

Executa o motor OR-Tools considerando todos os veículos disponíveis, janelas de entrega, tempo de parada de 8 minutos e capacidade por contagem de pedidos.

**Resposta `200 OK` (`RoutePlanDTO` com múltiplos veículos):**
```json
{
  "id": 1,
  "status": "planned",
  "origin": {
    "name": "Loja Matriz",
    "address": "Praça da República, 1 - Centro",
    "location": {
      "latitude": -13.3702,
      "longitude": -39.0731
    }
  },
  "matrix_source": "road_network",
  "routes": [
    {
      "vehicle": {
        "id": 1,
        "name": "Moto 01",
        "capacity": 8
      },
      "load": 2,
      "distance_m": 4200,
      "travel_min": 11,
      "wait_min": 0,
      "service_min": 16,
      "total_min": 27,
      "stops": [
        {
          "delivery_id": 10,
          "arrival_minute_of_day": 1140,
          "departure_minute_of_day": 1148
        },
        {
          "delivery_id": 12,
          "arrival_minute_of_day": 1154,
          "departure_minute_of_day": 1162
        }
      ]
    },
    {
      "vehicle": {
        "id": 2,
        "name": "Carro 01",
        "capacity": 15
      },
      "load": 1,
      "distance_m": 3100,
      "travel_min": 9,
      "wait_min": 0,
      "service_min": 8,
      "total_min": 17,
      "stops": [
        {
          "delivery_id": 13,
          "arrival_minute_of_day": 1145,
          "departure_minute_of_day": 1153
        }
      ]
    }
  ]
}
```

> **Nota sobre `matrix_source`:**
> * `"road_network"`: distâncias e tempos calculados sobre a malha viária real.
> * `"manual"`: matriz informada manualmente para simulação/teste (o front-end sinaliza o plano como estimativa via `isSimulation = true`).

---

## 4. Tratamento de Erros (HTTP 422)

Toda falha de validação ou impossibilidade de roteirização retorna **HTTP 422 Unprocessable Entity** no formato `ApiErrorDTO`:

```json
{
  "error": {
    "code": "no_feasible_solution",
    "message": "Não foi possível atender todas as entregas dentro das janelas de horário e capacidade dos veículos disponíveis.",
    "details": []
  }
}
```

### Códigos padronizados (`error.code`)

| Código (`error.code`) | Quando ocorre | Ação esperada no front-end |
| :--- | :--- | :--- |
| `validation_error` | Campos inválidos no cadastro, janela menor que 8 min ou horário fora de `00:00–24:00`. | Exibir mensagens de erro nos campos indicados em `details`. |
| `no_feasible_solution` | O motor comprovou que é matematicamente impossível atender 100% das entregas com a frota e janelas atuais. | Alertar o operador para revisar janelas apertadas ou aumentar a capacidade/frota. |
| `solver_timeout` | O motor atingiu o tempo limite de busca sem encontrar uma solução viável dentro do prazo. | Alertar que o tempo de cálculo esgotou e sugerir nova tentativa ou simplificação das restrições. |