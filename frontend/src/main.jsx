import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { api } from './lib/api'
import { configureLevels } from './lib/risk'

// Seuils du modèle chargé (attente brève ; valeurs par défaut si l'API ne répond pas)
const options = api.get('/model/options', { timeout: 3000 }).then((r) => configureLevels(r.data)).catch(() => {})

options.finally(() => {
  createRoot(document.getElementById('root')).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
})

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => {}))
}
