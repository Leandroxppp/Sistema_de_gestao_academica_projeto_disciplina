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
- Geracao, consulta e download (export) de relatorios.
- Edicao e desativacao/reativacao (soft delete) de usuarios, alunos e materias, preservando o historico de notas, vinculos e relatorios.
- Sessao persistida em banco (sobrevive a reinicios do servidor), com revogacao imediata ao desativar um usuario.
- Protecao contra forca bruta no login (rate limit) e CORS restrito a origens confiaveis.
- Interface web (SPA) para login e navegacao por todas as funcionalidades acima, com modo claro/escuro e layout responsivo (sidebar em drawer no mobile).
- Migracoes de schema versionadas (tabela `schema_migrations`), aplicadas automaticamente e de forma idempotente ao iniciar o servidor.
- Trilha de auditoria: toda criacao/edicao/desativacao/reativacao relevante e registrada (quem, quando, o que), consultavel via `GET /auditoria` e pela tela "Auditoria" (somente gestor).
- Logging estruturado em arquivo com rotacao (`logs/app.log`) e console, cobrindo requisicoes HTTP e excecoes nao tratadas.
- Backup automatico do banco SQLite a cada 24h (mais um backup imediato ao iniciar), com retencao das 7 copias mais recentes; tambem pode ser disparado manualmente.
- Importacao de alunos em lote via CSV, com relatorio de linhas importadas e erros (sem interromper a importacao por causa de uma linha invalida).
- Notificacao por email (opcional, via SMTP) quando um aluno e classificado em risco alto.
- Paginacao e filtro (por termo e por nivel de risco) no backend para `/alunos`, refletidos na tela de Alunos.
- Plano de acao (intervencoes) por aluno: registro de acoes de acompanhamento (contato, reuniao, encaminhamento, outro), com status pendente/concluida, visivel e editavel por qualquer usuario autenticado.
- Troca de senha self-service: qualquer usuario autenticado (professor ou gestor) pode alterar a propria senha sem depender do gestor.
- Limiares de risco configuraveis: o gestor pode ajustar, em tempo de execucao, os valores que definem risco Alto/Medio (media, frequencia, deficit de atividades, fator de risco), sem alterar codigo.
- Comparativo entre turmas da mesma materia: quando duas turmas da mesma materia tem professores diferentes, o sistema compara os indicadores de risco agregados de cada turma e destaca qual delas esta com melhor/pior desempenho.
- Recalculo automatico (noturno) dos indicadores de risco de todos os alunos, alem do recalculo manual ja existente.
- Script de restauracao de backup (contraparte do backup automatico), com copia de seguranca do banco atual antes de sobrescrever.
- Testes automatizados com `unittest` e integracao continua via GitHub Actions.

## Perfis de Acesso

### Gestor

Pode:

- cadastrar, editar e desativar/reativar usuarios;
- cadastrar, editar e desativar/reativar alunos;
- cadastrar, editar e desativar/reativar materias;
- vincular alunos a materias;
- consultar dashboard, alunos, alertas e relatorios;
- registrar desempenho;
- recalcular analises de risco;
- configurar os limiares de risco (`/config/risco`);
- consultar o comparativo entre turmas da mesma materia (`/materias/comparativo`).

> O gestor nao pode desativar a propria conta nem desativar o ultimo gestor ativo do sistema — isso evitaria que o sistema ficasse sem ninguem com permissao administrativa.

### Professor

Pode:

- consultar dashboard, alunos, alertas e relatorios;
- registrar desempenho dos alunos, inclusive em lote pela tela "Minhas Turmas" (ve somente as materias atribuidas a ele e lanca notas/frequencia/atividades de toda a turma de uma vez, sem precisar abrir aluno por aluno);
- gerar relatorios.

Nao pode:

- cadastrar alunos;
- cadastrar materias (a materia/turma e cadastrada pelo gestor, que tambem atribui o professor responsavel — isso evita turmas duplicadas ou com nomes inconsistentes, o que quebraria o comparativo entre turmas);
- cadastrar usuarios;
- vincular alunos a materias;
- configurar limiares de risco ou consultar o comparativo entre turmas (ambos somente gestor).

### Ambos os perfis (professor e gestor)

Independente do perfil, qualquer usuario autenticado pode:

- registrar e atualizar intervencoes (plano de acao) de qualquer aluno;
- consultar os limiares de risco atuais (`GET /config/risco`);
- alterar a propria senha (`POST /auth/senha`).

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

> Quer ver o sistema com uma base de dados rica (varios alunos em cada nivel de risco, comparativo entre turmas, intervencoes, alertas etc.) em vez dos 2 usuarios e 3 alunos do seed minimo? Rode `python .\scripts\seed_demo.py` (veja [Base de Demonstracao](#base-de-demonstracao-dados-de-teste)) antes do Passo 2.

### Passo 5 — Navegar

Apos o login, use o menu lateral para acessar Dashboard, Alunos, Materias, Alertas, Relatorios e (somente para o perfil gestor) Usuarios e Auditoria. O perfil professor tambem ve um item extra, "Minhas Turmas", com as materias atribuidas a ele e o lancamento de notas em lote (veja [Minhas Turmas](#minhas-turmas-lancamento-de-notas-em-lote)). Em telas estreitas (celular/tablet), o menu lateral fica escondido atras do botao ☰ no topo. O botao 🌙/☀ no topo alterna entre tema claro e escuro (preferencia salva no navegador).

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
| GET | `/usuarios` | Lista usuarios (ativos e inativos) |
| POST | `/usuarios` | Cadastra usuario, somente gestor |
| PATCH | `/usuarios/{usuario_id}` | Edita usuario (campos parciais), somente gestor |
| DELETE | `/usuarios/{usuario_id}` | Desativa usuario (soft delete), somente gestor |
| GET | `/materias` | Lista materias (ativas e inativas) |
| POST | `/materias` | Cadastra materia, somente gestor |
| PATCH | `/materias/{materia_id}` | Edita materia (campos parciais), somente gestor |
| DELETE | `/materias/{materia_id}` | Desativa materia (soft delete), somente gestor |
| GET | `/alunos?page=&page_size=&termo=&risco=&materia_id=` | Lista alunos com paginacao e filtro opcional por termo (nome/matricula), nivel de risco e materia (roster de uma turma) |
| POST | `/alunos` | Cadastra aluno, somente gestor |
| POST | `/alunos/importar` | Importa alunos em lote via CSV (campo `csv` no corpo), somente gestor |
| GET | `/alunos/{aluno_id}` | Detalha aluno |
| PATCH | `/alunos/{aluno_id}` | Edita aluno (campos parciais), somente gestor |
| DELETE | `/alunos/{aluno_id}` | Desativa aluno (soft delete), somente gestor |
| POST | `/alunos/{aluno_id}/materias/{materia_id}` | Vincula aluno a materia, somente gestor |
| POST | `/alunos/{aluno_id}/desempenhos` | Registra desempenho |
| POST | `/analises/recalcular` | Recalcula riscos |
| GET | `/dashboard` | Consulta indicadores gerais |
| GET | `/dashboard/aluno/{aluno_id}` | Consulta indicadores e historico de um aluno especifico |
| GET | `/alertas` | Lista alertas |
| GET | `/relatorios` | Lista relatorios |
| POST | `/relatorios` | Cria relatorio |
| GET | `/auditoria?page=&page_size=` | Lista o historico de auditoria, paginado, somente gestor |
| GET | `/alunos/{aluno_id}/intervencoes` | Lista o plano de acao (intervencoes) do aluno |
| POST | `/alunos/{aluno_id}/intervencoes` | Registra uma nova intervencao (tipo, descricao, responsavel) |
| PATCH | `/intervencoes/{intervencao_id}` | Atualiza status (Pendente/Concluida), descricao ou responsavel de uma intervencao |
| GET | `/config/risco` | Consulta os limiares de risco atuais (efetivos, com padroes aplicados) |
| PATCH | `/config/risco` | Atualiza um ou mais limiares de risco, somente gestor |
| POST | `/auth/senha` | Altera a propria senha (exige senha atual) |
| GET | `/materias/comparativo` | Compara turmas da mesma materia com professores diferentes, somente gestor |

> Observacao: `POST /usuarios` agora exige o campo `senha` no corpo da requisicao (nao ha mais senha padrao implicita).

### Resposta paginada (`/alunos` e `/auditoria`)

Ambos os endpoints retornam o mesmo formato de envelope:

```json
{
  "itens": [ /* registros da pagina atual */ ],
  "total": 42,
  "pagina": 1,
  "tamanho_pagina": 10
}
```

### Importacao de alunos via CSV

`POST /alunos/importar` espera um corpo `{"csv": "nome,matricula,email\n..."}` (texto puro, com cabecalho contendo ao menos `nome` e `matricula`; `email` e opcional). Linhas com campo obrigatorio vazio ou matricula duplicada sao reportadas em `erros`, sem interromper a importacao das demais linhas:

```json
{
  "importados": 3,
  "total_linhas": 5,
  "erros": [
    { "linha": 4, "motivo": "nome e matricula sao obrigatorios." },
    { "linha": 5, "motivo": "matricula '2026001' ja cadastrada." }
  ]
}
```

### Minhas Turmas (lancamento de notas em lote)

Pensada para o perfil professor: em vez de procurar cada aluno na lista geral de Alunos, a tela "Minhas Turmas" filtra `GET /materias` no proprio navegador (`professor_id` igual ao usuario logado) e mostra so as materias atribuidas a ele. Ao abrir uma turma, busca o roster com `GET /alunos?materia_id={id}&page_size=100` e exibe uma tabela com um aluno por linha, cada um com seus proprios campos de notas/frequencia/atividades e um botao "Salvar" — que chama o mesmo `POST /alunos/{aluno_id}/desempenhos` usado pelo formulario individual do perfil do aluno. Nenhum endpoint novo de escrita foi criado: a unica novidade no backend e o filtro `materia_id` em `GET /alunos`. Como antes, o calculo de risco, os alertas e os relatorios sao gerados automaticamente a partir desses lancamentos.

A criacao da materia/turma em si continua sendo somente do gestor (`POST /materias`, ja existente) — o professor usa a turma depois de ela ser atribuida a ele.

### Auditoria

Toda criacao, edicao, desativacao, reativacao e vinculo de materia/desempenho relevante grava uma linha na tabela `auditoria` (quem fez — quando logado, "Sistema" quando nao ha ator —, quando, em qual entidade e um resumo legivel). `GET /auditoria` retorna esse historico paginado, mais recente primeiro, e e usado pela tela "Auditoria" da interface web (visivel apenas ao perfil `gestor`).

## Edicao e Exclusao Suave (Soft Delete)

`usuarios`, `alunos` e `materias` tem uma coluna `ativo`. Nenhum desses registros e excluido de fato do banco:

- `PATCH /usuarios/{id}`, `PATCH /alunos/{id}` e `PATCH /materias/{id}` aceitam um corpo com somente os campos que devem mudar (ex.: `{"nome": "Novo nome"}`). Nenhum campo e obrigatorio alem de ao menos um estar presente.
- `DELETE /usuarios/{id}`, `DELETE /alunos/{id}` e `DELETE /materias/{id}` marcam o registro como inativo (`ativo = 0`) em vez de apagar a linha — historico de notas, vinculos e relatorios permanece intacto.
- Para reativar, basta `PATCH` com `{"ativo": true}`.
- Listagens (`GET /usuarios`, `GET /alunos`, `GET /materias`) sempre retornam ativos e inativos, para que o gestor consiga localizar e reativar um registro.
- Acoes operacionais sao bloqueadas para registros inativos: nao e possivel fazer login com um usuario desativado, nem vincular materia ou registrar desempenho para aluno/materia inativos.
- Ao desativar um usuario, todas as sessoes dele sao revogadas imediatamente (o token deixa de funcionar mesmo antes de expirar).
- Por seguranca, um gestor nao pode desativar a propria conta nem desativar o ultimo gestor ativo restante.

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

Regras principais (valores padrao — veja [Limiares de Risco Configuraveis](#limiares-de-risco-configuraveis) para ajusta-los):

- risco alto: media menor que 5, frequencia menor que 65%, entrega de menos de 50% das atividades ou `fator_risco >= 0.70`;
- risco medio: media menor que 7, frequencia menor que 80%, entrega abaixo de 75% das atividades ou `fator_risco >= 0.40`;
- risco baixo: indicadores dentro dos limites esperados.

## Limiares de Risco Configuraveis

Os valores que definem o que conta como risco Alto/Medio nao sao mais constantes fixas no codigo — ficam guardados na tabela `configuracoes` (chave `risco_thresholds`, valor em JSON) e sao aplicados em toda nova analise (registro de desempenho, recalculo manual e recalculo automatico).

- `GET /config/risco` retorna os limiares efetivos atuais (qualquer usuario autenticado pode consultar) — quando nenhum valor foi configurado ainda, retorna os padroes de fabrica (os mesmos descritos acima).
- `PATCH /config/risco` atualiza um ou mais campos (somente gestor), por exemplo `{"alto_media": 4.5, "alto_frequencia": 60}`. Campos nao informados permanecem com o valor atual. Os campos `*_frequencia` sao validados entre 0 e 100, e os campos `*_fator` entre 0 e 1.
- Na interface web, a tela **Configuracoes** (somente gestor) expoe um formulario com os 8 campos (4 para risco Alto, 4 para risco Medio).

## Plano de Acao (Intervencoes)

Para cada aluno e possivel registrar um historico de acoes de acompanhamento tomadas pela equipe (contato com o responsavel, reuniao, encaminhamento a outro setor, etc.), com status `Pendente`/`Concluida`:

- `GET /alunos/{aluno_id}/intervencoes` e `POST /alunos/{aluno_id}/intervencoes` listam/criam intervencoes; o responsavel padrao e quem criou a intervencao, mas pode ser outro usuario.
- `PATCH /intervencoes/{intervencao_id}` atualiza status, descricao ou responsavel. Ao marcar como `Concluida`, a data de resolucao e registrada automaticamente.
- Qualquer usuario autenticado (professor ou gestor) pode criar e atualizar intervencoes — e um trabalho colaborativo de acompanhamento, nao restrito ao gestor.
- A tela de detalhe do aluno mostra um card "Plano de acao" com a lista de intervencoes e um formulario para registrar uma nova.

## Comparativo entre Turmas da Mesma Materia

Quando a mesma materia (mesmo nome) e ministrada em mais de uma turma por professores diferentes, pode acontecer de uma turma ter alunos com indicadores de risco bem melhores ou piores que a outra. `GET /materias/comparativo` (somente gestor) identifica esses casos automaticamente:

- Agrupa as materias ativas pelo nome (normalizado), considerando apenas grupos com pelo menos duas turmas e pelo menos dois professores distintos.
- Para cada turma do grupo, calcula a media geral de notas, a frequencia media e o fator de risco medio (usando os mesmos limiares configuraveis do motor de risco) a partir de todos os desempenhos registrados naquela turma.
- Quando ha dados suficientes nas duas turmas, marca a de melhor indicador como `destaque_materia_id` e a de pior indicador como `atencao_materia_id`.
- Na tela **Materias**, isso aparece como uma secao "Comparativo entre turmas da mesma materia", com um selo "🌟 Destaque" ou "⚠ Atencao" por turma.

No banco de dados de demonstracao (seed), todas as materias tem o mesmo professor, entao essa secao so aparece com dados reais depois que houver duas turmas da mesma materia com professores diferentes.

## Seguranca

- **Senhas com hash salgado**: as senhas sao armazenadas com PBKDF2-HMAC-SHA256 (200.000 iteracoes) e salt aleatorio por usuario, no formato `salt$hash`. Hashes antigos (SHA256 sem salt, de bancos criados antes desta versao) continuam funcionando: no primeiro login com sucesso, o sistema migra automaticamente o hash do usuario para o novo formato salgado.
- **Sessao persistida em SQLite**: tokens de sessao sao gravados na tabela `sessoes`, e nao apenas em memoria — reiniciar o servidor nao desloga os usuarios. O token retornado em `POST /auth/login` expira apos 8 horas (`expira_em_segundos` na resposta). Apos expirar, qualquer chamada autenticada retorna 401 e o frontend redireciona para a tela de login.
- **Revogacao imediata**: desativar um usuario (`DELETE /usuarios/{id}`) apaga todas as sessoes dele na hora, alem de bloquear logins futuros.
- **Logout explicito**: `POST /auth/logout` invalida o token imediatamente, sem esperar a expiracao.
- **Troca de senha self-service**: `POST /auth/senha` permite que qualquer usuario autenticado troque a propria senha, exigindo a senha atual correta (`401` se incorreta) e uma nova senha com pelo menos 6 caracteres. Na interface web, isso fica disponivel ao clicar no nome do usuario na barra superior ("Minha conta").
- **Rate limit no login**: ate 5 tentativas de login com falha por email em uma janela de 5 minutos; ao exceder, o backend responde `429` ate a janela abrir novamente. O estado fica em memoria (por processo), reiniciando junto com o servidor.
- **CORS restrito**: o backend so libera `Access-Control-Allow-Origin` para origens conhecidas (por padrao, o proprio host:porta do servidor, em `http://host:porta`, `http://127.0.0.1:porta` e `http://localhost:porta`). Para liberar outras origens (ex.: servir o frontend de outro dominio), defina a variavel de ambiente `SIGMA_ALLOWED_ORIGINS` com uma lista separada por virgulas, ou `*` para liberar qualquer origem:

  ```powershell
  $env:SIGMA_ALLOWED_ORIGINS = "http://192.168.0.10:8000,http://meusite.com"
  python .\run.py
  ```

## Migracoes de Schema

O banco usa uma tabela `schema_migrations` para controlar quais alteracoes de estrutura ja foram aplicadas. Cada migracao tem um numero de versao e e aplicada no maximo uma vez; `init_db()` roda essa verificacao toda vez que o servidor inicia, entao atualizar o codigo e reiniciar o servidor e suficiente para migrar bancos existentes — nao ha passo manual.

## Logging Estruturado

Cada requisicao HTTP (metodo, caminho, status, duracao) e qualquer excecao nao tratada sao registradas em `logs/app.log` (com rotacao automatica ao atingir ~2 MB, mantendo as 5 ultimas rotacoes) e tambem no console. Util para investigar erros em produção sem precisar reproduzir o problema interativamente.

## Backup Automatico do Banco

Ao iniciar, o servidor copia `data/academico.db` para `data/backups/` imediatamente e depois a cada 24 horas, mantendo apenas as 7 copias mais recentes. Tambem e possivel gerar um backup manualmente (por exemplo, via cron ou Tarefas Agendadas) com:

```powershell
python .\scripts\backup_db.py
```

### Restauracao de Backup

Para restaurar um backup (por exemplo, apos um erro de importacao ou corrupcao do banco), use `scripts/restore_db.py`. **Pare o servidor antes de restaurar.**

```powershell
python .\scripts\restore_db.py --listar              # lista os backups disponiveis
python .\scripts\restore_db.py --mais-recente         # restaura o backup mais recente (pede confirmacao)
python .\scripts\restore_db.py academico-20260619-030000.db   # restaura um backup especifico
```

Antes de sobrescrever, o script sempre copia o banco atual para `data/pre-restore-{timestamp}.db`, para que a restauracao possa ser desfeita caso seja um engano. Use `--sim` para pular a confirmacao interativa (uteis em scripts nao interativos).

### Base de Demonstracao (dados de teste)

Para explorar o sistema com uma base rica, sem precisar cadastrar nada manualmente, use `scripts/seed_demo.py`. Ele **apaga e recria `data/academico.db` do zero** e povoa um cenario completo (diferente do seed minimo criado automaticamente no primeiro `python .\run.py`), passando pelos mesmos serviços que a API usa — ou seja, auditoria, alertas e analises de risco saem todos preenchidos de forma realista, e não apenas como linhas cruas no banco.

**Pare o servidor antes de rodar:**

```powershell
python .\scripts\seed_demo.py            # pede confirmacao antes de apagar o banco atual
python .\scripts\seed_demo.py --sim      # pula a confirmacao
```

O cenario gerado inclui:

- **5 usuarios**: 2 professores ativos, 2 gestores ativos e 1 professor inativo (para testar a tela de reativacao). Veja a tabela completa de credenciais abaixo.
- **6 materias**, incluindo duas turmas de "Calculo I" com professores diferentes (para o [comparativo entre turmas](#comparativo-entre-turmas-da-mesma-materia)) e uma materia inativa.
- **12 alunos**, cobrindo risco Baixo, Medio e Alto, um aluno recem-matriculado sem nenhuma analise ainda, e um aluno inativo — o suficiente para exercitar a paginacao da tela de Alunos (que mostra 10 por pagina).
- **Multiplos desempenhos por aluno** (historico), o que dispara automaticamente alertas para os alunos em risco Alto.
- **Intervencoes** (plano de acao) em ambos os status, Pendente e Concluida.
- **2 relatorios** ja gerados.
- Um arquivo `data/exemplo_importacao.csv` para testar a [importacao de alunos via CSV](#importacao-de-alunos-via-csv) pela tela de Alunos — tem uma linha duplicada (mesma matricula de uma aluna ja cadastrada) e uma linha sem matricula, para ver o relatorio de erros por linha.

Credenciais criadas pelo `seed_demo.py`:

| Perfil | Email | Senha | Observacao |
|---|---|---|---|
| Professor | `professor@sigma.edu` | `professor123` | Ana — Calculo I, Programacao, Logica |
| Professor | `professor2@sigma.edu` | `professor123` | Camila — Calculo I (outra turma), Banco de Dados, Fisica I |
| Professor (inativo) | `professor.inativo@sigma.edu` | `professor123` | Eduardo — login deve falhar (conta desativada de proposito) |
| Gestor | `gestor@sigma.edu` | `gestor123` | Bruno |
| Gestor | `gestor2@sigma.edu` | `gestor123` | Diana |

## Recalculo Automatico de Risco

Alem do recalculo manual (`POST /analises/recalcular`), o servidor executa esse mesmo recalculo automaticamente: uma vez ao iniciar e depois a cada 24 horas, em uma thread de fundo. Isso garante que os indicadores de risco continuem corretos mesmo que os limiares de risco sejam alterados (ver [Limiares de Risco Configuraveis](#limiares-de-risco-configuraveis)) sem que cada aluno precise receber um novo registro de desempenho manualmente.

Para desativar (por exemplo, em testes ou ambientes onde o recalculo deve ser so manual):

```powershell
python .\run.py --sem-recalculo
```

## Notificacao por Email em Risco Alto

Quando um aluno e classificado como risco `Alto` apos um registro de desempenho, o sistema tenta enviar um email de alerta — mas **isso fica desativado por padrao**. Para habilitar, defina as variaveis de ambiente abaixo antes de iniciar o servidor:

| Variavel | Obrigatoria | Descricao |
|---|---|---|
| `SIGMA_SMTP_HOST` | sim | Servidor SMTP (ex.: `smtp.gmail.com`) |
| `SIGMA_ALERTA_EMAIL_TO` | sim | Destinatario(s) do alerta, separados por virgula |
| `SIGMA_SMTP_PORT` | nao | Porta (padrao `587`) |
| `SIGMA_SMTP_USER` | nao | Usuario para autenticacao SMTP |
| `SIGMA_SMTP_PASS` | nao | Senha para autenticacao SMTP |
| `SIGMA_SMTP_FROM` | nao | Remetente (padrao: `SIGMA_SMTP_USER` ou `sigma@localhost`) |

Sem `SIGMA_SMTP_HOST` e `SIGMA_ALERTA_EMAIL_TO` definidos, o envio e simplesmente ignorado (log em nivel debug) — o registro de desempenho continua funcionando normalmente.

## Frontend

Interface web de pagina unica (SPA) em `frontend/`, servida pelo proprio backend em `/app/`. Sem framework, sem bundler, sem `npm install` — apenas modulos ES nativos carregados direto pelo navegador.

```text
frontend/
├── index.html        # shell da pagina
├── styles.css         # design system (cores, cards, tabelas, badges de risco, tema escuro etc.)
└── js/
    ├── main.js         # bootstrap, autenticacao, tema inicial e registro de rotas
    ├── router.js       # roteador baseado em hash (#/rota/:param)
    ├── api.js           # cliente HTTP (fetch) para o backend
    ├── helpers.js       # utilitarios de DOM, formatacao, toasts (com "Desfazer") e modais acessiveis
    ├── theme.js          # modo claro/escuro, persistido em localStorage
    ├── charts.js         # graficos SVG (donut e sparkline), sem biblioteca externa
    ├── layout.js          # shell do app (sidebar/drawer, topbar), modal "Minha conta" e estados de loading/erro
    └── views/              # uma view por tela: dashboard, alunos, aluno-detail,
                              materias, alertas, relatorios, usuarios, auditoria, config, login
```

Principais telas:

- **Login** com preenchimento rapido das credenciais de demonstracao.
- **Dashboard** com indicadores gerais, grafico de distribuicao de risco e alertas ativos.
- **Alunos** com busca por nome/matricula e filtro por nivel de risco (ambos resolvidos no backend), paginacao server-side, importacao em lote via CSV (somente gestor, com modal de resultado listando erros por linha), e detalhe por aluno (historico de desempenho, materias vinculadas, registro de novo desempenho, edicao e desativacao/reativacao do cadastro, e o card "Plano de acao" com o historico de intervencoes e formulario para registrar novas).
- **Materias**, com edicao e desativacao/reativacao; o seletor de professor so lista professores ativos. Para o perfil `gestor`, exibe tambem a secao "Comparativo entre turmas da mesma materia".
- **Alertas**.
- **Relatorios**, com visualizacao do conteudo e download (export) como arquivo `.json`/`.txt`.
- **Usuarios**, visivel apenas para o perfil `gestor` (a navegacao e as rotas sao bloqueadas para `professor`, refletindo a mesma regra aplicada pelo backend), com edicao e desativacao/reativacao.
- **Auditoria**, visivel apenas para o perfil `gestor`: historico paginado de quem fez o que e quando.
- **Configuracoes**, visivel apenas para o perfil `gestor`: formulario para ajustar os limiares de risco Alto/Medio usados pelo motor de analise.
- **Minha conta**: clicar no nome do usuario (canto superior direito) abre um modal para trocar a propria senha, disponivel para qualquer perfil.

Registros inativos (usuario, aluno ou materia) aparecem nas listas com um selo "Inativo"/"Inativa" e ficam levemente esmaecidos; o botao de acao alterna para "Reativar". Desativar um usuario, aluno ou materia tambem mostra um toast com botao **"Desfazer"** (ate 6 segundos), que reativa o registro sem precisar abrir a tela novamente. Todo modal pode ser fechado com a tecla **Esc**, alem do clique fora ou do botao "Cancelar".

### Acessibilidade e responsividade

- Modais tem foco preso (Tab/Shift+Tab nao escapa do dialogo), foco inicial no primeiro campo e o foco volta para quem abriu o modal ao fechar; tambem expõem `role="dialog"`, `aria-modal` e `aria-labelledby`.
- O menu lateral e totalmente operavel por teclado (Tab + Enter/Espaço) e marca a pagina atual com `aria-current="page"`.
- Tabelas tem cabecalhos com `scope="col"`; linhas clicaveis (alunos, alertas) sao acessiveis via teclado.
- A area de notificacoes (toasts) usa `aria-live="polite"`, para leitores de tela anunciarem mensagens novas.
- Em telas estreitas, o menu lateral se torna um drawer deslizante (acionado pelo botao ☰), e tabelas longas ganham rolagem horizontal em vez de quebrar o layout.
- Modo claro/escuro com preferencia persistida (`localStorage`), alternavel pelo botao 🌙/☀ na barra superior.

## Testes

Execute:

```powershell
python -m unittest discover -s tests
```

### Integracao continua

Todo `push` e `pull request` roda os testes automaticamente via GitHub Actions (`.github/workflows/tests.yml`), em Python 3.10 a 3.13 — sem dependencias externas para instalar.

## Estrutura

```text
.
├── .github
│   └── workflows
│       └── tests.yml
├── app
│   ├── api.py
│   ├── backup.py
│   ├── database.py
│   ├── logging_config.py
│   ├── models.py
│   ├── notifications.py
│   ├── scheduler.py
│   └── services.py
├── frontend
│   ├── index.html
│   ├── styles.css
│   └── js
│       ├── main.js
│       ├── router.js
│       ├── api.js
│       ├── helpers.js
│       ├── theme.js
│       ├── charts.js
│       ├── layout.js
│       └── views
├── scripts
│   ├── backup_db.py
│   ├── restore_db.py
│   └── seed_demo.py
├── tests
│   └── test_services.py
├── .gitignore
├── run.py
└── README.md
```
