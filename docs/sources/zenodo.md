# Zenodo — Air Quality Dataset for Hanoi (comparaison)

Rôle : comparaison uniquement, jamais la cible. C'est une sortie du modèle CAMS (via Open-Meteo), pas une mesure.
Emplacement : `data/external/zenodo/`.

## Identité

- Page : https://zenodo.org/records/18673906
- Licence : CC0-1.0 (selon ses métadonnées)
- Contenu : `air_quality_historical.csv`, 1 298 lignes × 12 colonnes, journalier, du 2022-08-01 au 2026-02-18, aux coordonnées 21.0245, 105.84117

## Récupération

- **Option A, manuelle** : téléchargement depuis la page (environ 54 kB). L'archive téléchargée le 2026-10-06 peut être réutilisée.
- **Option B, API** : `GET https://zenodo.org/api/records/18673906` (documentée par Zenodo).
  La structure de la liste des fichiers dans la réponse n'est pas documentée sur la page consultée : lire la réponse avant d'écrire un script.
  Limite invité : 60 requêtes/min, 2 000/h.
- SHA-256 inscrit dans `data/manifest.csv`.

## Constat (audit du 2026-10-06)

Sur 590 jours communs avec le Kaggle : CAMS supérieur de 12,8 µg/m³ en moyenne (46,1 contre 33,3), corrélation 0,61, MAE 16,5.

## Extractions

| Date | Fichier | SHA-256 |
| --- | --- | --- |
| 2026-10-06 | archive Zenodo (téléversée) | à calculer à la copie dans `data/external/zenodo/` |
