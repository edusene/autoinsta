import { createClient, type SupabaseClient } from '@supabase/supabase-js'

// A URL e a chave PÚBLICA do Supabase vêm da própria API (/api/public-config),
// assim o painel não precisa de variáveis de ambiente próprias.
export let supabase: SupabaseClient
export let supabaseConfigured = false
export let privacyContactEmail = ''

export async function initSupabase(): Promise<void> {
  let url = ''
  let key = ''
  try {
    const res = await fetch('/api/public-config')
    const json = await res.json()
    url = json?.data?.supabase_url ?? ''
    key = json?.data?.supabase_anon_key ?? ''
    privacyContactEmail = json?.data?.privacy_contact_email ?? ''
  } catch {
    // API indisponível: o login mostra o aviso de configuração
  }
  supabaseConfigured = Boolean(url && key)
  supabase = createClient(url || 'http://localhost', key || 'missing-key', {
    auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
  })
}
