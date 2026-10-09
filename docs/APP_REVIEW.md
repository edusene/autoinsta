# Revisão do app na Meta (Acesso Avançado)

Objetivo: permitir que **qualquer** conta profissional do Instagram conecte o AutoInsta e que DMs e comentários de **qualquer pessoa** disparem os workflows. Sem Acesso Avançado, só funcionam contas e pessoas com papel no app.

Pré-requisitos:
- [x] App publicado (Live)
- [x] Verificação da empresa concluída
- [x] Política de Privacidade (`/privacy`) e Termos (`/terms`) públicos
- [ ] Webhook entregando eventos (o vídeo precisa mostrar uma DM recebida e respondida)
- [ ] URL de exclusão de dados em *Configurações do app → Básico*
- [ ] E-mail de contato do app verificado
- [ ] Conta de teste para o revisor no AutoInsta (ver "Instruções para o revisor")

## Permissões a solicitar

No painel: **Revisão do app → Permissões e recursos**, em cada uma clique em **Solicitar acesso avançado**.

| Permissão | Por que precisamos |
|---|---|
| `instagram_business_basic` | Identificar a conta conectada (ID, @, foto) e renovar o token |
| `instagram_business_manage_messages` | Receber DMs (webhook `messages`) e responder automaticamente |
| `instagram_business_manage_comments` | Receber comentários (webhook `comments`), responder publicamente e enviar resposta privada |

Os textos abaixo estão em inglês, porque os revisores da Meta avaliam em inglês. Cole cada um no campo *"How will your app use this permission?"*.

### instagram_business_basic

> AutoInsta is a customer-service automation tool for Instagram professional accounts. Business owners connect their own Instagram professional account through Business Login for Instagram. We use instagram_business_basic to read the connected account's ID, username, name, account type and profile picture, so we can show which account is connected in the dashboard, route incoming webhook notifications to the right business, verify the account is a professional account, and refresh the long-lived access token. We do not access any data from accounts other than the one the business owner connected.

### instagram_business_manage_messages

> Businesses use AutoInsta to answer Instagram Direct messages automatically. When a customer sends a DM to the connected business account, we receive the "messages" webhook and run the automation workflow the business configured (for example: if the message contains "price", reply with the price list; otherwise generate a short answer with AI). The reply is sent with the Instagram Messaging API only to the person who messaged the business, within the 24-hour messaging window. Businesses can see every received message and every reply in the execution logs and can deactivate any automation at any time. We never send unsolicited messages or start conversations.

### instagram_business_manage_comments

> Businesses use AutoInsta to respond to comments on their own posts and reels. When someone comments on the connected account's media, we receive the "comments" webhook and, if the comment matches the business's rule (for example the keyword "I WANT"), we post a public reply to that comment and/or send one private reply to the commenter, as allowed by the Instagram Platform (one private reply per comment, within 7 days). We only act on comments on the connected business account's own media.

## Roteiro do vídeo (screencast)

Grave a tela em inglês, ou em português com legendas em inglês. De 2 a 4 minutos, sem cortes nas partes de login. Use **uma conta de cliente diferente** da conta da empresa para mandar a DM e o comentário.

1. **Login no AutoInsta**: abra `https://autoinsta-avbp.onrender.com/login` e entre.
2. **Conectar o Instagram** (`instagram_business_basic`):
   - Instagram → **Conectar Instagram** → tela oficial do Instagram;
   - mostrar as **permissões solicitadas** e clicar em **Permitir**;
   - voltar ao AutoInsta com a conta conectada (mostrar o @ e o Diagnóstico).
3. **Criar a automação de DM** (`instagram_business_manage_messages`):
   - Workflows → Novo → modelo **"Palavra-chave + IA"** → mostrar o editor → **Salvar e ativar**;
   - no celular ou em outra aba, da conta do cliente, mandar a DM *"How much does it cost?"*;
   - mostrar a **resposta chegando no Instagram** do cliente;
   - no AutoInsta, mostrar **Instagram → Eventos recebidos** e **Logs** com a execução.
4. **Automação de comentário** (`instagram_business_manage_comments`):
   - Novo workflow → modelo **"Comentou EU QUERO → DM"** → ativar;
   - da conta do cliente, comentar *"EU QUERO"* em um post da conta da empresa;
   - mostrar a **resposta pública** no comentário e a **DM privada** recebida pelo cliente;
   - mostrar o evento e o log no AutoInsta.
5. **Controle e desconexão**: desativar o workflow e mostrar **Desconectar** na página Instagram.

## Instruções para o revisor (campo "Instructions for reviewers")

Crie no AutoInsta um usuário só para a revisão (por exemplo `meta-review@seudominio.com`) com uma senha forte. Não use a sua conta pessoal. Depois preencha:

> Test URL: https://autoinsta-avbp.onrender.com/login
> Login: (e-mail de teste) / Password: (senha de teste)
> Steps: 1) Log in. 2) Go to "Instagram" and click "Conectar Instagram" (Connect Instagram), then authorize with your test Instagram professional account. 3) Go to "Workflows" > "Novo workflow" (New workflow), choose the template "Palavra-chave + IA" and click "Salvar e ativar" (Save and activate). 4) Send a Direct message to the connected account from another Instagram account; the automatic reply arrives within a few seconds. 5) Received events are listed under "Instagram" > "Eventos recebidos" and executions under "Logs".
> Note: the server runs on a free tier and may take up to 60 seconds to wake up on the first request.

## Depois da aprovação

- Os clientes conectam a própria conta pelo botão **Conectar Instagram**, sem precisar de papel no app.
- Para produção, considere um plano pago no Render (sem hibernação) e o worker separado (`EMBEDDED_WORKER=false` + `python worker.py`).
