# Open-Meteo Historical Weather API — météo horaire

Rôle : variables météo, aux coordonnées de chaque station retenue.
Emplacement des données : `data/raw/openmeteo/` (CSV ou JSON bruts).

## Faits vérifiés (doc Open-Meteo, consultée le 2026-10-23)

| Point | Valeur |
| --- | --- |
| Endpoint | `https://archive-api.open-meteo.com/v1/archive` |
| Clé | Aucune clé dans les exemples |
| Modèles | ERA5 (0,25°, depuis 1940), ERA5-Land (0,1°, depuis 1950), ECMWF IFS (9 km, depuis 2017) |
| Délai | ERA5 et ERA5-Land : quotidien, environ 5 jours de retard |
| Plusieurs points | Coordonnées séparées par des virgules ; en CSV, colonne `location_id` ajoutée |
| `timezone` | Fixe les horodatages et les limites des journées ; heure d'été ignorée |

## Conséquences pour le projet

- Une seule requête suffit pour toutes les stations : `latitude=a,b,c&longitude=x,y,z`.
- `timezone=Asia/Bangkok` (UTC+7, pas d'heure d'été) : aucune ambiguïté de fuseau.
- Mailles de 9 à 28 km : plusieurs stations de Hanoï peuvent tomber dans la même maille. À constater en comparant les séries, pas à supposer.
- Le délai de 5 jours rend l'archive inutilisable en exploitation. Pour une prévision émise le jour t, il faut l'API de prévision (modèle IFS, mise à jour sans délai). Écart réanalyse/prévision à déclarer dans le rapport.

## Non vérifié

- Le paramètre d'unité du vent (`wind_speed_unit=ms`) sur l'archive.
- La convention d'horodatage de `precipitation` : cumul de l'heure précédente ou suivante.
- Les limites d'usage gratuit.

## Requête type

```
https://archive-api.open-meteo.com/v1/archive
  ?latitude=<lat1>,<lat2>,...&longitude=<lon1>,<lon2>,...
  &start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
  &hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation,surface_pressure
  &timezone=Asia%2FBangkok&format=csv
```

Les coordonnées sont celles de `data/interim/stations_inventory.csv` ; les dates couvrent la période PM2.5 la plus longue.

## Extractions

| Date | Fichiers | Notes |
| --- | --- | --- |
| — | — | aucune |
