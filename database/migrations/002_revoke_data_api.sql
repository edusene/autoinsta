-- Defesa em profundidade: o frontend nunca acessa tabelas diretamente (tudo passa
-- pelo backend). Além do RLS sem policies, removemos qualquer privilégio dos papéis
-- usados pela Data API do Supabase. Condicional: os papéis só existem no Supabase.
do $$
declare
  r text;
begin
  foreach r in array array['anon', 'authenticated'] loop
    if exists (select 1 from pg_roles where rolname = r) then
      execute format('revoke all on all tables in schema public from %I', r);
      execute format('revoke all on all sequences in schema public from %I', r);
      execute format('revoke execute on all functions in schema public from %I', r);
      execute format('alter default privileges for role postgres in schema public revoke all on tables from %I', r);
      execute format('alter default privileges for role postgres in schema public revoke all on sequences from %I', r);
      execute format('alter default privileges for role postgres in schema public revoke execute on functions from %I', r);
    end if;
  end loop;
end
$$;
