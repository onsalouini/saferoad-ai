import { lazy, Suspense } from "react"
import { BrowserRouter, Link, Route, Routes } from "react-router-dom"
import Navbar from "./components/Navbar"
import { Spinner } from "./components/ui"
import { AuthProvider } from "./context/AuthContext"
import { NotificationProvider } from "./context/NotificationContext"
import Home from "./pages/Home"

// Pages chargées à la demande : la carte (Leaflet) et les graphiques ne pèsent que sur les pages qui les utilisent
const Account = lazy(() => import("./pages/Account"))
const Auth = lazy(() => import("./pages/Auth"))
const Copilot = lazy(() => import("./pages/Copilot"))
const History = lazy(() => import("./pages/History"))
const Model = lazy(() => import("./pages/Model"))
const MyTrips = lazy(() => import("./pages/MyTrips"))
const Simulator = lazy(() => import("./pages/Simulator"))
const Trip = lazy(() => import("./pages/Trip"))
const ForgotPassword = lazy(() => import("./pages/PasswordReset").then((m) => ({ default: m.ForgotPassword })))
const ResetPassword = lazy(() => import("./pages/PasswordReset").then((m) => ({ default: m.ResetPassword })))
const VerifyEmail = lazy(() => import("./pages/Account").then((m) => ({ default: m.VerifyEmail })))

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
        <NotificationProvider>
          <div className="min-h-screen flex flex-col">
            <Navbar />
            <main className="flex-1">
              <Suspense fallback={<div className="mx-auto max-w-page px-4 py-10"><Spinner /></div>}>
                <Routes>
                  <Route path="/" element={<Home />} />
                  <Route path="/trajet" element={<Trip />} />
                  <Route path="/predict" element={<Trip />} />
                  <Route path="/simulation" element={<Simulator />} />
                  <Route path="/copilote" element={<Copilot />} />
                  <Route path="/modele" element={<Model />} />
                  <Route path="/historique" element={<History />} />
                  <Route path="/mes-trajets" element={<MyTrips />} />
                  <Route path="/compte" element={<Account />} />
                  <Route path="/connexion" element={<Auth />} />
                  <Route path="/inscription" element={<Auth />} />
                  <Route path="/mot-de-passe-oublie" element={<ForgotPassword />} />
                  <Route path="/reinitialiser" element={<ResetPassword />} />
                  <Route path="/verifier-email" element={<VerifyEmail />} />
                  <Route path="*" element={<NotFound />} />
                </Routes>
              </Suspense>
            </main>
            <footer className="border-t border-line/60 py-6 text-center text-xs text-muted">
              SafeRoad AI · Données : US Accidents (Moosavi et al.), OpenStreetMap, OSRM, Open-Meteo · IA : Claude (Anthropic) · Alertes : NWS ·
              Outil d'aide à la décision, ne remplace pas la vigilance du conducteur.
            </footer>
          </div>
        </NotificationProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
