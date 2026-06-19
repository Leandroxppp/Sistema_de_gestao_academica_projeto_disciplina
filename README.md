# Sistema de Gestao do Desempenho Estudantil - Backend

Backend REST em Python para acompanhamento de desempenho academico, classificacao de risco, alertas e relatorios para professores e gestores.

O projeto usa apenas a biblioteca padrao do Python e SQLite, portanto nao exige instalacao de dependencias externas.

## Funcionalidades

O sistema oferece uma API para professores e gestores acompanharem o desempenho
academico dos alunos, identificarem risco de evasao e consultarem indicadores
consolidados.

### Autenticacao e perfis

- Login com email e senha.
- Controle de acesso por perfil:
  - `gestor`: pode cadastrar usuarios, alunos, materias e vincular alunos a materias.
  - `professor`: pode consultar dados academicos, registrar desempenho e gerar relatorios.
- Rotas protegidas por token de autenticacao.

### Gestao academica

- Cadastro e listagem de usuarios.
- Cadastro e listagem de alunos.
- Cadastro e listagem de materias.
- Vinculo de alunos a materias.
- Consulta detalhada de aluno por ID.
- Validacao para impedir materia com carga horaria negativa ou zerada.

### Desempenho dos alunos

- Registro de notas por aluno.
- Registro de frequencia.
- Registro opcional de atividades entregues e atividades esperadas.
- Associacao de desempenho a uma materia.
- Historico de desempenhos no banco SQLite.
- Validacao para impedir notas negativas, notas acima de 10 e frequencia fora de 0 a 100.

### Analise de risco

- Motor de analise deterministico baseado em regras.
- Classificacao do aluno em risco `Baixo`, `Medio` ou `Alto`.
- Calculo usando media das notas, frequencia, atividades entregues e fator de risco consolidado.
- Recalculo geral dos riscos academicos.

### Alertas, dashboard e relatorios

- Geracao de alertas para alunos em risco medio ou alto.
- Dashboard com indicadores gerais do sistema.
- Consulta de alertas ativos.
- Criacao e listagem de relatorios academicos.

### Banco e testes

- Banco SQLite criado automaticamente em `data/academico.db`.
- Dados iniciais de demonstracao na primeira execucao.
- Testes automatizados com `unittest`.

## Perfis de Acesso

### Gestor

Pode:

- cadastrar usuarios;
- cadastrar alunos;
- cadastrar materias;
- vincular alunos a materias;
- consultar dashboard, alunos, alertas e relatorios;
- registrar desempenho;
- recalcular analises de risco.

### Professor

Pode:

- consultar dashboard, alunos, alertas e relatorios;
- registrar desempenho dos alunos;
- gerar relatorios.

Nao pode:

- cadastrar alunos;
- cadastrar materias;
- cadastrar usuarios;
- vincular alunos a materias.

## Requisitos

- Python 3.10 ou superior.

## Como Executar

No terminal:

```powershell
python .\run.py --host 127.0.0.1 --port 8000
```

Depois acesse:

```text
http://127.0.0.1:8000/
```

O banco SQLite sera criado automaticamente em `data/academico.db` com dados de demonstracao.

Se aparecer o erro `sqlite3.DatabaseError: file is not a database`, apague o
arquivo `data/academico.db` e execute o projeto novamente:

```powershell
Remove-Item .\data\academico.db
python .\run.py --host 127.0.0.1 --port 8000
```

## Usuarios de Demonstracao

```text
professor@sigma.edu / professor123
gestor@sigma.edu / gestor123
```

## Como Testar Manualmente

### 1. Login como gestor

```powershell
$login = Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/auth/login" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"email":"gestor@sigma.edu","senha":"gestor123"}'

$headers = @{ Authorization = "Bearer $($login.token)" }
```

### 2. Consultar dashboard

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/dashboard" `
  -Headers $headers
```

### 3. Listar alunos

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/alunos" `
  -Headers $headers
```

### 4. Registrar desempenho com atividades opcionais

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/alunos/1/desempenhos" `
  -Method POST `
  -Headers $headers `
  -ContentType "application/json" `
  -Body '{"materia_id":1,"notas":[8.0,8.5,9.0],"frequencia":95,"atividades_entregues":1,"atividades_esperadas":4}'
```

Resposta esperada, em formato resumido:

```json
{
  "analise": {
    "nivel": "Alto",
    "fator_risco": 0.2125,
    "media_notas": 8.5,
    "frequencia": 95.0,
    "atividades_entregues": 1,
    "atividades_esperadas": 4
  }
}
```

Nesse exemplo, o aluno pode ser classificado como `Alto` mesmo com boa media e frequencia, porque entregou menos de 50% das atividades esperadas.

### 5. Consultar alertas

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/alertas" `
  -Headers $headers
```

## Endpoints

### Publicos

| Metodo | Rota | Descricao |
|---|---|---|
| GET | `/` | Informacoes iniciais da API |
| GET | `/health` | Verificacao de saude |
| POST | `/auth/login` | Login |

### Autenticados

| Metodo | Rota | Descricao |
|---|---|---|
| GET | `/usuarios` | Lista usuarios |
| POST | `/usuarios` | Cadastra usuario, somente gestor |
| GET | `/materias` | Lista materias |
| POST | `/materias` | Cadastra materia, somente gestor |
| GET | `/alunos` | Lista alunos |
| POST | `/alunos` | Cadastra aluno, somente gestor |
| GET | `/alunos/{aluno_id}` | Detalha aluno |
| POST | `/alunos/{aluno_id}/materias/{materia_id}` | Vincula aluno a materia, somente gestor |
| POST | `/alunos/{aluno_id}/desempenhos` | Registra desempenho |
| POST | `/analises/recalcular` | Recalcula riscos |
| GET | `/dashboard` | Consulta indicadores |
| GET | `/alertas` | Lista alertas |
| GET | `/relatorios` | Lista relatorios |
| POST | `/relatorios` | Cria relatorio |

## Motor de Analise de Risco

O motor usa regras deterministicas baseadas em:

- media das notas;
- frequencia;
- quantidade de atividades entregues;
- quantidade de atividades esperadas.

Campos aceitos no registro de desempenho:

Campos obrigatorios:

```json
{
  "materia_id": 1,
  "notas": [7.0, 8.0, 6.5],
  "frequencia": 82
}
```

Campos opcionais:

```json
{
  "materia_id": 1,
  "notas": [7.0, 8.0, 6.5],
  "frequencia": 82,
  "atividades_entregues": 2,
  "atividades_esperadas": 3,
  "data_referencia": "2026-06-04"
}
```

`atividades_entregues` e `atividades_esperadas` sao opcionais. Quando nao forem enviados, o risco e calculado apenas com notas e frequencia.

Quando forem enviados, os dois campos devem ser usados juntos:

- `atividades_esperadas` deve ser maior que zero;
- `atividades_entregues` nao pode ser negativa;
- `atividades_entregues` nao pode ser maior que `atividades_esperadas`;
- nao e permitido enviar `atividades_entregues` sem informar `atividades_esperadas`.

Regras principais:

- risco alto: media menor que 5, frequencia menor que 65%, entrega de menos de 50% das atividades ou `fator_risco >= 0.70`;
- risco medio: media menor que 7, frequencia menor que 80%, entrega abaixo de 75% das atividades ou `fator_risco >= 0.40`;
- risco baixo: indicadores dentro dos limites esperados.

## Testes Automatizados

Execute:

```powershell
python -m unittest discover -s tests
```

## Estrutura do Projeto

```text
.
|-- app
|   |-- api.py
|   |-- database.py
|   |-- models.py
|   `-- services.py
|-- data
|   `-- academico.db
|-- tests
|   `-- test_services.py
|-- run.py
`-- README.md
```
