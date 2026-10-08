-- AutoInsta — schema inicial (PostgreSQL / Supabase)
--
-- Todo acesso aos dados passa pelo backend Flask (conexão direta ao Postgres).
-- RLS fica habilitado em todas as tabelas SEM policies: isso bloqueia a Data API
-- (PostgREST) para os papéis anon/authenticated, mesmo que a anon key vaze do frontend.
-- O dono das tabelas (papel usado pelo backend) não é afetado pelo RLS.
--
-- Pré-requisito: o schema "auth" com a tabela auth.users (existe no Supabase).

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- Utilitário: updated_at automático
-- ---------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

-- ---------------------------------------------------------------------------
-- Perfis (1:1 com auth.users). Criado sob demanda pelo backend no 1º acesso.
-- ---------------------------------------------------------------------------
create table public.profiles (
  id           uuid primary key references auth.users (id) on delete cascade,
  email        text,
  display_name text,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Contas Instagram conectadas
-- ig_user_id = "user_id" de GET /me = "entry.id" dos webhooks
-- ---------------------------------------------------------------------------
create table public.instagram_accounts (
  id                  uuid primary key default gen_random_uuid(),
  user_id             uuid not null references public.profiles (id) on delete cascade,
  ig_user_id          text not null unique,
  username            text,
  name                text,
  account_type        text,
  profile_picture_url text,
  status              text not null default 'connected'
                      check (status in ('connected', 'disconnected', 'token_expired', 'error')),
  permissions         text[] not null default '{}',
  webhook_subscribed  boolean not null default false,
  last_webhook_at     timestamptz,
  last_error          text,
  connected_at        timestamptz,
  disconnected_at     timestamptz,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);
create index instagram_accounts_user_id_idx on public.instagram_accounts (user_id);

-- Tokens separados da conta: nunca retornados pela API, sempre criptografados (Fernet).
create table public.oauth_tokens (
  id                    uuid primary key default gen_random_uuid(),
  instagram_account_id  uuid not null unique references public.instagram_accounts (id) on delete cascade,
  user_id               uuid not null references public.profiles (id) on delete cascade,
  access_token_encrypted text not null,
  expires_at            timestamptz,
  last_refreshed_at     timestamptz not null default now(),
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);
create index oauth_tokens_user_id_idx on public.oauth_tokens (user_id);
create index oauth_tokens_expires_at_idx on public.oauth_tokens (expires_at);

-- ---------------------------------------------------------------------------
-- Workflows. graph = { nodes: [...], edges: [...] } (formato do React Flow)
-- trigger_type é derivado do nó gatilho no momento do save (usado no roteamento).
-- ---------------------------------------------------------------------------
create table public.workflows (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null references public.profiles (id) on delete cascade,
  name             text not null check (char_length(name) between 1 and 120),
  description      text check (char_length(description) <= 1000),
  status           text not null default 'draft' check (status in ('draft', 'active', 'inactive')),
  trigger_type     text,
  graph            jsonb not null default '{"nodes": [], "edges": []}'::jsonb,
  settings         jsonb not null default '{}'::jsonb,
  last_executed_at timestamptz,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);
create index workflows_user_id_idx on public.workflows (user_id, updated_at desc);
create index workflows_active_trigger_idx on public.workflows (user_id, trigger_type) where status = 'active';

-- ---------------------------------------------------------------------------
-- Contatos (CRM mínimo)
-- ---------------------------------------------------------------------------
create table public.contacts (
  id                   uuid primary key default gen_random_uuid(),
  user_id              uuid not null references public.profiles (id) on delete cascade,
  instagram_account_id uuid not null references public.instagram_accounts (id) on delete cascade,
  ig_scoped_id         text not null,
  username             text,
  name                 text,
  status               text not null default 'active' check (status in ('active', 'blocked', 'archived')),
  metadata             jsonb not null default '{}'::jsonb,
  last_interaction_at  timestamptz,
  last_event_type      text,
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now(),
  unique (instagram_account_id, ig_scoped_id)
);
create index contacts_user_id_idx on public.contacts (user_id, last_interaction_at desc nulls last);

create table public.contact_events (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references public.profiles (id) on delete cascade,
  contact_id  uuid not null references public.contacts (id) on delete cascade,
  event_type  text not null,
  summary     text,
  data        jsonb not null default '{}'::jsonb,
  created_at  timestamptz not null default now()
);
create index contact_events_contact_id_idx on public.contact_events (contact_id, created_at desc);
create index contact_events_user_id_idx on public.contact_events (user_id);

-- ---------------------------------------------------------------------------
-- Eventos brutos recebidos da Meta (1 linha por item: mensagem ou comentário)
-- dedupe_key evita processar duas vezes os reenvios da Meta.
-- ---------------------------------------------------------------------------
create table public.webhook_events (
  id                   uuid primary key default gen_random_uuid(),
  dedupe_key           text not null unique,
  object               text not null,
  field                text not null,
  ig_account_id        text not null,
  instagram_account_id uuid references public.instagram_accounts (id) on delete set null,
  user_id              uuid references public.profiles (id) on delete cascade,
  payload              jsonb not null,
  status               text not null default 'received'
                       check (status in ('received', 'processed', 'ignored', 'error')),
  status_reason        text,
  received_at          timestamptz not null default now(),
  processed_at         timestamptz
);
create index webhook_events_received_at_idx on public.webhook_events (received_at desc);
create index webhook_events_instagram_account_id_idx on public.webhook_events (instagram_account_id);
create index webhook_events_user_id_idx on public.webhook_events (user_id);

-- ---------------------------------------------------------------------------
-- Execuções e logs
-- ---------------------------------------------------------------------------
create table public.workflow_executions (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null references public.profiles (id) on delete cascade,
  workflow_id      uuid not null references public.workflows (id) on delete cascade,
  contact_id       uuid references public.contacts (id) on delete set null,
  webhook_event_id uuid references public.webhook_events (id) on delete set null,
  trigger_type     text not null,
  trigger_event    jsonb not null default '{}'::jsonb,
  context          jsonb not null default '{}'::jsonb,
  status           text not null default 'running'
                   check (status in ('running', 'waiting', 'success', 'error', 'cancelled')),
  current_node_id  text,
  steps_count      integer not null default 0,
  error            text,
  started_at       timestamptz not null default now(),
  finished_at      timestamptz
);
create index workflow_executions_user_id_idx on public.workflow_executions (user_id, started_at desc);
create index workflow_executions_workflow_id_idx on public.workflow_executions (workflow_id, started_at desc);
create index workflow_executions_contact_id_idx on public.workflow_executions (contact_id);
create index workflow_executions_webhook_event_id_idx on public.workflow_executions (webhook_event_id);

create table public.workflow_execution_logs (
  id           bigint generated always as identity primary key,
  execution_id uuid not null references public.workflow_executions (id) on delete cascade,
  user_id      uuid not null references public.profiles (id) on delete cascade,
  node_id      text,
  node_type    text,
  level        text not null default 'info' check (level in ('info', 'warning', 'error')),
  message      text not null,
  data         jsonb not null default '{}'::jsonb,
  created_at   timestamptz not null default now()
);
create index workflow_execution_logs_execution_id_idx on public.workflow_execution_logs (execution_id, id);
create index workflow_execution_logs_user_id_idx on public.workflow_execution_logs (user_id);

-- ---------------------------------------------------------------------------
-- Configurações por usuário (IA etc.). A chave da OpenAI fica SOMENTE no servidor.
-- ---------------------------------------------------------------------------
create table public.user_settings (
  user_id          uuid primary key references public.profiles (id) on delete cascade,
  ai_default_model text,
  settings         jsonb not null default '{}'::jsonb,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Fila de jobs (worker.py). Delays = run_at no futuro.
-- ---------------------------------------------------------------------------
create table public.jobs (
  id           bigint generated always as identity primary key,
  type         text not null,
  payload      jsonb not null default '{}'::jsonb,
  status       text not null default 'queued' check (status in ('queued', 'running', 'done', 'failed')),
  run_at       timestamptz not null default now(),
  attempts     integer not null default 0,
  max_attempts integer not null default 3,
  last_error   text,
  locked_at    timestamptz,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);
create index jobs_ready_idx on public.jobs (run_at) where status = 'queued';
create index jobs_running_idx on public.jobs (locked_at) where status = 'running';

-- ---------------------------------------------------------------------------
-- Triggers de updated_at
-- ---------------------------------------------------------------------------
create trigger profiles_updated_at before update on public.profiles
  for each row execute function public.set_updated_at();
create trigger instagram_accounts_updated_at before update on public.instagram_accounts
  for each row execute function public.set_updated_at();
create trigger oauth_tokens_updated_at before update on public.oauth_tokens
  for each row execute function public.set_updated_at();
-- workflows.updated_at é definido pela aplicação (só muda em edição do usuário,
-- não quando o motor registra last_executed_at).
create trigger contacts_updated_at before update on public.contacts
  for each row execute function public.set_updated_at();
create trigger user_settings_updated_at before update on public.user_settings
  for each row execute function public.set_updated_at();
create trigger jobs_updated_at before update on public.jobs
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- RLS: habilitado sem policies => Data API bloqueada para anon/authenticated.
-- ---------------------------------------------------------------------------
alter table public.profiles                enable row level security;
alter table public.instagram_accounts      enable row level security;
alter table public.oauth_tokens            enable row level security;
alter table public.workflows               enable row level security;
alter table public.contacts                enable row level security;
alter table public.contact_events          enable row level security;
alter table public.webhook_events          enable row level security;
alter table public.workflow_executions     enable row level security;
alter table public.workflow_execution_logs enable row level security;
alter table public.user_settings           enable row level security;
alter table public.jobs                    enable row level security;
