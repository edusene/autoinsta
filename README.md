# AutoInsta

Plataforma web de automação para Instagram: o usuário conecta a conta pelo fluxo oficial da Meta, monta workflows visuais (gatilho → condições → ações, com IA da OpenAI) e acompanha as execuções no painel.

Usa **somente APIs oficiais** (Instagram API with Instagram Login, Graph API v25.0). Não há scraping nem automação de navegador. A análise das APIs e as decisões de arquitetura estão em [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md).

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.12+ · Flask · psycopg 3 (SQL parametrizado) · pydantic |
| Banco / Auth | Supabase (PostgreSQL + Supabase Auth) |
| Fila | Tabela `jobs` no Postgres + `worker.py` (sem Redis) |
| Frontend | React · Vite · TypeScript · React Flow (`@xyflow/react`), servido pelo próprio Flask |
| Integrações | Meta Graph API (Instagram Login, webhooks) · OpenAI Responses API |

```
backend/      API Flask (routes → services → repositories), worker, testes
frontend/     painel React (pages, components, workflow/ = editor visual)
database/     migrations SQL
docs/         análise técnica e arquitetura
```

## O que o MVP faz

- Cadastro, login e logout (Supabase Auth). Cada usuário só acessa os próprios dados.
- **Conectar Instagram** com um clique (OAuth oficial). Reconectar, desconectar e uma tela de **diagnóstico** (configuração, token, permissões, webhook, eventos recebidos).
- Webhooks `messages`, `comments`, `messaging_postbacks` (cliques em botões) e outros: assinatura HMAC validada, deduplicação, resposta imediata e processamento em background.
- Editor visual com gatilhos (*Mensagem recebida*, *Comentário recebido*), condições (contém, igual, contém alguma palavra…) e ações (enviar DM, responder comentário em privado ou em público, esperar, IA, definir variável, finalizar).
- Variáveis: `{{message.text}}`, `{{comment.text}}`, `{{contact.username}}`, `{{contact.name}}`, `{{ai.response}}`, `{{vars.nome}}`.
- Ativar/desativar/duplicar/excluir workflows, com validação (gatilho único, campos obrigatórios, sem ciclos, regras da Meta).
- Logs de execução passo a passo, contatos com histórico, dashboard e configurações.
- **Caixa de entrada:** conversas por DM (inclusive as respondidas pelo app do Instagram), resposta manual dentro da janela de 24h e **pausa da automação** por contato (atendimento humano).
- **Contatos:** tags, notas, status e filtro por tag; nós *Adicionar/Remover tag* e condição *Contato tem a tag?*.
- **Disparos em massa:** mensagem (com até 3 botões de link) para um público por tags, na hora ou agendada, com relatório por destinatário. Quem está fora da janela de 24h é pulado.
- **CTR:** links trocados por links rastreados (`/r/<código>`, configure `PUBLIC_URL`) e cliques em botões; CTR no dashboard, na lista de workflows, em cada bloco do editor e em cada disparo.
- **Botões no workflow:** nó *Mensagem com botões* (template com até 3 botões ou até 13 respostas rápidas); cada botão de resposta vira um caminho no fluxo, mais o caminho *Sem clique*.
- **Follow-up:** nó *Aguardar resposta*, com os caminhos *Respondeu* (`{{reply.text}}`) e *Sem resposta* (prazo de até 23h) para enviar um lembrete.

### Limitações da API oficial (que o produto respeita)

- **Não é possível iniciar uma conversa.** DMs só podem ser enviadas até 24h depois da última mensagem do cliente. Por isso o delay e as esperas têm no máximo 23h, e os disparos em massa só chegam a quem escreveu nas últimas 24h.
- Para comentários, a alternativa oficial é a **resposta privada**: 1 por comentário, até 7 dias depois dele. O editor não deixa usar "Enviar DM" com o gatilho de comentário.
- Webhooks de comentários exigem **Advanced Access**, app em modo **Live** e conta **pública**.
- Só contas **profissionais** (Empresa/Criador). Mensagens de grupo não são suportadas.

---

## 1. Requisitos

- Python 3.12+ e Node.js 20+
- Um projeto no [Supabase](https://supabase.com)
- Um app na [Meta for Developers](https://developers.facebook.com/apps) (tipo **Business**)
- Uma chave da OpenAI (opcional; só os nós de IA dependem dela)
- Docker (opcional; usado para o Postgres dos testes e para o deploy)

## 2. Banco (Supabase)

1. Crie o projeto. Em **Connect**, copie a connection string. Em servidores sem IPv6, use o **Session pooler** (porta 5432).
2. Configure o `.env` da raiz (passo 4) e aplique as migrations:
   ```bash
   cd backend
   python migrate.py            # aplica database/migrations/*.sql
   python migrate.py --status
   ```
3. Em **Authentication → URL Configuration**, defina a *Site URL* (ex.: `http://localhost:5173`) e adicione `<frontend>/login` aos redirects permitidos (link de confirmação de e-mail).

Todas as tabelas ficam com **RLS habilitado e sem policies**. Isso bloqueia a Data API para a chave pública do frontend, e todo acesso a dados passa pelo backend (que é dono das tabelas). A chave `service_role` **não** é usada.

## 3. Meta Developer App (feito uma vez pelo administrador)

1. Crie um app do tipo **Business** e adicione o produto **Instagram**. Vá em **API setup with Instagram business login**.
2. Em **3. Set up Instagram business login → Business login settings**, copie o **ID do app do Instagram** e a **chave secreta do app do Instagram** para `META_APP_ID` e `META_APP_SECRET`.
   - `META_APP_SECRET` é **obrigatório para validar os webhooks**. Se o painel do Instagram não mostrar a chave secreta, use a **Chave secreta do app** em *Configurações do app → Básico*.
3. Em **Business login settings → OAuth redirect URIs**, cadastre exatamente o valor de `META_REDIRECT_URI`. Ele aponta para a rota do **frontend** `/instagram/callback`, por exemplo `https://app.seudominio.com/instagram/callback`.
4. Em **Configure webhooks**:
   - Callback URL: `https://api.seudominio.com/webhooks/meta`. Precisa ser HTTPS com certificado válido. Em desenvolvimento, use um túnel como `ngrok http 5000`.
   - Verify token: o valor de `META_VERIFY_TOKEN`.
   - Assine os campos `messages` e `comments`.
5. Cadastre as URLs de **Deauthorize callback** (`/webhooks/meta/deauthorize`) e **Data deletion request** (`/webhooks/meta/data-deletion`), ambas no host da API.
6. Enquanto o app está em **desenvolvimento**, só funcionam contas que tenham papel no app (adicione-as como *Instagram testers* e aceite o convite no Instagram). Para clientes reais, é preciso **App Review** das permissões `instagram_business_basic`, `instagram_business_manage_messages` e `instagram_business_manage_comments`, **Business Verification** e app em modo **Live**.
7. Na conta do Instagram, ative **Configurações → Mensagens → Ferramentas conectadas → Permitir acesso às mensagens**.

Ao conectar, a plataforma assina automaticamente os webhooks da conta (`POST /me/subscribed_apps`). Se a assinatura falhar, a página Instagram mostra o motivo e oferece o botão **Reativar webhooks**.

> **Assinatura do webhook:** a validação usa `META_APP_SECRET`. Se o painel do seu app assinar com outro segredo (por exemplo, o App Secret do app Meta em *Configurações → Básico*), adicione-o em `META_WEBHOOK_EXTRA_SECRETS`.

## 4. Configuração (um único `.env`)

Toda a configuração fica em **um arquivo `.env` na raiz** do projeto. Ele é ignorado pelo Git; o modelo versionado é o `.env.example`.

```bash
cp .env.example .env     # preencha os valores
```

O painel não tem variáveis próprias. A API e o painel ficam no mesmo endereço, e o painel busca a URL e a chave **pública** do Supabase em `GET /api/public-config` quando abre.

| Variável | Descrição |
|---|---|
| `SECRET_KEY` | Assina o `state` do OAuth. Use 32+ caracteres aleatórios. |
| `FRONTEND_URL` / `CORS_ORIGINS` | Endereço público do serviço (API e painel juntos). |
| `DATABASE_URL` | Postgres do Supabase (pooler). |
| `SUPABASE_URL` / `SUPABASE_ANON_KEY` | URL do projeto e chave **pública** (publishable/anon). Nunca a `service_role`. |
| `META_APP_ID` / `META_APP_SECRET` | "ID" e "Chave secreta" **do app do Instagram**. |
| `META_REDIRECT_URI` | `<endereço>/instagram/callback`, idêntica à do painel da Meta. |
| `META_VERIFY_TOKEN` | Token de verificação do webhook (você cola no painel da Meta). |
| `TOKEN_ENCRYPTION_KEY` | Chave Fernet dos tokens no banco. Não troque depois de conectar contas. |
| `OPENAI_API_KEY` / `OPENAI_DEFAULT_MODEL` | IA. A chave nunca vai para o navegador. |
| `EMBEDDED_WORKER` | `true` roda o worker dentro da API (Render free); `false` exige `python worker.py`. |

## 5. Execução local

```bash
# API (lê o .env da raiz)
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python migrate.py
python run.py          # http://localhost:5000
python worker.py       # outro terminal (ou EMBEDDED_WORKER=true)

# Painel com hot reload (proxy de /api para o Flask)
cd frontend && npm install && npm run dev      # http://localhost:5173
```

Para usar o mesmo endereço do deploy localmente, rode `npm run build` em `frontend/`: o Flask passa a servir o painel em http://localhost:5000.

## 6. Testes

Os testes usam um Postgres descartável. **O banco é recriado a cada execução.** Meta e OpenAI são sempre mockadas.

```bash
docker compose -f docker-compose.test.yml up -d --wait
cd backend && pytest
```

Cobrem autenticação/JWT, isolamento entre usuários, CRUD e validação de workflows, condições, variáveis, webhooks (assinatura, deduplicação, eco), o motor de ponta a ponta (ramos, IA, delays, falhas da Meta, token revogado), o OAuth (state, permissões, conta pessoal, conta já vinculada), os callbacks de exclusão de dados e o formato dos erros.

Frontend: `npm run build` (type-check + build).

## 7. Deploy

Uma única imagem Docker (`Dockerfile` na raiz) compila o painel e roda a API, que serve os dois. As migrations são aplicadas automaticamente a cada inicialização.

### Render (Web Service)

1. **New → Web Service**, conecte o repositório do GitHub.
2. **Language / Runtime: Docker**. Dockerfile Path: `./Dockerfile` (padrão). Root Directory: em branco.
3. **Region:** Virginia (mesma região do Supabase). **Instance type:** Free.
4. **Environment → Add from .env:** cole o conteúdo do seu `.env`. Ajuste `FRONTEND_URL`, `CORS_ORIGINS` e `META_REDIRECT_URI` para a URL que o Render gerar.
5. **Advanced → Health Check Path:** `/health`.

No plano free não há background worker: `EMBEDDED_WORKER=true` roda o worker dentro da API. O serviço hiberna após 15 min sem tráfego (cerca de 1 min para acordar); a Meta reenvia webhooks não confirmados.

**Keep-alive (evita a hibernação):** defina `KEEP_ALIVE_URL=https://<seu-serviço>.onrender.com/health`. Uma thread interna chama essa URL a cada 10 min (`KEEP_ALIVE_INTERVAL_SECONDS`), e o Render não hiberna o serviço. Isso é importante durante a revisão da Meta, que exige resposta em até 30 s. Um serviço ligado 24h consome cerca de 744 das 750 h grátis do workspace. Para reforçar contra reinícios inesperados, você pode cadastrar a mesma URL num monitor externo grátis (ex.: cron-job.org, a cada 10 min). **Para desligar** (por exemplo, numa VPS), deixe `KEEP_ALIVE_URL` vazia: nenhum código precisa mudar.

### VPS

```bash
cp .env.example .env      # ou copie o seu .env
docker compose up -d --build     # app (API + painel) na porta 5000 + worker separado
```

Coloque um proxy com HTTPS (Caddy ou Nginx) na frente da porta 5000; a Meta exige HTTPS. Mantenha a mesma `TOKEN_ENCRYPTION_KEY` ao migrar, e atualize as URLs no painel da Meta e no Supabase Auth.

## API (resumo)

Todas as respostas seguem `{"success": true, "data": ...}` ou `{"success": false, "error": {"code", "message"}}`.

```
GET  /api/auth/me
GET  /api/instagram/status | connect | diagnostics
POST /api/instagram/callback | disconnect | resubscribe
GET  /api/workflows            POST /api/workflows          GET /api/workflows/node-types
GET|PUT|DELETE /api/workflows/<id>
POST /api/workflows/<id>/activate | deactivate | duplicate | validate
POST /api/workflows/validate   (grafo não salvo)
GET  /api/workflows/<id>/executions   GET /api/logs   GET /api/executions/<id>
GET  /api/contacts   GET /api/contacts/<id>   GET /api/dashboard   GET|PUT /api/settings
GET|POST /webhooks/meta   POST /webhooks/meta/deauthorize   POST /webhooks/meta/data-deletion
GET  /health
```

## Como adicionar um novo tipo de nó

1. Em `backend/app/workflow/nodes.py`, registre a definição em `NODE_TYPES` (categoria, campos, saídas). O editor monta o formulário sozinho.
2. Implemente o executor e registre-o em `EXECUTORS`.
3. Adicione testes. Se o nó chamar a Meta, confirme antes na documentação oficial que o endpoint existe.

## Roadmap

- **Fase 2:** templates, mais gatilhos (postbacks, story mentions/replies), campos personalizados, histórico de conversas, analytics.
- **Fase 3:** WhatsApp/Messenger, equipes e permissões, planos e cobrança.
- **Fase 4:** marketplace de templates, agentes de IA especializados.
