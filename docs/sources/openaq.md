# OpenAQ — PM2.5 horaire, plusieurs stations (source principale)

Rôle : fournit la cible et les lags, une série par station retenue.
Emplacement des données : `data/raw/openaq/` (réponses JSON brutes, jamais modifiées).

## Faits vérifiés (doc OpenAQ et spécification `https://api.openaq.org/openapi.json`, consultées le 2026-10-23)

| Point | Valeur |
| --- | --- |
| Base | `https://api.openaq.org/v3` |
| Authentification | Clé obligatoire, en-tête `X-API-Key` ; requête sans clé refusée |
| Limites (gratuit) | 60 requêtes/min et 2 000/h par clé ; dépassement → HTTP 429 ; en-têtes `x-ratelimit-*` |
| Pagination | `limit` (défaut 100, max 1 000) et `page` ; total dans `meta.found` |
| Recherche de stations | `GET /v3/locations` avec soit `coordinates=lat,lon` + `radius` (m, max 25 000), soit `bbox=minLon,minLat,maxLon,maxLat` ; jamais les deux (HTTP 422) ; aussi `iso`, `parameters_id`, `monitor`, `mobile` |
| Objet station | `id`, `name`, `locality`, `timezone`, `provider`, `owner`, `isMobile`, `isMonitor`, `sensors[]` (id, name, parameter), `coordinates`, `licenses`, `datetimeFirst`, `datetimeLast` |
| Capteurs d'une station | `GET /v3/locations/{id}/sensors` |
| PM2.5 horaire | `GET /v3/sensors/{id}/hours`, paramètres `datetime_from`, `datetime_to`, `limit`, `page` |
| Objet horaire | `value`, `parameter` (avec `units`), `period` (`datetimeFrom`, `datetimeTo`), `coverage` (`expectedCount`, `observedCount`, `percentCoverage`…), `flagInfo.hasFlags`, `summary` |
| Dernière mesure | `GET /v3/locations/{id}/latest` |
| Horodatage | ISO 8601 ; chaque datetime est donné en `utc` et en `local` |
| Convention horaire | **Fin d'intervalle exclusive** : l'horodatage 03:00 couvre 02:00–02:59 |

## Conséquences pour le projet

- **Rattachement d'une heure à un jour** : utiliser `period.datetimeFrom.local` (début de l'heure).
  Avec l'heure de fin, l'heure 23:00–23:59 serait comptée le jour suivant.
- **Moniteur de référence ou capteur bas coût** : garder `isMonitor` dans l'inventaire et le rapporter par station.
- **Heures partielles** : garder `coverage.percentCoverage` et `flagInfo.hasFlags` ; la règle d'exclusion se décide à l'étape 3.
- **Volume** : 8 760 h/an, soit 9 pages de 1 000 par capteur et par an. Pour 10 capteurs sur 3 ans, environ 270 requêtes : sous la limite horaire, à condition d'espacer les appels d'au moins 1 s.

## Non vérifié

- Bornes de `datetime_from` / `datetime_to` : inclusives ou non, appliquées au début ou à la fin de période. Parade : chevaucher les fenêtres et dédupliquer sur `period.datetimeFrom.utc`.
- Zone de recherche couvrant Hanoï : `coordinates=21.0285,105.8542` avec `radius=25000` couvre le centre urbain, pas toute la province. **[HYPOTHÈSE NON VÉRIFIÉE]** Les stations utiles se trouvent dans ce rayon ; à confirmer par une seconde requête `iso=VN` filtrée sur la latitude et la longitude.
- Unité : lire `parameter.units` sur une réponse réelle (µg/m³ attendu, non confirmé).

## Procédure

1. `GET /v3/locations?coordinates=21.0285,105.8542&radius=25000&limit=1000` → sauvegarder le JSON.
2. Pour chaque station dont `isMobile` est false : garder les `sensors[]` dont le paramètre est PM2.5.
3. Construire `data/interim/stations_inventory.csv`.
4. Pour chaque capteur : `GET /v3/sensors/{id}/hours` par fenêtres d'un an, `limit=1000`, pages jusqu'à épuisement de `meta.found`.
5. En cas de 429 : attendre la réinitialisation (`x-ratelimit-reset`), puis reprendre. Aucun fichier existant n'est re-téléchargé.
6. Inscrire chaque fichier dans `data/manifest.csv`.

## Extractions

| Date | Fichiers | Notes |
| --- | --- | --- |
| — | — | aucune |
