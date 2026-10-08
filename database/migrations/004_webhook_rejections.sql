-- Tentativas de webhook recusadas (assinatura inválida/ausente), para diagnóstico.
-- Não guarda o corpo da requisição: só metadados. A aplicação mantém apenas as mais recentes.
create table public.webhook_rejections (
  id             bigint generated always as identity primary key,
  reason         text not null,
  ig_account_ids text[] not null default '{}',
  fields         text[] not null default '{}',
  has_signature  boolean not null,
  body_sha256    text not null,
  received_at    timestamptz not null default now()
);
create index webhook_rejections_received_at_idx on public.webhook_rejections (received_at desc);

alter table public.webhook_rejections enable row level security;

do $$
declare r text;
begin
  foreach r in array array['anon', 'authenticated'] loop
    if exists (select 1 from pg_roles where rolname = r) then
      execute format('revoke all on public.webhook_rejections from %I', r);
    end if;
  end loop;
end
$$;
