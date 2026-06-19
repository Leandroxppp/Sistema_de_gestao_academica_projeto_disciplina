# Sistema de Gestao do Desempenho Estudantil

Backend REST em Python e frontend web (HTML/CSS/JS puro) para acompanhamento de desempenho academico, classificacao de risco, alertas e relatorios para professores e gestores.

O backend usa apenas a biblioteca padrao do Python e SQLite. O frontend usa apenas HTML, CSS e JavaScript nativo (ES Modules), sem build step e sem dependencias de terceiros. Nenhuma das duas partes exige instalacao de pacotes externos (`pip` ou `npm`).

## Funcionalidades

- Autenticacao de usuarios com perfil `professor` ou `gestor`, com expiracao de sessao e logout explicito.
- Cadastro de usuarios, alunos e materias.
- Vinculo de alunos a materias.
- Registro de desempenho academico com notas, frequencia e atividades entregues.
- Motor de analise de risco por regras.
- Dashboard com indicadores consolidados (geral e por aluno).
- Alertas para alunos em risco medio ou alto.
- Geracao e consulta de relatorios.
- Interface web (SPA) para login e navegacao por todas as funcionalidades acima.
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
- Um navegador atual (Chrome, Firefox, Edge) para a interface web. Nao requer Node.js/npm e nao requer `pip install` de nada.

## Tutorial: Como Rodar e Acessar a Interface Web

### Passo 1 — Abrir um terminal na pasta do projeto

```powershell
cd Sistema_de_gestao_academica_projeto_disciplina
```

### Passo 2 — Iniciar o servidor

```powershell
python .\run.py
```

Se aparecer `Servidor iniciado em http://127.0.0.1:8000`, esta funcionando. **Deixe este terminal aberto** — fechar ele desliga o servidor. (Na primeira vez, o arquivo `data/academico.db` e criado automaticamente, ja com os usuarios de demonstracao.)

### Passo 3 — Abrir no navegador

Acesse exatamente este endereco, **com o `/app/` no final**:

```text
http://127.0.0.1:8000/app/
```

> ⚠️ Atencao: acessar so `http://127.0.0.1:8000/` (sem `/app/`) mostra apenas o JSON de status da API, e nao a interface visual. O `/app/` e obrigatorio para ver a tela de login.

### Passo 4 — Fazer login

Use uma das contas de demonstracao:

| Perfil | Email | Senha |
|---|---|---|
| Professor | `professor@sigma.edu` | `professor123` |
| Gestor | `gestor@sigma.edu` | `gestor123` |

Na propria tela de login ha botoes de atalho ("professor" / "gestor") que preenchem essas credenciais automaticamente.

### Passo 5 — Navegar

Apos o login, use o menu lateral para acessar Dashboard, Alunos, Materias, Alertas, Relatorios e (somente para o perfil gestor) Usuarios.

## Fluxo Basico de Teste (via API, sem usar a interface web)

Util para testar o backend diretamente, sem abrir o navegador.

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

### 3. Registrar desempenho com atividades

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

## Endpoints

### Publicos

| Metodo | Rota | Descricao |
|---|---|---|
| GET | `/` | Informacoes iniciais da API |
| GET | `/health` | Verificacao de saude |
| GET | `/app/*` | Interface web (arquivos estaticos do frontend) |
| POST | `/auth/login` | Login |
| POST | `/auth/logout` | Encerra a sessao atual (invalida o token) |

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
| GET | `/dashboard` | Consulta indicadores gerais |
| GET | `/dashboard/aluno/{aluno_id}` | Consulta indicadores e historico de um aluno especifico |
| GET | `/alertas` | Lista alertas |
| GET | `/relatorios` | Lista relatorios |
| POST | `/relatorios` | Cria relatorio |

> Observacao: `POST /usuarios` agora exige o campo `senha` no corpo da requisicao (nao ha mais senha padrao implicita).

## Motor de Analise de Risco

O motor usa regras deterministicas baseadas em:

- media das notas;
- frequencia;
- quantidade de atividades entregues;
- quantidade de atividades esperadas.

Campos aceitos no registro de desempenho:

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

Regras principais:

- risco alto: media menor que 5, frequencia menor que 65%, entrega de menos de 50% das atividades ou `fator_risco >= 0.70`;
- risco medio: media menor que 7, frequencia menor que 80%, entrega abaixo de 75% das atividades ou `fator_risco >= 0.40`;
- risco baixo: indicadores dentro dos limites esperados.

## Seguranca

- **Senhas com hash salgado**: as senhas sao armazenadas com PBKDF2-HMAC-SHA256 (200.000 iteracoes) e salt aleatorio por usuario, no formato `salt$hash`. Hashes antigos (SHA256 sem salt, de bancos criados antes desta versao) continuam funcionando: no primeiro login com sucesso, o sistema migra automaticamente o hash do usuario para o novo formato salgado.
- **Sessao com expiracao**: o token retornado em `POST /auth/login` expira apos 8 horas (`expira_em_segundos` na resposta). Apos expirar, qualquer chamada autenticada retorna 401 e o frontend redireciona para a tela de login.
- **Logout explicito**: `POST /auth/logout` invalida o token imediatamente, sem esperar a expiracao.

## Frontend

Interface web de pagina unica (SPA) em `frontend/`, servida pelo proprio backend em `/app/`. Sem framework, sem bundler, sem `npm install` — apenas modulos ES nativos carregados direto pelo navegador.

```text
frontend/
├── index.html        # shell da pagina
├── styles.css         # design system (cores, cards, tabelas, badges de risco etc.)
└── js/
    ├── main.js         # bootstrap, autenticacao e registro de rotas
    ├── router.js       # roteador baseado em hash (#/rota/:param)
    ├── api.js           # cliente HTTP (fetch) para o backend
    ├── helpers.js       # utilitarios de DOM, formatacao e toasts/modais
    ├── charts.js         # graficos SVG (donut e sparkline), sem biblioteca externa
    ├── layout.js          # shell do app (sidebar, topbar) e estados de loading/erro
    └── views/              # uma view por tela: dashboard, alunos, aluno-detail,
                              materias, alertas, relatorios, usuarios, login
```

Principais telas:

- **Login** com preenchimento rapido das credenciais de demonstracao.
- **Dashboard** com indicadores gerais, grafico de distribuicao de risco e alertas ativos.
- **Alunos** com busca/filtro, detalhe por aluno (historico de desempenho, materias vinculadas, registro de novo desempenho).
- **Materias**, **Alertas** e **Relatorios**.
- **Usuarios**, visivel apenas para o perfil `gestor` (a navegacao e as rotas sao bloqueadas para `professor`, refletindo a mesma regra aplicada pelo backend).

## Testes

Execute:

```powershell
python -m unittest discover -s tests
```

## Estrutura

```text
.
├── app
│   ├── api.py
│   ├── database.py
│   ├── models.py
│   └── services.py
├── frontend
│   ├── index.html
│   ├── styles.css
│   └── js
│       ├── main.js
│       ├── router.js
│       ├── api.js
│       ├── helpers.js
│       ├── charts.js
│       ├── layout.js
│       └── views
├── tests
│   └── test_services.py
├── run.py
└── README.md
```
