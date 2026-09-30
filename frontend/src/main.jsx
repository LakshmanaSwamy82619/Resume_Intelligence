import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { AuthProvider } from './state/AuthContext'
import { ThemeProvider } from './state/ThemeContext'
import App from './App'
import './styles.css'
import './theme.css'

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ThemeProvider><BrowserRouter><AuthProvider><App /></AuthProvider></BrowserRouter></ThemeProvider>
  </React.StrictMode>,
)
