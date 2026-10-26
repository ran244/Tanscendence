import { createContext, useContext, useEffect, useLayoutEffect, useState } from 'react'

const ThemeContext = createContext(null)
const THEME_KEY = 'ma-theme'

function isTheme(value) {
  return value === 'light' || value === 'dark'
}

function initialTheme() {
  if (typeof document === 'undefined') return 'light'

  const documentTheme = document.documentElement.dataset.theme
  if (isTheme(documentTheme)) return documentTheme

  try {
    const savedTheme = window.localStorage.getItem(THEME_KEY)
    if (isTheme(savedTheme)) return savedTheme
  } catch {
    // Fall back safely when storage is unavailable.
  }
  return 'light'
}

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(initialTheme)

  useLayoutEffect(() => {
    document.documentElement.dataset.theme = theme
  }, [theme])

  useEffect(() => {
    try {
      window.localStorage.setItem(THEME_KEY, theme)
    } catch {
      // ignore storage errors (e.g. private browsing)
    }
  }, [theme])

  useEffect(() => {
    const syncTheme = (event) => {
      if (event.key !== THEME_KEY) return
      setTheme(isTheme(event.newValue) ? event.newValue : 'light')
    }
    window.addEventListener('storage', syncTheme)
    return () => window.removeEventListener('storage', syncTheme)
  }, [])

  const toggleTheme = () => setTheme((t) => (t === 'light' ? 'dark' : 'light'))

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  return useContext(ThemeContext)
}
