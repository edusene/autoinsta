-- Caixa de entrada, contatos (tags/notas/pausa), disparos em massa, CTR e follow-up.

-- ---------------------------------------------------------------------------
-- Contatos: segmentação, atendimento humano e janela de 24h da Meta
-- ---------------------------------------------------------------------------
alter table public.contacts
  add column if not exists tags                 text[] not null default '{}',
  add column if not exists notes                text check (char_length(notes) <= 4000),
  add column if not exists automation_paused    boolean not null default false,
  add column if not exists last_inbound_at      timestamptz,  -- última DM do contato (abre a janela de 24h)
  add column if not exists last_message_at      timestamptz,  -- última mensagem da conversa (qualquer direção)
  add column if not exists last_message_preview text,
  add column if not exists unread_count         integer not null default 0;

create index if not exists contacts_tags_idx on public.contacts using gin (tags);
create index if not exists contacts_inbox_idx on public.contacts (user_id, last_message_at desc nulls last);

update public.contacts c
   set last_inbound_at = e.last_at
  from (select contact_id, max(created_at) as last_at from public.contact_events
         where event_type = 'messages' group by contact_id) e
 where e.contact_id = c.id and c.last_inbound_at is null;

-- ---------------------------------------------------------------------------
-- Disparos em massa (somente para quem está dentro da janela de 24h)
-- ---------------------------------------------------------------------------
create table public.broadcasts (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references public.profiles (id) on delete cascade,
  name          text not null check (char_length(name) between 1 and 120),
  text          text not null default '' check (char_length(text) <= 1000),
  buttons       jsonb not null default '[]'::jsonb,   -- [{id, title, type: "url", url}]
  audience      jsonb not null default '{}'::jsonb,   -- {"tags": [...]} (vazio = todos)
  track_links   boolean not null default true,
  status        text not null default 'draft'
                check (status in ('draft', 'scheduled', 'sending', 'done', 'cancelled', 'failed')),
  scheduled_at  timestamptz,
  started_at    timestamptz,
  finished_at   timestamptz,
  last_error    text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
create index broadcasts_user_id_idx on public.broadcasts (user_id, created_at desc);

-- ---------------------------------------------------------------------------
-- Mensagens (caixa de entrada + base das métricas de CTR)
--   direction: in = do contato; out = enviada pela conta
--   source: contact | workflow | inbox | broadcast | instagram_app (enviada pelo app do Instagram)
--   trackable: tinha link rastreado ou botão (entra no cálculo do CTR)
-- ---------------------------------------------------------------------------
create table public.messages (
  id                   uuid primary key default gen_random_uuid(),
  user_id              uuid not null references public.profiles (id) on delete cascade,
  instagram_account_id uuid not null references public.instagram_accounts (id) on delete cascade,
  contact_id           uuid not null references public.contacts (id) on delete cascade,
  direction            text not null check (direction in ('in', 'out')),
  source               text not null check (source in ('contact', 'workflow', 'inbox', 'broadcast', 'instagram_app')),
  kind                 text not null default 'text',
  text                 text,
  buttons              jsonb not null default '[]'::jsonb,
  mid                  text,
  status               text not null default 'sent' check (status in ('received', 'sending', 'sent', 'failed')),
  error                text,
  workflow_id          uuid references public.workflows (id) on delete set null,
  node_id              text,
  execution_id         uuid references public.workflow_executions (id) on delete set null,
  broadcast_id         uuid references public.broadcasts (id) on delete set null,
  trackable            boolean not null default false,
  clicked_at           timestamptz,
  created_at           timestamptz not null default now()
);
create unique index messages_account_mid_idx on public.messages (instagram_account_id, mid) where mid is not null;
create index messages_contact_idx on public.messages (contact_id, created_at desc);
create index messages_user_out_idx on public.messages (user_id, created_at desc) where direction = 'out';
create index messages_workflow_idx on public.messages (workflow_id, node_id) where workflow_id is not null;
create index messages_broadcast_idx on public.messages (broadcast_id) where broadcast_id is not null;
create index messages_execution_idx on public.messages (execution_id) where execution_id is not null;

-- Links rastreados: /r/<code> registra o clique e redireciona
create table public.tracked_links (
  id               bigint generated always as identity primary key,
  code             text not null unique,
  user_id          uuid not null references public.profiles (id) on delete cascade,
  message_id       uuid not null references public.messages (id) on delete cascade,
  url              text not null check (char_length(url) <= 2000),
  clicks           integer not null default 0,
  first_clicked_at timestamptz,
  last_clicked_at  timestamptz,
  created_at       timestamptz not null default now()
);
create index tracked_links_message_idx on public.tracked_links (message_id);
create index tracked_links_user_idx on public.tracked_links (user_id);

create table public.broadcast_recipients (
  id           bigint generated always as identity primary key,
  broadcast_id uuid not null references public.broadcasts (id) on delete cascade,
  contact_id   uuid not null references public.contacts (id) on delete cascade,
  status       text not null default 'pending'
               check (status in ('pending', 'processing', 'sent', 'skipped', 'failed')),
  reason       text,
  message_id   uuid references public.messages (id) on delete set null,
  processed_at timestamptz,
  unique (broadcast_id, contact_id)
);
create index broadcast_recipients_pending_idx on public.broadcast_recipients (broadcast_id, id) where status = 'pending';
create index broadcast_recipients_contact_idx on public.broadcast_recipients (contact_id);

-- ---------------------------------------------------------------------------
-- Execuções aguardando: delay, resposta do contato (follow-up) ou clique em botão
-- ---------------------------------------------------------------------------
alter table public.workflow_executions
  add column if not exists waiting_for text check (waiting_for in ('delay', 'reply', 'button')),
  add column if not exists wait_until  timestamptz;
create index if not exists workflow_executions_waiting_idx
  on public.workflow_executions (contact_id) where status = 'waiting';

create trigger broadcasts_updated_at before update on public.broadcasts
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- RLS sem policies + sem privilégios para a Data API (mesmo padrão da 001)
-- ---------------------------------------------------------------------------
alter table public.broadcasts           enable row level security;
alter table public.messages             enable row level security;
alter table public.tracked_links        enable row level security;
alter table public.broadcast_recipients enable row level security;

do $$
declare r text;
begin
  foreach r in array array['anon', 'authenticated'] loop
    if exists (select 1 from pg_roles where rolname = r) then
      execute format('revoke all on public.broadcasts, public.messages, public.tracked_links, '
                     'public.broadcast_recipients from %I', r);
    end if;
  end loop;
end
$$;
