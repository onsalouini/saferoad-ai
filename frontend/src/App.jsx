import { BrowserRouter, Link, Route, Routes } from "react-router-dom"
import Navbar from "./components/Navbar"
import { AuthProvider } from "./context/AuthContext"
import Auth from "./pages/Auth"
import History from "./pages/History"
import Home from "./pages/Home"
import Model from "./pages/Model"
import Simulator from "./pages/Simulator"
import Trip from "./pages/Trip"

function NotFound() {
  return (
    <div className="mx-auto max-w-xl px-4 py-20 text-center">
      <h1 className="text-3xl font-bold">Page introuvable</h1>
      <Link to="/" className="btn-primary mt-6">Retour à l'accueil</Link>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <div className="min-h-screen flex flex-col">
          <Navbar />
          <main className="flex-1">
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/trajet" element={<Trip />} />
              <Route path="/predict" element={<Trip />} />
              <Route path="/simulation" element={<Simulator />} />
              <Route path="/modele" element={<Model />} />
              <Route path="/historique" element={<History />} />
              <Route path="/connexion" element={<Auth />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </main>
          <footer className="border-t border-line/60 py-6 text-center text-xs text-muted">
            SafeRoad AI · Données : US Accidents (Moosavi et al.), OpenStreetMap, OSRM, Open-Meteo ·
            Outil d'aide à la décision, ne remplace pas la vigilance du conducteur.
          </footer>
        </div>
      </AuthProvider>
    </BrowserRouter>
  )
}
