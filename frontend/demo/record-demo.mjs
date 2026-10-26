// Enregistre une vidéo de démonstration de SafeRoad AI (application réelle : API, modèle, services externes).
// Prérequis : API sur http://localhost:8000 et frontend sur http://localhost:5173 (npx vite preview).
// Usage : node demo/record-demo.mjs [dossier_de_sortie]    (navigateur : Edge, ou PW_CHANNEL=chromium)
import { chromium } from "@playwright/test"
import { mkdirSync } from "node:fs"

const OUT = process.argv[2] || "demo-video"
const BASE = process.env.DEMO_URL || "http://localhost:5173"
const SIZE = { width: 1440, height: 810 }
mkdirSync(OUT, { recursive: true })

const browser = await chromium.launch({ channel: process.env.PW_CHANNEL || "msedge" })
const context = await browser.newContext({
  viewport: SIZE, recordVideo: { dir: OUT, size: SIZE }, locale: "fr-FR", timezoneId: "America/New_York",
  colorScheme: "dark", permissions: ["geolocation"], geolocation: { latitude: 39.7589, longitude: -84.1916 },
})
const page = await context.newPage()
const pause = (ms) => page.waitForTimeout(ms)

// Sous-titre en bas de l'écran (vidéo lisible sans le son, comme sur LinkedIn)
await context.addInitScript(() => {
  window.__caption = (title, text) => {
    let el = document.getElementById("__demo_caption")
    if (!el) {
      el = document.createElement("div")
      el.id = "__demo_caption"
      el.style.cssText = "position:fixed;left:50%;bottom:28px;transform:translateX(-50%);z-index:99999;max-width:78%;" +
        "padding:14px 26px;border-radius:16px;background:rgba(13,17,23,.92);border:1px solid rgba(57,135,229,.7);" +
        "box-shadow:0 10px 40px rgba(0,0,0,.5);color:#f0efec;font:500 20px system-ui,Segoe UI,sans-serif;text-align:center;" +
        "transition:opacity .35s;pointer-events:none"
      document.body.appendChild(el)
    }
    el.style.opacity = title ? "1" : "0"
    el.innerHTML = title ? `<div style="font-weight:700;color:#5aa2f0;font-size:15px;letter-spacing:.06em;text-transform:uppercase;margin-bottom:4px">${title}</div>${text || ""}` : ""
  }
})
const caption = async (title, text) => {
  await page.evaluate(([t, x]) => window.__caption?.(t, x), [title, text]).catch(() => {})
}
const scrollTo = async (locator, block = "center") => {
  await locator.first().evaluate((el, b) => el.scrollIntoView({ behavior: "smooth", block: b }), block).catch(() => {})
  await pause(1300)
}
const smoothScroll = async (dy, steps = 12) => {
  for (let i = 0; i < steps; i++) { await page.mouse.wheel(0, dy / steps); await pause(70) }
  await pause(600)
}
const step = async (name, fn) => {
  try { await fn() } catch (e) { console.warn(`Étape « ${name} » incomplète : ${e.message.split("\n")[0]}`) }
}

// 1. Accueil
await step("accueil", async () => {
  await page.goto(BASE)
  await pause(1200)
  await caption("SafeRoad AI", "Anticiper le risque de chaque trajet : quand partir, par où passer.")
  await pause(3500)
  await caption("Fonctionnalités", "Analyse de trajet, meilleur horaire, copilote IA, simulateur, transparence du modèle.")
  await scrollTo(page.getByText("Tout ce qu'il faut pour décider avant de partir"), "start")
  await pause(2500)
  await smoothScroll(700)
  await pause(1500)
  await caption("Comment ça marche", "Itinéraire réel, météo prévue à l'heure de passage, modèle LightGBM sur des millions d'accidents.")
  await smoothScroll(900)
  await pause(2000)
})

// 2. Inscription
await step("inscription", async () => {
  await page.goto(`${BASE}/inscription`)
  await caption("Inscription", "Compte gratuit : historique, copilote IA et alertes de départ.")
  await pause(1200)
  await page.getByLabel("Nom complet").pressSequentially("Ons Alouini", { delay: 60 })
  await page.getByLabel("E-mail").pressSequentially(`ons.demo${Date.now() % 10000}@example.com`, { delay: 35 })
  await page.locator("#password").pressSequentially("SafeRoad!2026", { delay: 60 })
  await pause(600)
  await page.getByLabel("Confirmer le mot de passe").pressSequentially("SafeRoad!2026", { delay: 50 })
  await pause(900)
  await page.getByRole("button", { name: "Créer mon compte" }).click()
  await page.waitForURL(/\/trajet/, { timeout: 15000 })
})

// 3. Analyse de trajet
await step("trajet", async () => {
  await caption("Analyse de trajet", "Départ et arrivée : l'itinéraire réel est calculé puis découpé en tronçons.")
  await pause(800)
  const dep = page.getByRole("combobox").first()
  await dep.click()
  await dep.pressSequentially("Dayton, Ohio", { delay: 70 })
  await page.getByRole("option").first().waitFor({ timeout: 15000 })
  await pause(700)
  await page.getByRole("option").first().click()
  const arr = page.getByRole("combobox").nth(1)
  await arr.click()
  await arr.pressSequentially("Columbus, Ohio", { delay: 70 })
  await page.getByRole("option").first().waitFor({ timeout: 15000 })
  await pause(700)
  await page.getByRole("option").first().click()
  await pause(800)
  await page.getByRole("button", { name: /Analyser le trajet/ }).click()
  await caption("Analyse en cours", "Météo à l'heure de passage, équipements OpenStreetMap, trafic TomTom, alertes officielles…")
  await page.getByText("Indice de risque du trajet").waitFor({ timeout: 90000 })
  await pause(800)
  await caption("Résultat", "Carte colorée par niveau de risque et indice du trajet.")
  await scrollTo(page.locator(".leaflet-container"))
  await pause(3000)
  await scrollTo(page.getByText("Indice de risque du trajet"), "start")
  await caption("Meilleur moment pour partir", "24 heures de départs comparés : SafeRoad propose le créneau le plus sûr.")
  await pause(3500)
})

await step("prévision et éblouissement", async () => {
  await scrollTo(page.getByText("Indice de risque selon l'heure de départ"))
  await caption("Prévision sur 24 h", "L'indice selon l'heure de départ, avec le seuil d'alerte du mode choisi.")
  await page.mouse.move(700, 450)
  await pause(3000)
  await scrollTo(page.getByText("Incidents et signalements"))
  await caption("En temps réel", "Incidents de circulation (TomTom), signalements des utilisateurs et pauses conseillées.")
  await pause(3500)
  await scrollTo(page.getByText("Risque tronçon par tronçon"))
  await caption("Tronçon par tronçon", "Type de route, météo au passage, équipements… et soleil bas face à vous.")
  await pause(3500)
})

// 4. Copilote IA (briefing du trajet)
await step("copilote", async () => {
  const btn = page.getByRole("button", { name: /Fais-moi un briefing de ce trajet/ })
  await scrollTo(btn)
  await caption("Copilote IA", "Il lit l'analyse et rédige un briefing en langage clair.")
  await pause(1200)
  await btn.click()
  await page.getByRole("button", { name: "Envoyer" }).waitFor({ timeout: 90000 })
  await pause(1200)
  const answer = page.locator("[aria-live=polite]").last()
  await answer.evaluate((el) => el.scrollTo({ top: 0, behavior: "smooth" })).catch(() => {})
  await pause(2500)
  for (let i = 0; i < 4; i++) {
    await answer.evaluate((el) => el.scrollBy({ top: 140, behavior: "smooth" })).catch(() => {})
    await pause(1600)
  }
  await pause(1500)
})

// 5. Mode conduite
await step("mode conduite", async () => {
  const btn = page.getByRole("button", { name: /Mode conduite/ })
  await scrollTo(btn)
  await btn.click()
  await caption("Mode conduite", "Plein écran épuré, résumé lu à voix haute, écran maintenu allumé.")
  await pause(4500)
  await page.keyboard.press("Escape")
  await pause(800)
})

// 6. Alertes de départ
await step("alertes", async () => {
  const btn = page.getByRole("button", { name: /Recevoir des alertes pour ce trajet/ })
  await scrollTo(btn)
  await caption("Alertes de départ", "Enregistrez votre trajet régulier : il est analysé avant chaque départ.")
  await btn.click()
  await pause(1500)
  await page.getByRole("button", { name: "Enregistrer" }).click()
  await pause(1500)
  await page.goto(`${BASE}/mes-trajets`)
  await page.getByRole("button", { name: "Vérifier maintenant" }).first().waitFor({ timeout: 15000 })
  await caption("Mes trajets", "Notification dans l'application, push sur le téléphone et e-mail si le risque est élevé.")
  await pause(1500)
  await page.getByRole("button", { name: "Vérifier maintenant" }).first().click()
  await page.locator("li", { hasText: "Départ prévu à" }).first().waitFor({ timeout: 90000 })
  await pause(4000)
})

// 7. Simulateur
await step("simulateur", async () => {
  await page.goto(`${BASE}/simulation`)
  await caption("Simulateur", "Et si… ? Pluie forte, de nuit, sur autoroute : le modèle explique chaque facteur.")
  await pause(1000)
  const lieu = page.getByRole("combobox").first()
  await lieu.click()
  await lieu.fill("")  // le champ reprend le dernier lieu utilisé
  await lieu.pressSequentially("Miami, Florida", { delay: 60 })
  await page.getByRole("option").first().waitFor({ timeout: 15000 })
  await page.getByRole("option").first().click()
  await page.locator("#weather").selectOption("Heavy Rain")
  await page.getByText("Il fait nuit").click()
  await page.getByRole("radio", { name: "Autoroute" }).click()
  await pause(800)
  await page.getByRole("button", { name: /Calculer le risque/ }).click()
  await page.getByText("Ce qui influence ce score").waitFor({ timeout: 30000 })
  await scrollTo(page.getByText("Ce qui influence ce score"))
  await pause(4000)
})

// 8. Copilote avec outils
await step("copilote outils", async () => {
  await page.goto(`${BASE}/copilote`)
  await caption("Copilote IA avec outils", "Il lance lui-même analyses et simulations pour répondre.")
  const input = page.locator("#copilot-input")
  await input.waitFor({ timeout: 15000 })
  await input.pressSequentially("Quel est le risque maintenant à Miami, et si je partais à 23 h sous la pluie ?", { delay: 30 })
  await pause(700)
  await page.getByRole("button", { name: "Envoyer" }).click()
  await page.getByRole("button", { name: "Envoyer" }).waitFor({ timeout: 90000 })
  await pause(1500)
  const box = page.locator("[aria-live=polite]").last()
  for (let i = 0; i < 3; i++) {
    await box.evaluate((el) => el.scrollBy({ top: 160, behavior: "smooth" })).catch(() => {})
    await pause(1600)
  }
  await pause(1500)
})

// 9. Transparence du modèle
await step("modèle", async () => {
  await page.goto(`${BASE}/modele`)
  await caption("Transparence du modèle", "Performances sur une année jamais vue, calibration, tests de cohérence et limites.")
  await pause(3000)
  await smoothScroll(800)
  await pause(2000)
  await smoothScroll(900)
  await pause(2500)
})

// 10. Fin
await step("fin", async () => {
  await page.goto(BASE)
  await pause(800)
  await caption("SafeRoad AI", "Python · FastAPI · LightGBM · React · IA générative — prenez la route au bon moment.")
  await pause(4500)
})

const video = page.video()
await context.close()
await browser.close()
console.log("Vidéo :", await video.path())
