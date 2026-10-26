import { expect, test } from "@playwright/test"
import { mockApi } from "./mock-api"

test("la page d'accueil présente les fonctionnalités", async ({ page }) => {
  await mockApi(page)
  await page.goto("/")
  await expect(page.getByRole("heading", { level: 1 })).toContainText("bon moment")
  await expect(page.getByRole("heading", { name: "Copilote IA" })).toBeVisible()
  await expect(page.getByRole("link", { name: /Analyser un trajet/ }).first()).toBeVisible()
})

test("inscription puis accès au compte", async ({ page }) => {
  const api = await mockApi(page)
  await page.goto("/inscription")
  await page.getByLabel("Nom complet").fill("Alice Martin")
  await page.getByLabel("E-mail").fill("alice@example.com")
  await page.locator("#password").fill("MotDePasse!123")
  await page.getByLabel("Confirmer le mot de passe").fill("MotDePasse!123")
  await page.getByRole("button", { name: "Créer mon compte" }).click()
  await expect(page).toHaveURL(/\/trajet/)
  expect(api.requests.find((r) => r.path === "/auth/register").body.email).toBe("alice@example.com")
  await page.goto("/compte")
  await expect(page.getByRole("heading", { name: "Alice Martin" })).toBeVisible()
  await expect(page.getByText("Adresse non confirmée")).toBeVisible()
})

test("mots de passe différents : erreur sans appel à l'API", async ({ page }) => {
  const api = await mockApi(page)
  await page.goto("/inscription")
  await page.getByLabel("Nom complet").fill("Bob")
  await page.getByLabel("E-mail").fill("bob@example.com")
  await page.locator("#password").fill("MotDePasse!123")
  await page.getByLabel("Confirmer le mot de passe").fill("Autre!123456")
  await page.getByRole("button", { name: "Créer mon compte" }).click()
  await expect(page.getByRole("alert")).toContainText("ne correspondent pas")
  expect(api.requests.some((r) => r.path === "/auth/register")).toBe(false)
})

test("analyse d'un trajet avec profil moto", async ({ page }) => {
  const api = await mockApi(page)
  await page.goto("/trajet?de=39.75890,-84.19160,Dayton&a=39.96120,-82.99880,Columbus")
  await page.getByLabel("Conducteur / véhicule").selectOption("moto")
  await page.getByRole("button", { name: /Analyser/ }).first().click()

  await expect(page.getByText("Indice de risque du trajet")).toBeVisible()
  expect(api.requests.findLast((r) => r.path === "/predict/trip").body.profile).toBe("moto")  // la page lance aussi une analyse à l'ouverture du lien
  await expect(page.getByText(/Conseils · Moto/)).toBeVisible()
  await expect(page.getByText(/éblouissement/).first()).toBeVisible()
  await expect(page.getByRole("heading", { name: /Pauses conseillées/ })).toBeVisible()
  await expect(page.getByText("Nid-de-poule")).toBeVisible()
  await expect(page.getByText("Autoroute").first()).toBeVisible()
})

test("mode conduite en plein écran", async ({ page }) => {
  await mockApi(page)
  await page.goto("/trajet?de=39.75890,-84.19160,Dayton&a=39.96120,-82.99880,Columbus")
  await page.getByRole("button", { name: /Analyser/ }).first().click()
  await page.getByRole("button", { name: /Mode conduite/ }).click()
  const dialog = page.getByRole("dialog", { name: "Mode conduite" })
  await expect(dialog).toBeVisible()
  await expect(dialog.getByText("Meilleur départ")).toBeVisible()
  await page.keyboard.press("Escape")
  await expect(dialog).toBeHidden()
})

test("le copilote demande un compte aux visiteurs", async ({ page }) => {
  await mockApi(page)
  await page.route("http://api.test/assistant/status", (r) => r.fulfill({ contentType: "application/json", body: '{"available":true}' }))
  await page.goto("/copilote")
  await expect(page.getByText("Le copilote IA est réservé aux membres")).toBeVisible()
})
