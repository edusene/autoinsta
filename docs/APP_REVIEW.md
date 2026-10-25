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
- [ ] URL de exclusão de dados em *Configurações do app → Básico*: `https://autoinsta-3wyp.onrender.com/webhooks/meta/data-deletion`
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
| A1 | Abrir `https://autoinsta-3wyp.onrender.com/login` e fazer login | *"The business owner logs in to AutoInsta."* |
| A2 | Menu **Instagram** → se estiver conectado, **Desconectar** | *"Starting from a disconnected state."* |
| A3 | Clicar em **Conectar Instagram** | *"The owner clicks 'Connect Instagram' to start Business Login for Instagram."* |
| A4 | Tela do Instagram: login e **lista de permissões** visível por 3 segundos | *"Instagram shows the permissions requested by AutoInsta."* |
| A5 | Clicar em **Permitir** | *"The owner grants the permissions."* |
| A6 | Volta ao AutoInsta: @sene.ia conectado | *"The account is connected. AutoInsta never shows the access token."* |

---

## 1) instagram_business_basic

### Descreva como seu aplicativo usa esta permissão

Atende às "Instructions for Developers" da Meta: credenciais do app, onde ver o perfil e permissão dependente. Troque `REVIEWER_EMAIL`/`REVIEWER_PASSWORD` pela conta de revisor criada no AutoInsta. **Não** informe credenciais do Instagram.

```
HOW WE USE IT
AutoInsta is a customer-service automation tool for Instagram professional accounts. A business owner connects their own Instagram professional account through Business Login for Instagram. We use instagram_business_basic to read the connected account's user ID, username, name, account type and profile picture in order to: (1) show the business owner which account is connected (username and profile picture); (2) confirm the account is a professional account (Business or Creator) before enabling automations; (3) match incoming webhook notifications to the correct business by the account's user ID; and (4) refresh the long-lived access token. We only access the account the owner explicitly connected. Data is stored encrypted, never sold or shared, and deleted when the owner disconnects or requests data deletion.

DEPENDENT PERMISSION
We are also requesting instagram_business_basic as a dependent permission for instagram_business_manage_messages and instagram_business_manage_comments, which are part of this same submission.

APP CREDENTIALS (AutoInsta account for the reviewer, not an Instagram account)
URL: https://autoinsta-3wyp.onrender.com/login
Email: REVIEWER_EMAIL
Password: REVIEWER_PASSWORD
Note: the server runs on a free tier and may take up to 60 seconds to load the first time. The interface is in Portuguese; English translations are given in parentheses.

HOW TO TEST
1) Log in with the credentials above.
2) In the left menu click "Instagram".
3) Click "Conectar Instagram" (Connect Instagram). You are redirected to the official Instagram authorization screen. Log in with your own test Instagram professional account and click "Allow".
4) You are redirected back to AutoInsta.

WHERE TO SEE THE PROFILE INFORMATION
- "Instagram" page (left menu): the card at the top shows the connected account's profile picture, @username, the "Conectado" (Connected) status and the connection date.
- Same page, "Diagnóstico da integração" (Integration diagnostics) section: shows "Conta profissional" (Professional account) with the account type returned by the API.
- "Configurações" (Settings) page, "Instagram" card: shows the connected @username.
To disconnect, click "Desconectar" (Disconnect) on the Instagram page; the access token is deleted immediately.
```

### Roteiro do vídeo (1–2 min)

A Meta exige: (1) mostrar a conta profissional se conectando; (2) mostrar dados do perfil (username, foto) da conta conectada.

| # | Ação na tela | Legenda (inglês) |
|---|---|---|
| 1 | Abrir `https://autoinsta-3wyp.onrender.com/login` e fazer login | *"The business owner logs in to AutoInsta."* |
| 2 | Menu **Instagram**: estado desconectado (desconecte antes de gravar) | *"No Instagram account is connected yet."* |
| 3 | Clicar em **Conectar Instagram** | *"The owner clicks 'Connect Instagram' (Business Login for Instagram)."* |
| 4 | Tela oficial do Instagram: login e **lista de permissões** visível por 3 s | *"Instagram shows the permissions requested by AutoInsta."* |
| 5 | Clicar em **Permitir** | *"The owner grants access."* |
| 6 | Volta ao AutoInsta: **foto de perfil, @username e "Conectado"** em destaque. Passe o mouse sobre eles | *"AutoInsta displays the connected account's profile picture and username (instagram_business_basic)."* |
| 7 | Rolar até **Diagnóstico**: "Conta profissional: BUSINESS" | *"The account type (Business) is read from the API to confirm it is a professional account."* |
| 8 | Abrir **Configurações** → card Instagram com o @ | *"The connected username is also shown in Settings."* |

---

## 2) instagram_business_manage_messages

### Descreva como seu aplicativo usa esta permissão

Troque `REVIEWER_EMAIL`/`REVIEWER_PASSWORD` pela conta de revisor do AutoInsta.

```
HOW WE USE IT
AutoInsta is a customer-service automation and lightweight CRM tool for Instagram professional accounts. We use instagram_business_manage_messages to (1) receive the Direct messages that customers send to the connected business account through the "messages" webhook, and (2) reply to those customers automatically through the Instagram Messaging API, according to rules the business owner configures in a visual workflow editor (for example: if the message contains "price", send the price list; otherwise generate a short, polite answer with AI).

Every incoming message is shown to the business owner in the "Eventos recebidos" (Received events) monitor, the sender is saved as a contact in our CRM ("Contatos" page, with interaction history), and every automated reply is recorded step by step in the execution logs ("Logs" page), so the owner always sees what was received and what was answered.

VALUE FOR THE USER
Small businesses and creators receive many repeated questions by Direct (prices, opening hours, links, availability) and often take hours to answer, losing sales. AutoInsta answers these customers within seconds, 24/7, with the business's own content, while keeping the full conversation history organized per customer for follow-up.

WHY IT IS NECESSARY
Without this permission the app cannot receive Direct messages nor send replies, so the core feature of the product (automatic replies to customer messages) would not work at all.

LIMITS WE RESPECT
We only reply to people who messaged the business first, inside the 24-hour standard messaging window. We never start conversations, never send unsolicited or promotional messages, and ignore echo events of our own replies to avoid loops. The owner can deactivate any automation or disconnect the account at any time. Message data is not sold or shared; text is sent to OpenAI only when the owner adds an AI step, and only the text configured in that step. instagram_business_basic is included in this submission as a dependent permission.

APP CREDENTIALS (AutoInsta account for the reviewer, not an Instagram account)
URL: https://autoinsta-3wyp.onrender.com/login
Email: REVIEWER_EMAIL
Password: REVIEWER_PASSWORD
The interface is in Portuguese; English translations are given in parentheses. The server may take up to 60 seconds to load the first time.

HOW TO TEST
1) Log in and click "Instagram" > "Conectar Instagram" (Connect Instagram); authorize your test Instagram professional account.
2) Click "Workflows" > "+ Novo workflow" (New workflow), select the template "Palavra-chave + IA" (Keyword + AI), click "Criar e abrir editor" (Create and open editor) and then "Salvar e ativar" (Save and activate).
3) From a different Instagram account, send a Direct message containing "preço" (price) to the connected account. An automatic reply arrives within a few seconds. Send another message without that word to receive the AI reply.
4) In AutoInsta, open "Instagram" and scroll to "Eventos recebidos" (Received events) to see the message with status "Processado" (Processed).
5) Open "Logs" and click the execution to see each step: trigger, condition, reply sent.
6) Open "Contatos" (Contacts) to see the customer saved with the interaction history.
```

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
| 14 | **Contatos** → clicar no cliente: histórico da interação | *"The customer is saved in the CRM with the conversation history."* |

---

## 3) instagram_business_manage_comments

### Descreva como seu aplicativo usa esta permissão

Pré-requisitos: um **post público** no @sene.ia com o workflow "Comentou EU QUERO → DM" **ativo** na conta do AutoInsta conectada a ele, e o servidor **sem hibernar** (a Meta exige resposta em até 30 s). Troque `POST_LINK` pelo link do post.

```
HOW WE USE IT
AutoInsta is a customer-service automation tool for Instagram professional accounts. We use instagram_business_manage_comments to receive comments made on the connected business account's own posts and reels (through the "comments" webhook) and to respond to them automatically, according to a rule the business owner configures in our visual workflow editor. In our main use case, when someone comments a keyword such as "EU QUERO" ("I WANT") on a post, AutoInsta (1) posts a public reply to that comment using the Comments API, and (2) sends one private reply to the commenter's Direct inbox using the Private Replies API, as allowed by the platform (one private reply per comment, within 7 days). Every comment received and every action taken is shown to the business owner in the "Eventos recebidos" (Received events) monitor and in the execution logs.

VALUE FOR THE USER
Businesses and creators run "comment to receive" campaigns ("comment I WANT to get the link / price / coupon"). Answering hundreds of comments by hand is slow and people give up waiting. AutoInsta answers every matching comment within seconds, publicly and in Direct, so the customer immediately gets what they asked for and the business converts more.

WHY IT IS NECESSARY
Without this permission the app cannot receive comments on the business's posts nor reply to them, so the comment automation feature would not work.

LIMITS WE RESPECT
We only act on comments on the connected account's own media, only when the comment matches the owner's rule, and ignore comments made by the business itself to avoid loops. We do not hide, delete or moderate other users' comments. instagram_business_basic is included in this submission as a dependent permission.

HOW TO TEST (no login needed for this test)
The automation is already active on this post of our test business account:
POST_LINK
1) Open the post above with any Instagram account.
2) Comment exactly: eu quero
   (the rule matches the words "eu quero", "quero" or "link", in any letter case)
3) Within a few seconds:
   - a public reply "Te enviei no direct! 📩" ("I sent it to your Direct!") appears under your comment (Comments API);
   - a private message with the requested link arrives in your Direct inbox (Private Replies API).
Comments that do not contain the keyword are ignored on purpose.

To see the business side, log in at https://autoinsta-3wyp.onrender.com/login with the reviewer credentials provided in the instagram_business_basic section, open "Instagram" > "Eventos recebidos" (Received events) and "Logs".
```

### Roteiro do vídeo (3–4 min) — refeito após a recusa de 25/10/2026

Motivo da recusa: *"o screencast não demonstra a experiência completa do caso de uso descrito"*. A Meta pediu, **no mesmo vídeo**: (1) o fluxo de login completo da Meta; (2) o usuário concedendo a permissão; (3) o caso de uso inteiro; (4) interface em inglês, legendas e explicação dos botões. Tudo que a descrição acima promete precisa aparecer na tela.

**Preparação (antes de gravar)**

- Grave numa **janela anônima** do Chrome. Assim o Instagram pede **usuário e senha** (o "fluxo de login completo"); com o Instagram já logado, essa tela é pulada e o vídeo fica incompleto.
- Instagram da empresa e do cliente em **inglês** (Configurações → Idioma → English). A tela de permissões e o app do cliente aparecem em inglês.
- Painel do AutoInsta em inglês: na janela anônima, clique com o botão direito → **Traduzir para inglês** (Chrome). Mantenha os nomes originais nas legendas entre parênteses.
- Apague workflows de comentário antigos e **desconecte** o Instagram no AutoInsta.
- Abra `https://autoinsta-3wyp.onrender.com/health` 1 minuto antes para acordar o servidor.
- Deixe pronto um **post público** do @sene.ia e a conta do cliente aberta no celular (espelhado na tela) ou em outra janela.
- Não digite a senha do Instagram na legenda nem dê zoom nela.

**Cenas** (sem cortes da cena 4 até a 17)

| # | Ação na tela | Legenda (inglês) |
|---|---|---|
| 1 | Título por 3 s | *"AutoInsta – instagram_business_manage_comments: automatic public reply and private reply to comments on the business's own posts."* |
| 2 | Abrir `https://autoinsta-3wyp.onrender.com/login` e entrar | *"The business owner logs in to AutoInsta (our app)."* |
| 3 | Menu **Instagram**: mostrar "não conectado" | *"No Instagram account is connected yet."* |
| 4 | Passar o mouse e clicar em **Conectar Instagram** | *"'Connect Instagram' starts Business Login for Instagram (Meta login)."* |
| 5 | Tela oficial do Instagram: digitar **usuário e senha** do @sene.ia e entrar (fazer 2FA se pedir) | *"The owner logs in with Instagram – full Meta login flow."* |
| 6 | Tela de permissões: deixar **3 s parado** e passar o mouse em **"Manage comments"** | *"Instagram lists the permissions requested, including managing comments."* |
| 7 | Clicar em **Allow** | *"The owner grants AutoInsta access to the permissions."* |
| 8 | Volta ao AutoInsta: foto, @sene.ia e **Conectado** | *"The business account is connected."* |
| 9 | **Workflows → + Novo workflow** → modelo **Comentou "EU QUERO" → DM** → **Criar e abrir editor** | *"The owner creates a comment automation from a template."* |
| 10 | Clicar no gatilho **Comentário recebido** e mostrar o painel lateral | *"Trigger: a new comment on one of the business's own posts (comments webhook)."* |
| 11 | Clicar na **Condição**: mostrar "eu quero, quero, link" | *"Condition: the comment contains the keyword 'eu quero' ('I want'). Other comments are ignored."* |
| 12 | Clicar em **Responder comentário publicamente** e em **Responder comentário por DM** (mostrar os textos) | *"Actions: reply publicly to the comment and send one private reply to the commenter."* |
| 13 | Passar o mouse e clicar em **Salvar e ativar** → status **Ativo** | *"'Save and activate' turns the automation on."* |
| 14 | Conta do **cliente**: abrir o post do @sene.ia e comentar **"hello"** | *"A customer comments without the keyword. AutoInsta ignores it on purpose."* |
| 15 | Mesma conta: comentar **"eu quero"** | *"The customer comments the keyword 'eu quero' ('I want')."* |
| 16 | Atualizar os comentários até aparecer a **resposta pública** do @sene.ia (zoom) | *"Within seconds AutoInsta posts a public reply to the comment (Comments API)."* |
| 17 | Abrir o **Direct** do cliente: mostrar a **mensagem privada** do @sene.ia | *"The customer receives one private reply in Direct (Private Replies API)."* |
| 18 | AutoInsta → **Instagram → Eventos recebidos**: os 2 comentários (tipo **Comentário**, status **Processado**) | *"Every comment received by the webhook is shown to the owner."* |
| 19 | **Logs** → abrir a execução do "eu quero": cada passo (gatilho, condição, DM e resposta pública) com sucesso | *"The execution log shows each step: condition matched, private reply sent, public reply sent."* |
| 20 | **Instagram → Desconectar** | *"The owner can disconnect at any time; the access token is deleted immediately."* |

A Meta exige que a resposta pública e a DM apareçam **em até 30 segundos** depois do comentário. Se demorar, regrave: não corte o vídeo entre a cena 15 e a 17.

**Notas para o revisor** (cole no campo de observações do envio)

```
The screencast shows, in one continuous recording: (1) the full Meta login flow (Business Login for Instagram, username and password entered); (2) the business owner granting the permissions, including instagram_business_manage_comments; (3) the complete use case: creating and activating the comment rule, a customer commenting a non-matching text (ignored) and the keyword "eu quero" ("I want"), the public reply under the comment, the private reply in the customer's Direct inbox, and the received comments and execution log in the AutoInsta dashboard.
Our dashboard is in Portuguese; it is shown translated to English by the browser, and every step has English captions. This is not a server-to-server app: it uses Business Login for Instagram on the front end.
```

---

## Perguntas personalizadas (se aparecerem)

As perguntas mudam por conta. Use estas respostas como base, sempre verdadeiras:

- **Is your app a Tech Provider / does it serve businesses you don't own?** → *Yes. AutoInsta is a SaaS platform: each business connects its own Instagram professional account and configures its own automations. We only act on behalf of the account that granted access.*
- **Who are your app users?** → *Small businesses and creators in Brazil that want to answer Instagram Direct messages and comments automatically.*
- **Where is the data stored / do you share it?** → *Stored in our own database (Supabase, PostgreSQL), access tokens encrypted at rest. We do not sell or share data. Message text is only sent to OpenAI when the business explicitly adds an AI step, and only the text configured in that step.*
- **How can users delete their data?** → *Disconnecting in the dashboard deletes the access token immediately; removing the app in Instagram settings triggers our deauthorize callback; data deletion requests are handled at /webhooks/meta/data-deletion and remove the account, contacts and history.*

## Instruções para o revisor (Complete App Verification)

Marque que o app usa login da Meta (**Yes**) e preencha:

> Website: https://autoinsta-3wyp.onrender.com/login
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
