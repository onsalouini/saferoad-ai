# Évaluation de la fiabilité du modèle SafeRoad AI

## Mise à jour : modèle v3 (26/10/2026)

Les recommandations 1 à 3 ci-dessous ont été appliquées (`ml/train.py`) :

| | v2 | v3 |
|---|---|---|
| `Distance(mi)` (fuite de données) | utilisée | retirée (93 variables) |
| Découpage | aucun garanti | entraînement 2016, 2017, 2021 · test **2022** (234 573 accidents jamais vus) |
| Calibration | aucune (`scale_pos_weight`) | Platt sur un jeu séparé |
| ROC-AUC (2022) | 0,881 | **0,900** |
| PR-AUC (2022) | 0,776 | **0,812** |
| Brier (2022) | 0,160 | **0,121** |
| Score moyen / taux observé | 48,5 % / 33,5 % | **34,5 % / 33,5 %** |

Seuils recalculés pour garder les compromis de la v2 (rappel visé 80 / 66 / 42 % sur le jeu de calibration) :
Standard 0,51 · Pro 0,70 · Strict 0,87. Sur 2022 : rappel 73 / 57 / 36 %, précision 75 / 82 / 89 %.
Niveaux : Modéré dès 0,27, Élevé dès 0,51, Très élevé dès 0,87.

Calibration sur 2022 : bonne jusqu'à 0,5 ; légère surestimation au-delà (prédit 0,95 → observé 0,91).

**Nouvelles observations (tests de cohérence v3, `ml/reports/evaluation.json`)** :
pluie forte +13,5 pts, nuit +9,8 pts, brouillard +3,5 pts, intersection +8,6 pts (cohérent) ;
neige légère −2,8 pts, heure de pointe −3,8 pts, vent fort −0,6 pt (incohérent ou neutre) ;
**feu de signalisation −31,5 pts** : en ville, les accidents sont plus fréquents mais moins graves (vitesses
basses). C'est une association réelle du jeu de données, mais elle fait baisser l'indice des trajets urbains
maintenant que les équipements sont détectés via OpenStreetMap. La localisation reste le premier facteur
(perte d'AUC de 0,17 si on la mélange).

**Non traité, faute de données** : la recommandation 4 (risque d'*occurrence*) demande des exemples « sans
accident » avec leur exposition (volumes de trafic, météo historique aux mêmes lieux et heures), et un modèle
hors États-Unis demande un jeu d'accidents local géolocalisé. Aucun des deux n'est disponible dans le projet.
Seul un fragment (1,1 M sur 7,7 M accidents) a servi à l'entraînement.

---

## Rapport initial (modèle v2)

> Rapport produit par `ml/evaluate.py` (données brutes : `ml/reports/evaluation.json`).
> Évalué le 19/10/2026 sur **299 581 accidents réels** du jeu US Accidents (mars 2023),
> fragment 1/7 du miroir Hugging Face `yuvidhepe/us-accidents-updated` (années 2016, 2017, 2021, 2022).

## 1. Modèle analysé

| Élément | Valeur |
|---|---|
| Algorithme | LightGBM `LGBMClassifier` (1 000 arbres, 127 feuilles, profondeur 9, lr 0,05) |
| Variables | 94 (lieu, météo, temps, 13 indicateurs routiers, one-hot météo / saison / État) |
| Déséquilibre | `scale_pos_weight = 3.71` |
| ROC-AUC annoncé | 0,8955 |
| Seuils | standard 0,65 · pro 0,75 · strict 0,85 |

## 2. Que prédit réellement le modèle ?

Le dataset US Accidents ne contient **que des accidents**. Trois cibles possibles ont été testées :

| Cible | ROC-AUC |
|---|---|
| **Severity ≥ 3** | **0,880** ✓ |
| Severity ≥ 2 | 0,725 |
| Severity = 4 | 0,589 |

➡ Le modèle prédit la **probabilité qu'un accident soit grave** (gravité 3-4), **pas** la probabilité
qu'un accident se produise. Dans l'application, le score est donc présenté comme un *indice de risque*
(gravité potentielle) et non comme une probabilité d'accident.

L'encodage `Sunrise_Sunset` (Day/Night) n'a quasiment aucun effet sur l'AUC (0,8799 vs 0,8796).
`Night = 1` a été retenu.

## 3. Performances

| Mesure | Distance réelle | Distance fixée (inférence API) |
|---|---|---|
| ROC-AUC | 0,880 | **0,891** |
| PR-AUC (taux de base 35,5 %) | 0,797 | **0,804** |
| Brier | 0,161 | **0,157** |

Le pouvoir de classement est **bon et conforme à l'annonce**.

### Seuils (distance fixée)

| Mode | Seuil | Rappel | Précision | F1 | Part signalée |
|---|---|---|---|---|---|
| (réf.) | 0,50 | 92 % | 61 % | 0,74 | 53 % |
| **Standard** | 0,65 | 80 % | 70 % | **0,75** | 40 % |
| Pro | 0,75 | 66 % | 77 % | 0,71 | 30 % |
| Strict | 0,85 | 42 % | 86 % | 0,56 | 17 % |

### Stabilité

* **Par année** : AUC de 0,900 (2016) à 0,880 (2022), soit une légère dérive sur les données récentes.
* **Par État** (12 plus représentés) : AUC de 0,84 (OH) à 0,94 (IL).

## 4. Problèmes détectés

| # | Problème | Gravité | Traitement |
|---|---|---|---|
| 1 | **Calibration** : le score surestime fortement (prédit 45 % → 18 % observés ; prédit 25 % → 5 %) à cause de `scale_pos_weight` | Élevée | Score affiché comme indice relatif, avec une courbe de calibration sur la page « Le modèle ». Piste : recalibrer (isotonique / Platt) |
| 2 | **Fuite de données** : `Distance(mi)` = longueur de route impactée **par** l'accident, inconnue avant le trajet (2ᵉ variable en gain, 21 %) | Élevée | Fixée à la médiane (0 mi) à l'inférence ; retirée des explications. Piste : réentraîner sans cette variable |
| 3 | **Dépendance au lieu** : la localisation domine (perte d'AUC de 0,19 si on la mélange). À conditions identiques, le score varie de 1 à 77 selon l'endroit | Moyenne | Signalé dans l'interface. Le modèle apprend en partie *où* les accidents graves sont enregistrés (effets de source / de déclaration) |
| 4 | **Couverture** : entraîné uniquement sur les États-Unis | Moyenne | Hors USA : avertissement explicite, score indicatif |
| 5 | **Bugs de l'ancienne API** : catégories météo mal encodées (`Fair` jamais transmis, colonnes `Clear` / `Snow` / `Thunderstorm` inexistantes), `Sunrise_Sunset` jamais renseigné, `IsWeekend` / `IsRushHour` / `Bump` ignorés par le schéma, plantage au démarrage si le modèle est absent | Élevée | **Corrigés** (`api/ml/features.py`, une seule source de vérité partagée avec l'évaluation) |
| 6 | Vent fort sans effet (−0,6 pt) ; l'heure de pointe ne fait monter le score que dans 27 % des cas | Faible | Documenté |

## 5. Tests de cohérence (300 situations réelles, un facteur modifié à la fois)

| Changement | Effet moyen | Cas en hausse | Verdict |
|---|---|---|---|
| Pluie forte | +9,1 pts | 100 % | ✓ |
| Neige légère | +9,9 pts | 98 % | ✓ |
| Brouillard, visibilité 0,5 mi | +6,1 pts | 94 % | ✓ |
| Nuit (23 h) | +5,2 pts | 95 % | ✓ |
| Heure de pointe (17 h) | +1,0 pt | 27 % | ≈ mitigé |
| Vent fort (35 mph) | −0,6 pt | 49 % | ✕ |
| Intersection | +7,1 pts | 88 % | — |
| Feu de signalisation | −0,1 pt | 56 % | — |

## 6. Verdict

Le modèle est **fiable pour classer des situations** du plus au moins risqué aux États-Unis
(AUC ≈ 0,89, stable dans le temps et entre États), avec des réactions sensées à la météo et à la nuit.
Il **n'est pas fiable comme probabilité absolue** (non calibré), il **ne prédit pas l'occurrence** d'un
accident, et il s'appuie fortement sur la localisation et sur une variable qui fuit l'information.

**Recommandations, par priorité :**
1. Réentraîner sans `Distance(mi)` (et sans autres variables postérieures à l'accident).
2. Recalibrer les probabilités (régression isotonique sur un jeu de validation).
3. Évaluer sur un jeu de test strictement séparé (split temporel, par exemple entraînement ≤ 2021 et test 2022-2023).
   *Limite de ce rapport : le fragment évalué a pu servir à l'entraînement, donc les chiffres sont possiblement optimistes.*
4. Pour estimer un vrai **risque d'occurrence**, ajouter des exemples « sans accident »
   (trafic / exposition), par exemple par échantillonnage négatif spatio-temporel.

## Reproduire

```bash
# Fragment du dataset (~125 Mo)
curl -L -o data/raw/shard0.parquet \
  https://huggingface.co/datasets/yuvidhepe/us-accidents-updated/resolve/main/data/train-00000-of-00007-218a12ee754b447b.parquet
python ml/evaluate.py --data data/raw/shard0.parquet --sample 300000
```
