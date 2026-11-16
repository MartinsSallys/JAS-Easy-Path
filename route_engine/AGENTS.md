# Contexto do Projeto — RotaCerta

## 1. Sobre o projeto

O RotaCerta é um sistema de otimização de rotas logísticas que busca auxiliar empresas na distribuição de entregas, considerando veículos disponíveis, capacidade de carga, localização dos destinos, distância e tempo de deslocamento.

O objetivo é desenvolver um sistema capaz de receber informações operacionais, processá-las e produzir rotas eficientes, respeitando as restrições de cada operação.

## 2. Minha responsabilidade

Estou trabalhando no desenvolvimento do motor de otimização de rotas (Route Engine).

Minha responsabilidade envolve:

- Modelagem dos dados de entrada.
- Validação de veículos, entregas e restrições.
- Preparação da matriz de custos.
- Integração com serviços de geocodificação e roteamento.
- Modelagem do problema matemático.
- Implementação do OR-Tools.
- Distribuição de entregas entre veículos.
- Otimização da sequência de paradas.
- Construção e organização dos resultados.
- Integração do motor com a API principal.

## 3. Tecnologias e conceitos

Tecnologias previstas:

- Python.
- Google OR-Tools.
- FastAPI, quando necessário para integração.
- Serviços externos de geocodificação e roteamento, como OSRM.
- Pytest para testes automatizados.

Conceitos fundamentais:

- VRP (Vehicle Routing Problem).
- CVRP (Capacitated Vehicle Routing Problem).
- Matriz de distâncias.
- Matriz de tempos.
- Geocodificação.
- Restrições de capacidade.
- Funções de custo.
- Heurísticas e metaheurísticas de otimização.

## 4. Fluxo esperado do motor

O fluxo conceitual do Route Engine é:

1. Receber os dados da operação.
2. Validar os dados de entrada.
3. Identificar depósito, veículos e entregas.
4. Obter ou validar as coordenadas geográficas.
5. Construir a matriz de distâncias e/ou tempos.
6. Preparar o problema para o OR-Tools.
7. Configurar veículos, demandas e restrições.
8. Executar o processo de otimização.
9. Extrair as rotas encontradas.
10. Calcular métricas e organizar o resultado.
11. Retornar uma resposta estruturada para o sistema.

O OR-Tools será responsável pela otimização matemática, não pela interpretação de endereços ou descoberta automática de caminhos pelas ruas.

## 5. Contrato inicial de entrada

Estamos desenvolvendo uma estrutura inicial com:

- Depósito: ID, endereço, latitude e longitude.
- Veículos: ID e capacidade.
- Entregas: ID, demanda, endereço, latitude e longitude.

Exemplo conceitual:

```python
problem = {
    "depot": {
        "id": 0,
        "location": {
            "address": "Endereço do depósito",
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
            "id": 1,
            "demand": 4,
            "location": {
                "address": "Endereço da entrega",
                "latitude": -2.910,
                "longitude": -41.780
            }
        }
    ]
}
```

Esse contrato ainda está em desenvolvimento e não deve ser tratado como definitivo.

## 6. Princípios de arquitetura

O motor deve ter responsabilidades separadas.

Estrutura planejada:

```text
route_engine/
├── main.py
├── domain/
│   ├── models.py
│   └── constraints.py
├── services/
│   ├── validator.py
│   ├── matrix_builder.py
│   └── result_builder.py
├── optimizer/
│   └── ortools_solver.py
└── tests/
    ├── test_validator.py
    ├── test_matrix.py
    └── test_optimizer.py
```

A estrutura pode evoluir conforme as necessidades reais do projeto.

Evitar misturar validação, integração externa, modelagem matemática e extração de resultados em um único módulo.

## 7. Regras de negócio importantes

- Cada veículo possui uma capacidade máxima.
- Cada entrega possui uma demanda.
- A capacidade dos veículos deve ser respeitada durante a otimização.
- Inicialmente, considerar entregas indivisíveis como hipótese de modelagem, sujeita à confirmação.
- Os veículos começam e terminam no depósito, conforme a configuração inicial.
- Endereços devem ser preservados junto às coordenadas para apresentação ao usuário.
- Distância e tempo são métricas diferentes.
- Uma solução deve respeitar todas as restrições obrigatórias.
- Quando não houver solução viável, o sistema deve informar o motivo sempre que possível.
- Recomendações de veículos adicionais ou alterações operacionais devem ser apresentadas ao usuário como sugestões, não executadas automaticamente.

## 8. Como o agente deve trabalhar comigo

Sou estudante de Análise e Desenvolvimento de Sistemas e estou desenvolvendo minhas habilidades em Python, backend e engenharia de dados.

Quero aprender a projetar e implementar o motor, não simplesmente receber código pronto.

Portanto:

1. Não implemente funcionalidades sem antes explicar o problema que elas resolvem.
2. Apresente a lógica antes do código.
3. Divida tarefas grandes em etapas pequenas.
4. Explique decisões arquiteturais e suas consequências.
5. Não presuma que requisitos ainda não definidos já foram aprovados.
6. Não invente funcionalidades ou regras de negócio.
7. Quando houver ambiguidades, faça uma pergunta objetiva.
8. Priorize documentação oficial e práticas consolidadas.
9. Revise meu código apontando problemas, melhorias e possíveis falhas.
10. Não reescreva todo o projeto quando uma correção pontual for suficiente.
11. Incentive a implementação independente antes de apresentar uma solução completa.
12. Utilize testes para validar as decisões e o comportamento do motor.

## 9. Estado atual do desenvolvimento

Estamos na etapa de definição do contrato de entrada do motor.

Já discutimos:

- Diferença entre dados de entrada e dados processados.
- Representação de depósito, veículos e entregas.
- Endereço associado a latitude e longitude.
- Importância da matriz de custos.
- Diferença entre capacidade, distância e tempo.
- Papel do OR-Tools na resolução do CVRP.
- Tratamento de operações sem solução viável.

Ainda não consideramos o motor implementado.

A próxima tarefa é concluir a modelagem do contrato de entrada, definir suas validações e começar a desenvolver um CVRP básico com matriz de distâncias manual, antes de integrar serviços externos.

**Diretriz principal:** ajude-me a construir uma solução de engenharia compreensível, testável e bem estruturada. Meu objetivo é dominar o funcionamento do motor e conseguir justificar tecnicamente as decisões de implementação.