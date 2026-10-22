import apiService from '../services/api'

const STORAGE_KEY = 'theme'
const VALID = ['light', 'dark', 'system']

export function getStoredTheme() {
  const stored = localStorage.getItem(STORAGE_KEY)
  return VALID.includes(stored) ? stored : 'system'
}

export function resolveTheme(preference) {
  if (preference === 'system') {
    return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  }
  return preference === 'dark' ? 'dark' : 'light'
}

// Applies a preference ('light' | 'dark' | 'system') to the whole app and remembers it locally.
export function applyTheme(preference) {
  const value = VALID.includes(preference) ? preference : 'system'
  localStorage.setItem(STORAGE_KEY, value)
  document.documentElement.setAttribute('data-theme', resolveTheme(value))
}

// Called once at startup: apply the cached choice instantly, follow the OS when set to
// "system", then let the saved database preference win if the user is signed in.
export function initTheme() {
  applyTheme(getStoredTheme())
  window.matchMedia?.('(prefers-color-scheme: dark)').addEventListener?.('change', () => {
    if (getStoredTheme() === 'system') applyTheme('system')
  })
  if (localStorage.getItem('accessToken')) {
    apiService.settings.getPreferences().then((prefs) => applyTheme(prefs.theme)).catch(() => {})
  }
}
