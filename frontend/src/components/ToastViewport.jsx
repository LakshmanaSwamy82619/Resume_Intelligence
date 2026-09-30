import { useEffect, useState } from 'react'
import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react'

let nextToastId = 0
export const toast = {
  success: (message) => window.dispatchEvent(new CustomEvent('ri:toast', { detail: { id: ++nextToastId, type: 'success', message } })),
  error: (message) => window.dispatchEvent(new CustomEvent('ri:toast', { detail: { id: ++nextToastId, type: 'error', message } })),
  info: (message) => window.dispatchEvent(new CustomEvent('ri:toast', { detail: { id: ++nextToastId, type: 'info', message } })),
  async copy(text, label = 'Text') {
    try {
      await navigator.clipboard.writeText(text)
      toast.success(`${label} copied.`)
    } catch {
      toast.error('Could not access the clipboard. Please copy the text manually.')
    }
  },
}

const icons = { success: CheckCircle2, error: AlertCircle, info: Info }

export default function ToastViewport() {
  const [items, setItems] = useState([])
  useEffect(() => {
    const addToast = (event) => {
      const item = event.detail
      setItems((current) => [...current.slice(-3), item])
      window.setTimeout(() => setItems((current) => current.filter((toastItem) => toastItem.id !== item.id)), 4500)
    }
    window.addEventListener('ri:toast', addToast)
    return () => window.removeEventListener('ri:toast', addToast)
  }, [])
  return <div className="toast-viewport" aria-live="polite" aria-relevant="additions text">
    {items.map((item) => {
      const Icon = icons[item.type] || Info
      return <div className={`app-toast toast-${item.type}`} key={item.id} role={item.type === 'error' ? 'alert' : 'status'}>
        <Icon size={18} aria-hidden="true" /><span>{item.message}</span>
        <button type="button" aria-label="Dismiss notification" onClick={() => setItems((current) => current.filter((toastItem) => toastItem.id !== item.id))}><X size={15} /></button>
      </div>
    })}
  </div>
}
