# Revisão do app na Meta (Acesso Avançado)

Objetivo: permitir que **qualquer** conta profissional do Instagram conecte o AutoInsta e que DMs e comentários de **qualquer pessoa** disparem os workflows.

## Onde enviar

**Instagram → API setup with Instagram login → "Complete app review"** (seta no canto superior direito) → *Continue to app review* → **Revisão do app → Solicitações → Editar**. Em cada permissão, clique na seta de *"Como esse app usará…"*.

## Peça SOMENTE estas 3 permissões

| Permissão | Pedir? | Motivo |
|---|---|---|
| `instagram_business_basic` | **Sim** | Identificar a conta conectada; obrigatória para as outras |
| `instagram_business_manage_messages` | **Sim** | Receber e responder DMs |
| `instagram_business_manage_comments` | **Sim** | Receber comentários, responder publicamente e em privado |
| `instagram_business_content_publish` | **Não** | O AutoInsta não publica posts |
| `instagram_business_manage_insights` | **Não** | O AutoInsta não lê métricas |
| Human Agent | **Não** | O AutoInsta não responde fora da janela de 24h |

Pedir permissão sem uso demonstrado no vídeo leva à recusa.

## Checklist antes de enviar

- [x] App publicado, empresa verificada, Política de Privacidade e Termos públicos
- [x] Webhook entregando DMs (testado em 09/10/2026)
- [x] Chamada bem-sucedida com `instagram_business_basic` e `instagram_business_manage_messages`
- [ ] Chamada bem-sucedida com `instagram_business_manage_comments`: ative o modelo "Comentou EU QUERO → DM" e comente "eu quero" em um post, de outra conta. A Meta leva até 2 dias para registrar.
- [ ] URL de exclusão de dados em *Configurações do app → Básico*: `https://autoinsta-avbp.onrender.com/webhooks/meta/data-deletion`
- [ ] Ícone do app 1024×1024 (sem logos da Meta ou do Instagram)
- [ ] E-mail de contato do app verificado
- [ ] Conta do AutoInsta só para o revisor (não use a sua pessoal)

## Regras dos vídeos (valem para os 3)

- **1080p**, só a janela do navegador, **sem áudio** (os revisores não escutam), cursor grande.
- **Legendas em inglês** em cada cena (a interface está em português). Use os textos "Legenda" dos roteiros.
- Cada vídeo precisa mostrar **o usuário concedendo a permissão** na tela oficial do Instagram. Por isso todos começam desconectando e reconectando a conta.
- Use **duas contas**: a da empresa (@sene.ia, conectada) e a de um "cliente" (outra conta, de preferência no celular ou em outra janela).
- Antes de gravar, abra o site e espere carregar (o servidor grátis "dorme" após 15 minutos).
- Duração: de 1 a 3 minutos cada. Sem cortes nas partes de autorização.

### Abertura comum (use no início dos 3 vídeos)

| # | Ação na tela | Legenda (inglês) |
|---|---|---|
| A1 | Abrir `https://autoinsta-avbp.onrender.com/login` e fazer login | *"The business owner logs in to AutoInsta."* |
| A2 | Menu **Instagram** → se estiver conectado, **Desconectar** | *"Starting from a disconnected state."* |
| A3 | Clicar em **Conectar Instagram** | *"The owner clicks 'Connect Instagram' to start Business Login for Instagram."* |
| A4 | Tela do Instagram: login e **lista de permissões** visível por 3 segundos | *"Instagram shows the permissions requested by AutoInsta."* |
| A5 | Clicar em **Permitir** | *"The owner grants the permissions."* |
| A6 | Volta ao AutoInsta: @sene.ia conectado | *"The account is connected. AutoInsta never shows the access token."* |

---

## 1) instagram_business_basic

### Descreva como seu aplicativo usa esta permissão

> AutoInsta is a customer-service automation tool for Instagram professional accounts. A business owner connects their own Instagram professional account through Business Login for Instagram. We use instagram_business_basic to read the connected account's user ID, username, name, account type and profile picture. We use this data to: (1) show the business owner which account is connected (username and profile picture on the Instagram page of the dashboard); (2) confirm that the account is a professional account (Business or Creator) before enabling automations; (3) match incoming webhook notifications to the correct business by the account's user ID; and (4) refresh the long-lived access token before it expires. We only access data of the account that the business owner explicitly connected. The data is stored encrypted, is never sold or shared, and is deleted when the owner disconnects the account or requests data deletion.

### Roteiro do vídeo (1–2 min)

| # | Ação na tela | Legenda (inglês) |
|---|---|---|
| 1–6 | **Abertura comum** (A1–A6) | — |
| 7 | Página **Instagram**: mostrar @, foto e "Conectado" | *"AutoInsta displays the connected account's username and profile picture (instagram_business_basic)."* |
| 8 | Rolar até **Diagnóstico**: "Conta conectada", "Token válido", "Conta profissional" | *"We verify the account is a professional (Business) account and the connection is valid."* |
| 9 | Ir em **Configurações** → card Instagram mostrando @ | *"The connected account is shown in Settings."* |
| 10 | Voltar em **Instagram** → **Desconectar** → confirmar | *"The owner can disconnect at any time; the access token is deleted immediately."* |

---

## 2) instagram_business_manage_messages

### Descreva como seu aplicativo usa esta permissão

> Businesses use AutoInsta to answer Instagram Direct messages automatically. After connecting their account, the business owner creates an automation workflow in a visual editor (for example: if the message contains "price", reply with the price list; otherwise generate a short reply with AI) and activates it. When a customer sends a Direct message to the business account, we receive the "messages" webhook, run the workflow and send the reply with the Instagram Messaging API only to the person who messaged the business, within the 24-hour standard messaging window. We never start conversations, never send unsolicited or promotional messages, and ignore echoes of our own messages to avoid loops. The business owner can see every received message and every reply in the "Received events" monitor and in the execution logs, and can deactivate any automation or disconnect the account at any time.

### Roteiro do vídeo (2–3 min)

| # | Ação na tela | Legenda (inglês) |
|---|---|---|
| 1–6 | **Abertura comum** (A1–A6) | — |
| 7 | **Workflows → Novo workflow** → escolher **"Palavra-chave + IA"** → Criar | *"The owner creates a Direct message automation from a template."* |
| 8 | No editor, clicar no bloco **Condição** e no **Enviar mensagem** (mostrar os textos) | *"If the message contains 'price', send the price reply. Otherwise, reply with AI."* |
| 9 | Clicar em **Salvar e ativar** → status **Ativo** | *"The automation is activated."* |
| 10 | Na conta do **cliente** (celular ou outra janela): enviar DM para @sene.ia: *"quanto custa?"* | *"A customer sends a Direct message to the business account."* |
| 11 | Mostrar a **resposta automática** chegando na conversa do cliente | *"AutoInsta replies automatically within seconds (instagram_business_manage_messages)."* |
| 12 | No AutoInsta: **Instagram → Eventos recebidos**: a DM com status **Processado** | *"The received message appears in the events monitor."* |
| 13 | **Logs** → abrir a execução: Gatilho → Condição → Mensagem enviada | *"The execution log shows each step and the reply sent."* |
| 14 | Voltar em **Workflows** → **Desativar** | *"The owner can deactivate the automation at any time."* |

---

## 3) instagram_business_manage_comments

### Descreva como seu aplicativo usa esta permissão

> Businesses use AutoInsta to respond to comments on their own posts and reels. The business owner creates a comment automation (for example: when someone comments the keyword "EU QUERO" / "I WANT", send them the requested link). When someone comments on the connected account's media, we receive the "comments" webhook, check the business's rule, and then (1) send one private reply to the commenter via the Instagram Messaging API, as allowed by the platform (one private reply per comment, within 7 days), and (2) post a short public reply to that comment. We only act on comments on the connected account's own media, ignore comments made by the business itself to avoid loops, and never hide, delete or moderate comments of other users. Every comment received and every action taken is visible to the business owner in the events monitor and execution logs.

### Roteiro do vídeo (2–3 min)

| # | Ação na tela | Legenda (inglês) |
|---|---|---|
| 1–6 | **Abertura comum** (A1–A6) | — |
| 7 | **Workflows → Novo workflow** → modelo **"Comentou EU QUERO → DM"** → Criar | *"The owner creates a comment automation from a template."* |
| 8 | No editor, mostrar **Condição** (eu quero, quero, link), **Responder por DM** e **Responder publicamente** | *"If a comment contains the keyword, send a private reply and a public reply."* |
| 9 | **Salvar e ativar** | *"The automation is activated."* |
| 10 | Conta do **cliente**: abrir um post de @sene.ia e comentar *"eu quero"* | *"A customer comments the keyword on the business's post."* |
| 11 | Mostrar a **resposta pública** aparecendo no comentário | *"AutoInsta posts a public reply to the comment (instagram_business_manage_comments)."* |
| 12 | Mostrar a **DM privada** que chegou ao cliente | *"The customer receives one private reply in Direct."* |
| 13 | No AutoInsta: **Eventos recebidos** (Comentário, Processado) e **Logs** da execução | *"The comment and both actions are recorded in the dashboard."* |
| 14 | **Desativar** o workflow | *"The owner can deactivate the automation at any time."* |

---

## Perguntas personalizadas (se aparecerem)

As perguntas mudam por conta. Use estas respostas como base, sempre verdadeiras:

- **Is your app a Tech Provider / does it serve businesses you don't own?** → *Yes. AutoInsta is a SaaS platform: each business connects its own Instagram professional account and configures its own automations. We only act on behalf of the account that granted access.*
- **Who are your app users?** → *Small businesses and creators in Brazil that want to answer Instagram Direct messages and comments automatically.*
- **Where is the data stored / do you share it?** → *Stored in our own database (Supabase, PostgreSQL), access tokens encrypted at rest. We do not sell or share data. Message text is only sent to OpenAI when the business explicitly adds an AI step, and only the text configured in that step.*
- **How can users delete their data?** → *Disconnecting in the dashboard deletes the access token immediately; removing the app in Instagram settings triggers our deauthorize callback; data deletion requests are handled at /webhooks/meta/data-deletion and remove the account, contacts and history.*

## Instruções para o revisor (Complete App Verification)

Marque que o app usa login da Meta (**Yes**) e preencha:

> Website: https://autoinsta-avbp.onrender.com/login
> Login: (e-mail da conta de revisor) / Password: (senha da conta de revisor)
> The interface is in Portuguese. Steps:
> 1) Log in. The server runs on a free tier and may take up to 60 seconds to load the first time.
> 2) In the left menu click "Instagram", then "Conectar Instagram" (Connect Instagram) and authorize your test Instagram professional account.
> 3) Click "Workflows" > "+ Novo workflow" (New workflow), choose the template "Palavra-chave + IA" (Keyword + AI) and click "Criar e abrir editor", then "Salvar e ativar" (Save and activate).
> 4) From another Instagram account, send a Direct message containing "preço" (price) to the connected account. The automatic reply arrives within a few seconds.
> 5) For comments: create a workflow from the template "Comentou EU QUERO → DM", activate it and comment "eu quero" on a post of the connected account. You will receive a public reply and a private reply.
> 6) Received events are listed under "Instagram" > "Eventos recebidos" (Received events), and each execution under "Logs".

## Depois da aprovação

- Qualquer conta profissional pode clicar em **Conectar Instagram**, sem precisar ter papel no app.
- Para produção, use um plano pago no Render (sem hibernação) e o worker separado (`EMBEDDED_WORKER=false` + `python worker.py`).
