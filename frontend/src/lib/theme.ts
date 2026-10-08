import { useSyncExternalStore } from 'react'

export type Theme = 'light' | 'dark'

// Preferência por navegador. O index.html aplica o tema antes do React carregar (sem "piscar").
const STORAGE_KEY = 'autoinsta-theme'
const listeners = new Set<() => void>()

export function getTheme(): Theme {
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'
}

export function setTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme
  try {
    localStorage.setItem(STORAGE_KEY, theme)
  } catch {
    // modo privado / armazenamento bloqueado: vale só nesta sessão
  }
  listeners.forEach((notify) => notify())
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function useTheme(): Theme {
  return useSyncExternalStore(subscribe, getTheme)
}
