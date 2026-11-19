# Ambiente Python do motor

O motor usa OR-Tools para resolver o CVRP com matriz de distâncias manual. Pytest,
Ruff e Taskipy são ferramentas de desenvolvimento.

## Preparar o ambiente

Use Python 3.14 e Poetry. Na raiz do repositório, crie o ambiente virtual dentro do
projeto e instale as versões fixadas no lock:

```bash
export POETRY_VIRTUALENVS_IN_PROJECT=true
poetry env use python3.14
poetry install --with dev
```

O ambiente local fica em `.venv/`, ignorado pelo Git. O Poetry não instala o motor
como pacote; instala apenas suas dependências.

## Comandos de desenvolvimento

Execute da raiz do repositório:

```bash
poetry run task lint          # Ruff no código Python do motor
poetry run task format        # aplica a formatação Ruff ao motor
poetry run task format-check  # verifica a formatação sem alterar arquivos
poetry run task test          # executa os testes descobertos em route_engine/tests
```

## Executar os testes Python

Depois de preparar o ambiente, rode os testes com:

```bash
poetry run pytest -q
```

O pytest descobre os arquivos `test_*.py` em `route_engine/tests/`. O atalho
`poetry run task test` executa o mesmo comando.

## Solver OR-Tools

O solver usa Google OR-Tools 9.15.6755, instalado como dependência de execução e
fixado em `poetry.lock`. Ele minimiza a distância total da matriz, atende todas as
entregas exatamente uma vez e aplica a capacidade individual de cada veículo. Todos
os veículos começam e terminam no depósito; um veículo sem entregas retorna ao mesmo
depósito sem percorrer distância. **O solver ainda não aplica expediente ou janelas
de entrega e não garante que as rotas calculadas sejam temporalmente viáveis.**

A busca usa `PATH_CHEAPEST_ARC` para criar uma solução inicial e `GUIDED_LOCAL_SEARCH`
para buscar melhorias, com limite padrão de 1 segundo (`time_limit_seconds` pode ser
configurado em `solve_routes`). O limite curto atende o exemplo pequeno; não garante
otimalidade global. O resultado separa inviabilidade comprovada de busca encerrada
sem solução: somente `ROUTING_INFEASIBLE` é tratado como inviabilidade comprovada;
`ROUTING_FAIL` e `ROUTING_FAIL_TIMEOUT` indicam busca encerrada sem solução. Sem uma
atribuição, rotas e distância total vêm como `None`.

O solver não tem dimensão temporal nem matriz de tempos. Ele não considera duração de
atendimento, espera por abertura de janela ou retorno ao depósito até o fim do
expediente. A validação dos horários verifica apenas a coerência local do contrato;
deslocamentos e a sequência das paradas ainda não são avaliados. O exemplo executável
envia um aviso para `stderr` antes de imprimir o JSON do resultado em `stdout`.

O motor ainda não geocodifica endereços nem calcula distâncias rodoviárias.

## Contrato de expediente e janelas

O payload exige `operating_hours` com `start` e `end`. Cada entrega pode informar
`time_window`; se a chave for omitida ou tiver valor `null`, a entrega herda o
expediente. Uma janela explícita deve conter os dois limites.

```json
{
  "operating_hours": {"start": "08:00", "end": "18:00"},
  "depot": {
    "id": 0,
    "location": {
      "address": "Depósito, Parnaíba - PI",
      "latitude": -2.905,
      "longitude": -41.776
    }
  },
  "vehicles": [
    {"id": 152, "capacity": 10},
    {"id": 153, "capacity": 15}
  ],
  "deliveries": [
    {
      "id": 101,
      "demand": 4,
      "location": {
        "address": "Rua das Flores, Parnaíba - PI",
        "latitude": -2.910,
        "longitude": -41.780
      },
      "time_window": {"start": "09:00", "end": "12:00"}
    },
    {
      "id": 102,
      "demand": 3,
      "location": {
        "address": "Av. São Sebastião, Parnaíba - PI",
        "latitude": -2.920,
        "longitude": -41.790
      }
    }
  ]
}
```

Os horários usam `HH:MM`, com zero à esquerda e sem segundos. São convertidos em
minutos desde o início do dia (`08:00` = 480). `24:00` é aceito somente como limite
final e representa 1440 minutos; não pode ser início. Intervalos iguais, invertidos
ou que atravessam a meia-noite são rejeitados.

A janela efetiva é a interseção com o expediente. Por exemplo, expediente
`08:00–18:00` e janela solicitada `17:00–20:00` resultam em `17:00–18:00`. Janelas
sem interseção ou com menos de 8 minutos efetivos são rejeitadas; exatamente 8
minutos é válido. Cada atendimento dura 8 minutos, valor interno e não configurável
no payload. Produtos são considerados disponíveis e conferidos no início da
operação. A validação não agenda o atendimento nem prova que uma rota consegue
respeitar os horários.

`Delivery.time_window` armazena somente a janela efetiva em minutos; a janela original
solicitada não é preservada nesse modelo. Um futuro cadastro que precise exibir ou
editar o valor original deverá armazená-lo separadamente.

### Migração de payloads existentes

Payloads sem expediente agora são rejeitados. Informe `operating_hours` em cada
problema existente; não há expediente padrão. Janelas por entrega continuam
opcionais, então omiti-las mantém o comportamento de herdar o expediente:

```json
{
  "operating_hours": {"start": "08:00", "end": "18:00"}
}
```

O contrato registra atendimento fixo e janelas, mas o solver ainda não aplica as
restrições temporais. A próxima integração precisará modelar duração de viagem,
atendimento de 8 minutos (sem atendimento no depósito), espera por abertura, início e
término do atendimento dentro da janela, retorno de todos os veículos antes do
fechamento e operação sem atravessar a meia-noite. Chegar antes da abertura permitirá
espera; os produtos são considerados disponíveis e conferidos no início do dia. Essas
regras aprovadas ainda não são verificadas pelas rotas atuais.

Após alterar restrições de dependências no `pyproject.toml`, atualize o lock com
`poetry lock` e revise as mudanças antes de instalá-las.

## Exemplo manual da matriz de distâncias

O cenário reutilizável está em `route_engine/examples/manual_distance_scenario.py`.
Ele fornece um `Problem` validado e uma matriz manual em metros. A ordem dos pontos
é `[depósito, *problem.deliveries]`: índice `0` representa o depósito e índice
`i + 1` representa `problem.deliveries[i]`, sem usar IDs como índices. As
coordenadas são sintéticas; os valores da matriz não foram calculados a partir delas.
O teste de referência confere rotas e métricas inseridas manualmente; ele não
executa nem representa uma saída do solver.

Para executar os testes do cenário e do validador de matriz:

```bash
poetry run pytest -q route_engine/tests/test_distance_matrix.py
```

Para executar o exemplo real com OR-Tools e imprimir o resultado estruturado:

```bash
poetry run python -m route_engine.examples.solve_manual_scenario
```

Os testes de integração do solver também podem ser executados isoladamente:

```bash
poetry run pytest -q route_engine/tests/test_ortools_solver.py
```
