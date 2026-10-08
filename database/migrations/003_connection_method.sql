-- Como a conta foi conectada:
--   oauth        = botão "Conectar Instagram" (login oficial do Instagram)
--   server_token = token gerado no painel da Meta e configurado no servidor (.env)
alter table public.instagram_accounts
  add column if not exists connection_method text not null default 'oauth'
  check (connection_method in ('oauth', 'server_token'));
