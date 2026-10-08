# AutoInsta — Análise técnica e arquitetura do MVP

Documentação Meta consultada em **2026-10-08** (Graph API **v25.0**). Sempre que a
documentação oficial mudar, ela prevalece sobre este documento.

## 1. API oficial escolhida

**Instagram API with Instagram Login** (host `graph.instagram.com`).

| Item | Situação oficial |
|---|---|
| Tipo de conta | Somente **profissional** (Business ou Creator). Página do Facebook **não** é necessária. |
| Instagram Basic Display API | Descontinuada — não usada. |
| Tipo de app Meta | App do tipo **Business**, produto "Instagram" → "API setup with Instagram business login". |
| OAuth | `https://www.instagram.com/oauth/authorize` → `POST https://api.instagram.com/oauth/access_token` |
| Token | Curto (1h) → longo (60 dias) via `GET graph.instagram.com/access_token?grant_type=ig_exchange_token` |
| Renovação | `GET graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token` (token com ≥ 24h e ainda válido) |
| Identidade | `GET /me?fields=user_id,username,name,account_type,profile_picture_url` — `user_id` = `entry.id` dos webhooks |

### Permissões solicitadas (mínimo necessário)

- `instagram_business_basic` — perfil e renovação de token
- `instagram_business_manage_messages` — receber/enviar DMs
- `instagram_business_manage_comments` — receber comentários, responder publicamente e em privado

**Não** solicitamos `instagram_business_content_publish` (não publicamos conteúdo).

### Webhooks

- `GET /webhooks/meta`: `hub.mode=subscribe`, `hub.verify_token`, `hub.challenge` (ecoar).
- `POST /webhooks/meta`: header `X-Hub-Signature-256: sha256=<HMAC-SHA256(body, app secret)>`.
- Campos usados: `messages` (array `entry[].messaging[]`) e `comments` (array `entry[].changes[]`).
- Assinatura da conta: `POST /me/subscribed_apps?subscribed_fields=messages,comments` (feito automaticamente ao conectar).
- A Meta reenvia por até 36h quando não recebe 200 → deduplicação obrigatória (`dedupe_key`).

### Ações oficialmente possíveis

| Ação | Endpoint | Regra oficial |
|---|---|---|
| Enviar DM | `POST /me/messages` `{recipient:{id}, message:{text}}` | Somente em até **24h** após mensagem do usuário. Texto ≤ **1000 bytes**. |
| Resposta privada a comentário | `POST /me/messages` `{recipient:{comment_id}, message:{text}}` | **1 por comentário**, até **7 dias** após o comentário. |
| Resposta pública a comentário | `POST /<COMMENT_ID>/replies?message=` | Não funciona em comentário oculto. |
| Perfil do contato | `GET /<IGSID>?fields=name,username,profile_pic,...` | Só depois que o usuário mandou mensagem (consentimento). |

### Limitações que afetam o MVP

1. **Não é possível iniciar conversa** com quem não mandou mensagem. "Enviar mensagem" só funciona em workflows de gatilho *mensagem recebida*. Para comentários, a alternativa oficial é a **resposta privada**.
2. **Janela de 24h**: delays longos podem fazer a mensagem falhar. O editor limita o delay a 23h.
3. Webhooks de comentários exigem **Advanced Access**, app em modo **Live** e conta **pública**.
4. Em modo de desenvolvimento, só contas com papel no app (testers) funcionam; para clientes reais é preciso **App Review** + **Business Verification**.
5. Mensagens de grupo não são suportadas.
6. Tags/anúncios não são acessíveis por esta API.

## 2. Arquitetura

```
React (Vite) ──HTTPS/JSON──▶ Flask API ──▶ Services ──▶ Repositories ──▶ Postgres (Supabase)
     │                          │                │
     └─ supabase-js (Auth)      │                ├─▶ Meta Graph API (MetaClient)
                                │                └─▶ OpenAI (OpenAIService)
Meta ──webhook──▶ /webhooks/meta ─▶ grava evento + job ─▶ worker.py ─▶ WorkflowEngine
```

- **Auth**: Supabase Auth no frontend (registro/login/sessão/refresh oficiais). O Flask valida o JWT (JWKS assimétrico ou segredo HS256 legado) e aplica ownership em toda query (`WHERE user_id = %s`).
- **Banco**: o backend acessa o Postgres diretamente (`DATABASE_URL`). O frontend **nunca** acessa tabelas: RLS habilitado em todas as tabelas sem policies, o que bloqueia a Data API para `anon`/`authenticated`. A chave `service_role` não é necessária.
- **Fila**: tabela `jobs` + `worker.py` (polling com `FOR UPDATE SKIP LOCKED`). Delays usam `run_at`. Sem Redis.
- **Workflow**: grafo (nós + arestas no formato do React Flow) salvo em `workflows.graph` (JSONB).
- **Tokens**: criptografados com Fernet (`TOKEN_ENCRYPTION_KEY`), nunca retornados pela API nem registrados em log.

## 3. Fluxo OAuth

1. Front chama `GET /api/instagram/connect` (autenticado) e recebe a URL de autorização com `state` assinado (user_id + nonce, validade de 10 min).
2. Usuário autoriza no Instagram, que redireciona para `META_REDIRECT_URI` = rota do **frontend** `/instagram/callback`.
3. O front envia `POST /api/instagram/callback {code, state}` com o JWT da sessão. O backend exige `state.uid == usuário logado`, o que impede que um link forjado conecte a conta de outra pessoa.
4. Backend: troca o code (remove `#_`), confere as permissões concedidas, troca pelo token longo, lê `/me`, verifica se a conta é profissional e não está vinculada a outro usuário, grava o token criptografado e assina os webhooks.

## 4. Fluxo de webhook

`POST /webhooks/meta` → valida assinatura → quebra em itens → `INSERT webhook_events ON CONFLICT (dedupe_key) DO NOTHING` + `INSERT jobs` → **200** em milissegundos.
Worker: `process_webhook_event` → localiza a conta (`entry.id`) → ignora eco/mensagens próprias → upsert do contato → workflows ativos com o mesmo `trigger_type` → `WorkflowEngine.start`.

## 5. Fluxo de execução

`start` cria `workflow_executions` (status `running`) e percorre o grafo a partir do gatilho. Cada nó grava em `workflow_execution_logs`.
Condição → handle `true`/`false`. Delay → salva contexto, status `waiting`, cria job `resume_execution` com `run_at` → o worker retoma depois.
Erros finalizam a execução com `status=error` e mensagem legível. Limite de 100 passos por execução.

## 6. Variáveis

`{{message.text}}`, `{{comment.text}}`, `{{contact.username}}`, `{{contact.name}}` (aliases `{{user.*}}`), `{{ai.response}}`, `{{vars.nome}}`.
A substituição é feita por regex com lookup de caminho em dicionários, sem `eval` nem template engine.
