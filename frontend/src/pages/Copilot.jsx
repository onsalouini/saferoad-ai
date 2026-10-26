import { Link } from "react-router-dom"
import Assistant, { CopilotIcon } from "../components/Assistant"
import { Card } from "../components/ui"

const SUGGESTIONS = [
  "Comment lire l'indice de risque de SafeRoad ?",
  "Quels sont les dangers de la conduite sous la pluie ?",
  "Comment préparer un long trajet de nuit ?",
  "Pourquoi la localisation pèse-t-elle autant dans le modèle ?",
]

export default function Copilot() {
  return (
    <div className="mx-auto max-w-page px-4 py-10">
      <div className="grid gap-6 lg:grid-cols-12">
        <div className="lg:col-span-4 space-y-4">
          <div>
            <p className="eyebrow text-accent">Nouveau · IA générative</p>
            <h1 className="mt-2 text-3xl font-bold tracking-tight">Copilote IA</h1>
            <p className="mt-3 text-soft">
              Un assistant conversationnel qui explique le modèle, répond à vos questions de sécurité routière et,
              depuis une analyse de trajet, rédige un briefing personnalisé.
            </p>
          </div>
          <Card bodyClass="card-pad space-y-3 text-sm text-soft">
            <p className="font-semibold text-ink">Pour un briefing de trajet</p>
            <p>Lancez une analyse, puis ouvrez la carte « Copilote IA » en bas des résultats : il lit les chiffres de votre trajet.</p>
            <Link to="/trajet" className="btn-primary w-full">Analyser un trajet →</Link>
          </Card>
          <p className="text-xs text-muted">
            Le copilote s'appuie sur les sorties du modèle et sur des connaissances générales. Il n'a accès ni au trafic
            en temps réel ni aux alertes officielles.
          </p>
        </div>

        <Card className="lg:col-span-8" eyebrow="Discussion" title={<span className="inline-flex items-center gap-2"><CopilotIcon className="h-5 w-5 text-accent" /> Copilote SafeRoad</span>}>
          <Assistant height="h-[30rem]" suggestions={SUGGESTIONS}
            intro="Posez une question sur la sécurité routière, la météo ou le fonctionnement du modèle." />
        </Card>
      </div>
    </div>
  )
}
