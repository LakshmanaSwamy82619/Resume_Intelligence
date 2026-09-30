import { Moon, Sun } from 'lucide-react'
import { useTheme } from '../state/ThemeContext'

export default function ThemeToggle({ className = '' }) {
  const { theme, toggleTheme } = useTheme()
  const nextTheme = theme === 'dark' ? 'light' : 'dark'
  const Icon = theme === 'dark' ? Sun : Moon
  return <button
    type="button"
    className={`theme-toggle ${className}`.trim()}
    onClick={toggleTheme}
    aria-label={`Switch to ${nextTheme} theme`}
    title={`Switch to ${nextTheme} theme`}
  ><Icon size={16} /><span>{theme === 'dark' ? 'Light' : 'Dark'}</span></button>
}
