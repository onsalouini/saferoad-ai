import { useEffect, useState } from "react"
import { CalibrationChart, HBarList } from "../components/charts"
import { Alert, Card, Spinner, Stat } from "../components/ui"
import { api, errorMessage } from "../lib/api"
import { MODES, fmt } from "../lib/risk"

const MODE_LABEL = { "0.50": "Seuil 0,50 (réf.)", ...Object.fromEntries(Object.entries(MODES).map(([k, m]) => [k, m.label])) }

export default function Model() {
  const [info, setInfo] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.get("/model/info").then((r) => setInfo(r.data)).catch((e) => setError(errorMessage(e)))
  }, [])

  if (error) return <div className="mx-auto max-w-page px-4 py-8"><Alert tone="error" title="Impossible de charger le modèle">{error}</Alert></div>
  if (!info) return <div className="mx-auto max-w-page px-4 py-8"><Spinner /></div>

  const ev = info.evaluation
  const m = ev?.metrics

  return (
    <div className="mx-auto max-w-page px-4 py-8 space-y-6">
      <header>
        <p className="eyebrow">Le modèle</p>
        <h1 className="mt-1 text-2xl sm:text-3xl font-bold tracking-tight">Fiabilité du modèle SafeRoad AI</h1>
        <p className="mt-2 max-w-3xl text-soft">
          {info.algorithm} · {info.n_features} variables · évalué de façon indépendante sur
          {ev ? ` ${fmt.int(ev.dataset.rows_evaluated)} accidents réels` : " (rapport d'évaluation absent)"}.
          Cette page présente ce que le modèle prédit réellement, ses performances et ses limites.
        </p>
      </header>

      {!ev && <Alert tone="warning">Lancez <code>python ml/evaluate.py</code> pour générer le rapport d'évaluation.</Alert>}

      {ev && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <Stat label="ROC-AUC mesuré" value={fmt.num(m.roc_auc_distance_fixed, 3)} hint={`annoncé : ${fmt.num(info.declared_roc_auc, 4)}`} />
            <Stat label="PR-AUC" value={fmt.num(m.pr_auc_distance_fixed, 3)} hint={`taux de base : ${fmt.pct(ev.dataset.positive_rate)}`} />
            <Stat label="Score de Brier" value={fmt.num(m.brier_distance_fixed, 3)} hint="0 = parfait · plus bas = mieux" />
            <Stat label="Accidents évalués" value={fmt.int(ev.dataset.rows_evaluated)} hint={`années ${ev.dataset.years.join(", ")}`} />
          </div>

          <Card eyebrow="À lire en premier" title="Ce que le modèle prédit réellement">
            <div className="grid gap-5 lg:grid-cols-2 text-sm text-soft leading-relaxed">
              <div className="space-y-3">
                <p>
                  La cible identifiée est <b className="text-ink">{ev.target.identified}</b> : parmi les hypothèses testées,
                  c'est celle qui reproduit l'AUC annoncée.
                </p>
                <p>{ev.target.meaning}</p>
                <p>
                  Le score SafeRoad est donc un <b className="text-ink">indice de gravité potentielle</b> : à quel point les
                  conditions (lieu, météo, heure, route) ressemblent à celles des accidents graves passés.
                </p>
              </div>
              <ul className="space-y-2">
                {ev.target.hypotheses.filter((h) => h.night_encoding === ev.target.night_encoding).map((h) => (
                  <li key={h.target} className="flex items-center justify-between rounded-lg bg-raised/60 px-3 py-2">
                    <span>Cible « {h.target} »</span>
                    <span className={`tnum font-semibold ${h.target === ev.target.identified ? "text-good" : "text-muted"}`}>
                      AUC {fmt.num(h.roc_auc, 3)} {h.target === ev.target.identified && "✓"}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </Card>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card eyebrow="Calibration" title="Le score surestime la probabilité réelle">
              <CalibrationChart bins={ev.calibration} />
              <p className="mt-3 text-sm text-soft">
                La courbe est sous la diagonale : un score de 45 correspond en réalité à environ
                {" "}{fmt.pct(ev.calibration.find((b) => b.bin === "0.4-0.5")?.observed ?? 0, 0)} d'accidents graves.
                C'est l'effet de <code>scale_pos_weight = {info.hyperparameters.scale_pos_weight}</code> à l'entraînement.
                Le classement des situations reste bon (AUC), mais le score ne doit pas être lu comme un pourcentage.
              </p>
            </Card>

            <Card eyebrow="Modes d'alerte" title="Compromis selon le seuil" bodyClass="px-2 pb-4 pt-2 sm:px-3">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-muted">
                      <th className="px-3 py-2 font-medium">Mode</th>
                      <th className="px-3 py-2 font-medium text-right">Seuil</th>
                      <th className="px-3 py-2 font-medium text-right" title="Part des accidents graves détectés">Rappel</th>
                      <th className="px-3 py-2 font-medium text-right" title="Part des alertes justifiées">Précision</th>
                      <th className="px-3 py-2 font-medium text-right">F1</th>
                      <th className="px-3 py-2 font-medium text-right">Alertes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ev.thresholds.map((t) => (
                      <tr key={t.mode} className="border-t border-line/50">
                        <td className="px-3 py-2 font-medium">{MODE_LABEL[t.mode] || t.mode}</td>
                        <td className="px-3 py-2 text-right tnum text-soft">{Math.round(t.threshold * 100)}</td>
                        <td className="px-3 py-2 text-right tnum">{fmt.pct(t.recall, 0)}</td>
                        <td className="px-3 py-2 text-right tnum">{fmt.pct(t.precision, 0)}</td>
                        <td className="px-3 py-2 text-right tnum">{fmt.num(t.f1, 2)}</td>
                        <td className="px-3 py-2 text-right tnum text-soft">{fmt.pct(t.flagged_rate, 0)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="mt-3 px-3 text-sm text-soft">
                <b className="text-ink">Standard</b> détecte 8 accidents graves sur 10 (meilleur F1).
                <b className="text-ink"> Strict</b> se trompe rarement (86 % de précision) mais en manque plus de la moitié.
              </p>
            </Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card eyebrow="Importance des variables" title="Part du gain dans les arbres">
              <HBarList items={info.feature_importance.slice(0, 12).map((f) => ({ label: f.label, value: f.share }))}
                format={(v) => fmt.pct(v)} />
              <p className="mt-3 text-xs text-muted">Gain cumulé des divisions LightGBM par groupe de variables (one-hot regroupés).</p>
            </Card>
            <Card eyebrow="Importance par permutation" title="Perte d'AUC si on mélange le groupe">
              <HBarList items={ev.permutation_importance.map((p) => ({ label: p.group, value: Math.max(0, p.auc_drop) }))}
                format={(v) => `−${fmt.num(v, 3)}`} labelWidth="14rem" />
              <p className="mt-3 text-sm text-soft">
                La <b className="text-ink">localisation</b> domine : le modèle a surtout appris <i>où</i> les accidents graves
                ont été enregistrés. La météo pèse peu (−{fmt.num(ev.permutation_importance.find((p) => p.group.startsWith("Météo"))?.auc_drop ?? 0, 3)}).
              </p>
            </Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card eyebrow="Stabilité dans le temps" title="ROC-AUC par année">
              <HBarList items={ev.by_year.map((y) => ({ label: String(y.year), value: y.roc_auc_distance_fixed }))}
                max={1} format={(v) => fmt.num(v, 3)} labelWidth="5rem" />
              <p className="mt-3 text-sm text-soft">Légère baisse sur les données récentes (2021-2022) : un réentraînement périodique est conseillé.</p>
            </Card>
            <Card eyebrow="Stabilité géographique" title="ROC-AUC par État (12 plus représentés)">
              <HBarList items={ev.by_state.map((s) => ({ label: s.state, value: s.roc_auc }))}
                max={1} format={(v) => fmt.num(v, 3)} labelWidth="3rem" />
            </Card>
          </div>

          <Card eyebrow="Tests de cohérence" title="Le modèle réagit-il comme attendu ?" bodyClass="px-2 pb-4 pt-2 sm:px-3">
            <p className="px-3 pb-2 text-sm text-soft">
              Sur 300 situations réelles, on change un seul facteur à la fois (via le même code que l'API) et on mesure l'effet sur le score.
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-muted">
                    <th className="px-3 py-2 font-medium">Changement</th>
                    <th className="px-3 py-2 font-medium text-right">Effet moyen</th>
                    <th className="px-3 py-2 font-medium text-right">Cas en hausse</th>
                    <th className="px-3 py-2 font-medium">Verdict</th>
                  </tr>
                </thead>
                <tbody>
                  {ev.directional_tests.map((t) => (
                    <tr key={t.test} className="border-t border-line/50">
                      <td className="px-3 py-2">{t.test}</td>
                      <td className="px-3 py-2 text-right tnum font-semibold">{t.mean_delta_pts > 0 ? "+" : "−"}{fmt.num(Math.abs(t.mean_delta_pts), 1)} pts</td>
                      <td className="px-3 py-2 text-right tnum text-soft">{fmt.pct(t.share_increase, 0)}</td>
                      <td className="px-3 py-2">
                        {t.consistent === true && t.share_increase >= 0.5 && <span className="text-good font-medium">✓ cohérent</span>}
                        {t.consistent === true && t.share_increase < 0.5 && <span className="text-warning font-medium">≈ mitigé</span>}
                        {t.consistent === false && <span className="text-serious font-medium">✕ incohérent</span>}
                        {t.consistent === null && <span className="text-muted">— pas d'attente</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card eyebrow="Verdict" title="Peut-on faire confiance au modèle ?">
            <div className="grid gap-6 lg:grid-cols-2 text-sm leading-relaxed">
              <div>
                <h3 className="mb-2 font-semibold text-good">✓ Points forts</h3>
                <ul className="space-y-2 text-soft list-disc pl-5">
                  <li>Bon pouvoir de classement : ROC-AUC de {fmt.num(m.roc_auc_distance_fixed, 3)} sur données réelles, conforme à l'annonce.</li>
                  <li>Performance homogène entre États (AUC {fmt.num(Math.min(...ev.by_state.map((s) => s.roc_auc)), 2)}–{fmt.num(Math.max(...ev.by_state.map((s) => s.roc_auc)), 2)}) et entre années.</li>
                  <li>Réactions cohérentes à la pluie, la neige, le brouillard et la nuit.</li>
                </ul>
              </div>
              <div>
                <h3 className="mb-2 font-semibold text-serious">⚠ Limites</h3>
                <ul className="space-y-2 text-soft list-disc pl-5">
                  <li>Prédit la <b className="text-ink">gravité</b> d'un accident, pas la probabilité qu'il survienne.</li>
                  <li>Scores non calibrés (surestimation) : à lire comme un indice relatif.</li>
                  <li>Forte dépendance au lieu : à conditions identiques, le score varie de {Math.round(ev.location_only_spread.min * 100)} à {Math.round(ev.location_only_spread.max * 100)} selon l'endroit.</li>
                  <li><code>Distance(mi)</code> est une fuite de données (connue après l'accident) : fixée à {ev.dataset.distance_median_mi} à l'inférence.</li>
                  <li>Valide uniquement aux États-Unis ; le vent fort n'augmente pas le score.</li>
                  <li>Évaluation sur un fragment du dataset qui a pu servir à l'entraînement : chiffres possiblement optimistes.</li>
                </ul>
              </div>
            </div>
          </Card>

          <Card eyebrow="Fiche technique" title="Hyperparamètres">
            <dl className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
              {Object.entries(info.hyperparameters).map(([k, v]) => (
                <div key={k} className="rounded-lg bg-raised/60 px-3 py-2">
                  <dt className="text-xs text-muted">{k}</dt>
                  <dd className="tnum font-medium">{String(v)}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-4 text-xs text-muted">Source d'évaluation : {ev.dataset.source}. Généré le {fmt.date(ev.generated_at)}.</p>
          </Card>
        </>
      )}
    </div>
  )
}
