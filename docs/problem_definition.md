# Définition du problème

Statut : brouillon, à valider par le groupe puis à figer par le tag git `v0-definition`.
Toute modification après le tag est datée et justifiée en bas de ce fichier.

## 1. Cible

- Variable : concentration moyenne de PM2.5 du jour civil local t+1, en µg/m³, **par station**.
- Jour civil local : de 00:00 à 23:59, fuseau Asia/Bangkok (UTC+7, sans heure d'été).
- Validité d'un jour : au moins `forecast.min_valid_hours_per_day` heures présentes sur 24 (18 par défaut).
  **[HYPOTHÈSE NON VÉRIFIÉE]** Seuil de 75 % de complétude attribué à l'EPA (40 CFR Part 50, Appendix N), à sourcer.
  Impact si faux : le nombre de jours valides change, pas la méthode.
- Un jour invalide est exclu, jamais imputé.

## 2. Instant d'émission

- La prévision de t+1 est émise le jour t à l'heure H (`forecast.emission_hour`, 0 <= H < 24).
- **H : non fixé.** Il dépend du délai de publication des mesures PM2.5 (à mesurer à l'étape 2)
  et de l'usage visé.
- Toute variable doit être disponible à l'heure H du jour t, délai de publication de sa source compris.

## 3. Disponibilité des variables à l'heure H du jour t

| Variable | Disponible ? | Règle |
| --- | --- | --- |
| PM2.5 horaire des jours t−1 et antérieurs | Oui | Autorisée |
| PM2.5 horaire du jour t, heures 00 à H−1 | Oui, sous réserve du délai de publication | Autorisée (moyenne partielle) |
| PM2.5 du jour t à partir de H, et de t+1 | Non | Interdite |
| Météo observée jusqu'à H le jour t | En exploitation : via l'API de prévision Open-Meteo (IFS, sans délai) | Autorisée |
| Météo observée de t+1 | Non | Variante oracle (b) uniquement |
| Calendrier de t+1 (mois, jour de semaine, Tết) | Oui, déterministe | Autorisée |

Écart d'exploitation à déclarer : l'entraînement utilise la réanalyse historique (ERA5, publiée avec environ
5 jours de délai), l'exploitation utiliserait des analyses ou prévisions IFS.

## 4. Variantes

- **(a) Opérationnelle** : uniquement les données disponibles à H le jour t. Seule variante mesurant la performance du système.
- **(b) Oracle** : (a) plus la météo observée de t+1. Borne supérieure, jamais présentée comme performance.

## 5. Sorties

- Principale : PM2.5 moyen de t+1 (µg/m³), par station.
- Secondaire : catégorie AQI EPA (révision 2024), **déduite de la valeur prédite** (`aqi.breakpoints`).

## 6. Décisions ouvertes

| Décision | Étape | Dépend de |
| --- | --- | --- |
| Valeur de H | 2 | Délai de publication mesuré |
| Stations retenues et seuils d'inclusion | 2 | Inventaire et couverture OpenAQ |
| Fuseau réel des horodatages OpenAQ | 2 | Réponse brute de l'API |
| Nombre de lags | 4 | Lag plot, autocorrélation |
| Modèle par station ou modèle commun | 6 | Couverture simultanée des stations |
| Largeur de la fenêtre Tết | 5 | À justifier |
| Taille du bloc de test | 6 | Couverture réelle |

## Journal des modifications

- 2026-10-23 : création.
