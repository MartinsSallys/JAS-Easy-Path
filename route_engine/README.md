# Ambiente Python do motor

O motor ainda não usa dependências externas em tempo de execução. Pytest, Ruff e
Taskipy são ferramentas de desenvolvimento; OR-Tools será adicionado quando houver
código que o utilize.

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

O solver ainda não está implementado, e OR-Tools não está configurado nem instalado
no ambiente do motor. Quando o solver for desenvolvido, OR-Tools deverá ser declarado
como dependência de execução no `pyproject.toml`; depois será necessário atualizar o
lock com `poetry lock` e instalar a dependência com `poetry install`. Os testes atuais
de modelos e validação não dependem do OR-Tools.

Após alterar restrições de dependências no `pyproject.toml`, atualize o lock com
`poetry lock` e revise as mudanças antes de instalá-las.
