import React from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './pages/App'
import { ThemeProvider } from './contexts/ThemeContext'
import './index.css'

const root = createRoot(document.getElementById('root')!)
root.render(
  <ThemeProvider>
    <App />
  </ThemeProvider>
)


