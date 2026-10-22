# Segurança

## Como reportar uma vulnerabilidade

Não abra uma issue pública. Use **Security > Report a vulnerability** neste repositório
(relato privado do GitHub). Responderemos assim que possível.

## Segredos

Nenhum segredo fica no repositório. Toda a configuração sensível vem de variáveis de ambiente
(`.env` local, ignorado pelo git; variáveis do serviço em produção). Use `.env.example` como modelo.

- `SUPABASE_ANON_KEY` é a chave **pública** do Supabase; a `service_role` nunca é usada.
- Tokens do Instagram ficam criptografados no banco (Fernet, `TOKEN_ENCRYPTION_KEY`).
- Webhooks da Meta são aceitos apenas com assinatura `X-Hub-Signature-256` válida.
- Todas as tabelas têm RLS habilitado sem policies: o navegador não acessa dados direto,
  só pela API, que filtra tudo pelo usuário autenticado.

Se algum segredo for exposto, troque-o no provedor (Supabase, Meta, OpenAI) e atualize as
variáveis do serviço: apagar do histórico do git não basta.
