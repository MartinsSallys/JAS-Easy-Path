# Validação da proposta com operações piloto (Issue #14)

Documento de validação da proposta do JAS Easy Path junto a operações piloto.
Define o instrumento de coleta em campo e registra uma **simulação executada
sobre o código real do sistema** como primeira leitura, antes do acompanhamento
presencial.

## 1. Objetivo e escopo

Validar se o problema e a proposta do JAS Easy Path fazem sentido para
operações piloto, conforme a issue #14:

- Acompanhar de 3 a 5 operações e registrar quantidade de paradas, tempo de
  planejamento e distância.
- Comparar uma rota sugerida com o método atual, sem prometer ganhos não
  medidos.
- Registrar problemas de geocodificação nos bairros testados e disposição a
  pagar.

Fora de escopo (Pós-MVP): rotação de veículos, horários de entrega avançados,
sistema de fidelidade e acompanhamento em tempo real.

## 2. Estado desta validação

| Entrega | Estado |
| --- | --- |
| Instrumento de coleta em campo (§6 e §8) | Pronto |
| Simulação de 5 operações piloto com o motor real (§4–§5) | Executada em 2026-11-27 |
| Problemas de geocodificação nos bairros testados (§7) | Registrados (dados reais do Nominatim) |
| Acompanhamento de 3–5 operações **reais** | Pendente — requer campo |
| Disposição a pagar | Pendente — requer entrevista com pilotos |

> **Leitura honesta:** os números de §5 vêm de endereços reais geocodificados
> de verdade e do solver real, mas as operações são simuladas — nenhum lojista
> foi acompanhado. Eles servem para exercitar o instrumento e antecipar
> problemas (a geocodificação, por exemplo, já se mostrou o ponto crítico).
> Os critérios de aceite de campo permanecem pendentes até a coleta real.

## 3. Metodologia da simulação

O script `scripts/validacao_piloto.py` reproduz o fluxo real do sistema:

1. **Geocodificação real** dos endereços via `NominatimGeocoder` (o mesmo do
   backend), em estágios: endereço completo → `rua + cidade` → centroide do
   bairro. É a degradação prevista em `arquitetura-mvp.md` §6.1.
2. **Matriz de custo** por Haversine com velocidade média de ~30 km/h — o
   mesmo fallback documentado do backend quando não há `ORS_API_KEY`.
3. **Otimização** com `route_engine.solve_routes` (OR-Tools), expediente fixo
   08:00–18:00 e 8 min de atendimento por parada, como no MVP.
4. **Método atual (baseline):** distância do percurso na ordem de registro
   dos pedidos — aproximação do que o lojista faz hoje (entrega na ordem em
   que os pedidos chegaram). Não mede o tempo que o lojista leva planejando;
   esse dado só existe em campo.

Cenários: 5 pequenos comércios típicos de Teresina-PI (distribuidora de água
e gás, drogaria, mercearia, material de construção e confeitaria atacado),
cobrindo 19 bairros. Resultados brutos em
`docs/validacao-piloto-resultados.json` (regenerável, ver §10).

## 4. Operações simuladas

| Operação | Veículo(s) | Entregas | Com janela |
| --- | --- | --- | --- |
| Distribuidora de água e gás | 1 caminhão + 1 moto | 14 | 0 |
| Drogaria | 1 moto | 10 | 2 |
| Mercearia de bairro | 1 carro | 8 | 1 |
| Loja de material de construção | 1 caminhão | 12 | 1 |
| Confeitaria atacado | 1 van | 14 | 2 |

## 5. Resultados medidos na simulação

| Operação | Paradas | Rota sugerida (km) | Ordem de registro (km) | Variação | Tempo previsto | Solver |
| --- | --- | --- | --- | --- | --- | --- |
| Distribuidora de água e gás | 14 | 56,6 | 89,5 | −36,8% | 3h52 | ~5 s |
| Drogaria | 10 | 15,5 | 31,4 | −50,8% | 6h23¹ | ~5 s |
| Mercearia de bairro | 8 | 49,9 | 56,8 | −12,2% | 2h50 | ~5 s |
| Material de construção | 12 | 42,8 | 63,5 | −32,6% | 4h58 | ~5 s |
| Confeitaria atacado | 14 | 32,6 | 55,0 | −40,7% | 3h05 | ~5 s |

¹ Inclui espera ociosa: a janela 14:00–18:00 do Jóquei combinada com outras
matinais gera ociosidade — o solver minimiza distância, não espera.

### Ressalvas obrigatórias (sem promessas não medidas)

- **Distâncias em linha reta.** O Haversine subestima o percurso real por
  ruas; a variação percentual é indicativa da ordem de grandeza, não do ganho
  real. Em operação real usa-se ORS/OSRM (`arquitetura-mvp.md` §4).
- **Coordenadas aproximadas.** 24 dos 63 endereços usaram centroide de bairro
  (§7): as rotas desses pontos são menos precisas — reforça que o instrumento
  mede comportamento, não precisão geográfica final.
- **Baseline é uma hipótese.** "Ordem de registro" é um proxy simples; o
  método real do lojista pode ser melhor ou pior. Em campo, o baseline será a
  sequência que o lojista realmente montou.
- **Tempo de planejamento do lojista não foi medido** — o ~5 s é só o solver.
  A coleta em campo registra quanto tempo o lojista leva hoje.

## 6. Instrumento de coleta em campo

Para cada operação acompanhada, preencher:

| Campo | Como coletar |
| --- | --- |
| Tipo de comércio e cidade/bairros atendidos | Entrevista |
| Nº de paradas no dia | Contagem das entregas |
| Tempo de planejamento atual (método manual) | Cronometrar o lojista montando a rota |
| Sequência montada pelo lojista + distância estimada | Registrar ordem; medir via mapa |
| Distância efetivamente percorrida | Odômetro/app do entregador ao fim do dia |
| Rota sugerida pela ferramenta (mesmas entregas) | Otimizar no JAS Easy Path e comparar |
| Paradas com janela e se foram cumpridas | Registro do entregador |
| Endereços que falharam na geocodificação | Log do §7 |
| Tempo de planejamento com a ferramenta | Cronometrar cadastro → rota pronta |

Regra da comparação: reportar o que foi **medido**, lado a lado, sem projetar
economia de combustível, tempo ou dinheiro que não tenha sido observado.

## 7. Problemas de geocodificação registrados

Medição real sobre 63 endereços (58 entregas + 5 depósitos) em 19 bairros de
Teresina-PI, via Nominatim em 2026-11-27:

| Situação | Qtde | % | O que significa |
| --- | --- | --- | --- |
| `ambigu` | 37 | 59% | Rua existe, mas há múltiplos candidatos/trechos sem número — o usuário precisaria confirmar o ponto |
| `centroide_bairro` | 24 | 38% | Rua não consta no OSM para Teresina; usado o centro do bairro como aproximação |
| `baixa_confianca` | 2 | 3% | Só o bairro foi informado/encontrado |
| `ok` (confiança alta, sem ambiguidade) | 0 | 0% | Nenhum endereço geocodificou limpo |

### Achados

1. **Cobertura do OSM em Teresina é fraca para ruas secundárias.** Avenidas
   principais geocodificam (com ambiguidade de trechos); ruas menores de
   bairros como Saci, Dirceu, Vermelha e Tancredo Neves frequentemente não
   existem na base. Em piloto real, boa parte dos pontos exigirá confirmação
   manual no mapa — fluxo já previsto no contrato (`latitude`/`longitude`
   manuais e retorno de candidatos para seleção, `api.md`/`arquitetura-mvp.md` §6).
2. **O token de bairro atrapalha a busca livre.** `Rua, Bairro, Teresina, PI`
   falha com mais frequência que `Rua, Teresina`: o parser do Nominatim
   confunde o bairro com outros elementos. Recomendação técnica: tentar a
   query sem bairro antes de desistir — o que o script já faz e o que pode virar
   melhoria no backend.
3. **O limiar de ambiguidade (0,9) marca quase tudo em Teresina.** A confiança
   máxima observada foi ~0,7 (rua + número raramente chegam). Calibrar o
   limiar por região ou exibir sempre os candidatos quando houver >1.
4. **Cidade pequena ≠ cidade grande.** O mesmo teste em São Paulo (coords dos
   testes) teria cobertura muito melhor; os bairros piloto precisam ser
   escolhidos sabendo disso — e o problema é *mais* relevante para o público
   do produto em capitais menores.

Bairros exercitados: Aeroporto, Buenos Aires, Centro, Cristo Rei, Dirceu,
Fátima, Gurupi, Horto, Itararé, Jóquei, Lourival Parente, Mafrense, Morada do
Sol, Piçarra, Saci, Santa Maria da Codipi, São Cristóvão, Tancredo Neves e
Vermelha.

### Limitações operacionais observadas

- **Expediente fixo 08:00–18:00** (limitação conhecida do MVP): perfis como
  pizzaria (noite) não são modeláveis hoje — os 5 cenários foram escolhidos
  dentro do expediente. Registrar em campo se algum piloto opera fora dele.
- O solver minimiza **distância**, não espera: janelas conflitantes podem
  gerar ociosidade prevista (ver Drogaria).

## 8. Disposição a pagar

Aplicar ao final de cada acompanhamento (registrar literal, não inferir):

| Pergunta | Resposta do piloto |
| --- | --- |
| O lojista reconhece o problema de planejar rota no braço? | _a preencher em campo_ |
| Usaria a ferramenta no dia seguinte, de graça? | _a preencher em campo_ |
| Pagaria por ela? Em que formato (mensalidade, por rota, por entrega)? | _a preencher em campo_ |
| Faixa de preço aceitável (espontânea e ancorada)? | _a preencher em campo_ |
| O que faria desistir da ferramenta? | _a preencher em campo_ |

**Hipótese a validar:** haverá disposição a pagar se o tempo de planejamento
e o retrabalho com endereços ruins forem percebidos como custos reais. O ponto
de fricção já identificado — geocodificação manual em cidades com OSM fraco —
pode ser o maior argumento contra o pagamento; medir isso em campo.

## 9. Cobertura dos critérios de aceite

| Critério (issue #14) | Estado | Evidência |
| --- | --- | --- |
| 3–5 operações acompanhadas | Parcial (simuladas) | 5 cenários simulados, §4–§5; falta campo real |
| Paradas, tempo de planejamento e distância por operação | Simulado | §5 (tempo de planejamento manual pendente de campo) |
| Rota sugerida vs. método atual, sem ganhos não medidos | Simulado | §5, com ressalvas explícitas |
| Problemas de geocodificação nos bairros testados | **Registrado** | §7 — dado real do Nominatim |
| Disposição a pagar identificada | Pendente | Instrumento em §8; requer entrevista |

## 10. Como reproduzir a simulação

Pré-requisitos: Python ≥ 3.14, `ortools`, `httpx`, `tenacity`,
`pydantic-settings` (deps do backend/route_engine instaladas).

```bash
# Git Bash / Linux / macOS — a partir da raiz do repositório
PYTHONPATH="backend:route_engine" python scripts/validacao_piloto.py

# PowerShell
$env:PYTHONPATH = "backend;route_engine"; python scripts/validacao_piloto.py
```

O script chama o Nominatim real (~110 requisições a 1 req/s, ~2 min) e grava
`docs/validacao-piloto-resultados.json`. Respeitar o rate limit do serviço.

## 11. Próximos passos

1. Selecionar 3–5 operações reais (preferir bairros com melhor cobertura OSM
   ou aceitar a confirmação manual de pontos como parte do teste).
2. Aplicar o instrumento de §6 e as perguntas de §8 em campo.
3. Substituir a tabela de §5 por dados medidos em campo e fechar os critérios.
4. Avaliar melhorias motivadas por §7: retry sem bairro, calibração do limiar
   de ambiguidade e UX de confirmação de ponto no mapa.

---

*Issue: #14 — Validar a proposta com operações piloto (Pós-MVP)*
*Simulação executada em: 2026-11-27*
