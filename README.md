# AutoInsta

Plataforma web de automação para Instagram: o usuário conecta a conta pelo fluxo oficial da Meta, monta workflows visuais (gatilho → condições → ações, com IA da OpenAI) e acompanha as execuções no painel.

Usa **somente APIs oficiais** (Instagram API with Instagram Login, Graph API v25.0). Não há scraping nem automação de navegador. A análise das APIs e as decisões de arquitetura estão em [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md).

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.12+ · Flask · psycopg 3 (SQL parametrizado) · pydantic |
| Banco / Auth | Supabase (PostgreSQL + Supabase Auth) |
| Fila | Tabela `jobs` no Postgres + `worker.py` (sem Redis) |
| Frontend | React · Vite · TypeScript · React Flow (`@xyflow/react`) |
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
- Webhooks `messages` e `comments`: assinatura HMAC validada, deduplicação, resposta imediata e processamento em background.
- Editor visual com gatilhos (*Mensagem recebida*, *Comentário recebido*), condições (contém, igual, contém alguma palavra…) e ações (enviar DM, responder comentário em privado ou em público, esperar, IA, definir variável, finalizar).
- Variáveis: `{{message.text}}`, `{{comment.text}}`, `{{contact.username}}`, `{{contact.name}}`, `{{ai.response}}`, `{{vars.nome}}`.
- Ativar/desativar/duplicar/excluir workflows, com validação (gatilho único, campos obrigatórios, sem ciclos, regras da Meta).
- Logs de execução passo a passo, contatos com histórico, dashboard e configurações.

### Limitações da API oficial (que o produto respeita)

- **Não é possível iniciar uma conversa.** DMs só podem ser enviadas até 24h depois da última mensagem do cliente. Por isso o delay máximo é de 23h.
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
2. Configure `backend/.env` (passo 4) e aplique as migrations:
   ```bash
   cd backend
   python migrate.py            # aplica database/migrations/*.sql
   python migrate.py --status
   ```
3. Em **Authentication → URL Configuration**, defina a *Site URL* (ex.: `http://localhost:5173`) e adicione `<frontend>/login` aos redirects permitidos (link de confirmação de e-mail).

Todas as tabelas ficam com **RLS habilitado e sem policies**. Isso bloqueia a Data API para a chave pública do frontend, e todo acesso a dados passa pelo backend (que é dono das tabelas). A chave `service_role` **não** é usada.

## 3. Meta Developer App (feito uma vez pelo administrador)

1. Crie um app do tipo **Business** e adicione o produto **Instagram**. Vá em **API setup with Instagram business login**.
2. Copie o **Instagram App ID** e o **Instagram App Secret** para `META_APP_ID` e `META_APP_SECRET`.
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

## 4. Configuração

```bash
cp backend/.env.example backend/.env       # preencha
cp frontend/.env.example frontend/.env     # VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY
```

| Variável | Onde | Descrição |
|---|---|---|
| `SECRET_KEY` | backend | Assina o `state` do OAuth. Use 32+ caracteres aleatórios. |
| `DATABASE_URL` | backend | Postgres do Supabase. |
| `SUPABASE_URL` | backend | Valida os JWTs (JWKS). |
| `SUPABASE_JWT_SECRET` | backend | Só para projetos com segredo HS256 legado. |
| `META_APP_ID` / `META_APP_SECRET` | backend | Credenciais do Instagram Login. |
| `META_REDIRECT_URI` | backend | URL do frontend `/instagram/callback` (idêntica à do painel). |
| `META_VERIFY_TOKEN` | backend | Token de verificação do webhook. |
| `TOKEN_ENCRYPTION_KEY` | backend | Chave Fernet para criptografar os tokens no banco. |
| `OPENAI_API_KEY` / `OPENAI_DEFAULT_MODEL` | backend | IA. A chave nunca vai para o frontend. |
| `FRONTEND_URL` / `CORS_ORIGINS` | backend | Origem do painel. |
| `VITE_API_URL` | frontend | URL da API. Vazio = mesma origem. |
| `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` | frontend | Chave **pública** do Supabase. |

Para gerar os segredos:
```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"                                   # SECRET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"     # TOKEN_ENCRYPTION_KEY
```

## 5. Execução local

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python migrate.py
python run.py          # API em http://localhost:5000
python worker.py       # em outro terminal: processa webhooks, delays e renovação de tokens

# Frontend
cd frontend
npm install
npm run dev            # http://localhost:5173 (proxy de /api para o Flask)
```

Para receber webhooks localmente, exponha a API com um túnel HTTPS (`ngrok http 5000`) e use essa URL no painel da Meta.

## 6. Testes

Os testes usam um Postgres descartável. **O banco é recriado a cada execução.** Meta e OpenAI são sempre mockadas.

```bash
docker compose -f docker-compose.test.yml up -d --wait
cd backend && pytest
```

Cobrem autenticação/JWT, isolamento entre usuários, CRUD e validação de workflows, condições, variáveis, webhooks (assinatura, deduplicação, eco), o motor de ponta a ponta (ramos, IA, delays, falhas da Meta, token revogado), o OAuth (state, permissões, conta pessoal, conta já vinculada), os callbacks de exclusão de dados e o formato dos erros.

Frontend: `npm run build` (type-check + build).

## 7. Deploy

### Render (ambiente de teste, plano free)

1. Suba o repositório para o GitHub e, no Render, use **New → Blueprint** (lê o `render.yaml`).
2. As variáveis podem ficar vazias na criação. Depois, em cada serviço, vá em **Environment → Add from .env** e cole:
   - `autoinsta-api`: o conteúdo de `backend/.env.render`
   - `autoinsta-web`: o conteúdo de `frontend/.env.render` (variáveis `VITE_*` entram no build, então faça um novo deploy depois de alterar)

   Esses arquivos são ignorados pelo Git (`.env.*`) e nunca devem ser versionados.
3. No plano free não existe background worker: `EMBEDDED_WORKER=true` roda o worker dentro da API. O serviço hiberna após 15 min sem tráfego (cerca de 1 min para acordar); a Meta reenvia webhooks não confirmados.
4. Supabase: use a connection string do **Session pooler** (o Render só tem IPv4).

### Linux / Docker

A API e o worker usam a mesma imagem:

```bash
docker compose up -d --build      # lê backend/.env; API na porta 5000
```

Ou sem Docker: `gunicorn -c gunicorn.conf.py wsgi:app` e `python worker.py` como serviços (systemd ou supervisor).

- **Frontend:** `cd frontend && npm run build` gera `dist/`, um site estático. Configure o fallback de SPA para `index.html`. Sirva pela mesma origem da API via reverse proxy (`/api` e `/webhooks` → Flask) ou defina `VITE_API_URL` no build.
- **HTTPS obrigatório** (a Meta exige). Termine TLS no proxy; o Flask usa `ProxyFix`.
- Em produção: `APP_ENV=production`, segredos no gerenciador de secrets do provedor (nunca no Git), `CORS_ORIGINS` só com o domínio do painel.
- Com várias instâncias da API, defina `RATELIMIT_STORAGE_URI` para um storage compartilhado.
- Rode `python migrate.py` a cada deploy que trouxer migrations novas.
- Escala: é possível rodar vários workers, porque os jobs são reservados com `FOR UPDATE SKIP LOCKED`.

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
