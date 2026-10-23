# Kaggle - Hanoi Air Quality (PM2.5) + Weather Data 2024-2026 (contrôle)

Rôle : contrôle croisé uniquement. La station d'origine n'est pas identifiée, donc la série ne peut pas être rattachée à une zone.
Emplacement : `data/external/kaggle/` (archive d'origine + fichiers extraits, non modifiés).

## Identité

- Page : https://www.kaggle.com/datasets/diabolicfox/hanoi-air-quality-pm2-5-weather-data-2024-2026
- Identifiant : `diabolicfox/hanoi-air-quality-pm2-5-weather-data-2024-2026`
- Licence : CC0 (selon son README)
- Fichier principal : `hanoi_aqi_ml_ready_fixed.csv`, 14 451 lignes × 34 colonnes, horaire, du 2024-02-14 09:00 au 2026-01-26 07:00

## Récupération

- **Option A, manuelle** : bouton « Download » de la page (compte Kaggle requis), archive copiée dans `data/external/kaggle/`.
  L'archive téléchargée le 2026-10-06 peut être réutilisée.
- **Option B, CLI** : `pip install kaggle`, identifiants dans `~/.kaggle/kaggle.json` (droits 600), puis :
  `kaggle datasets download -d diabolicfox/hanoi-air-quality-pm2-5-weather-data-2024-2026 -p data/external/kaggle --unzip`
  Le comportement exact de `-p` pour les téléchargements de datasets n'est pas confirmé par la source consultée.
- Dans les deux cas : SHA-256 de l'archive inscrit dans `data/manifest.csv`. Un dataset Kaggle peut être mis à jour par son auteur, et l'empreinte prouve quelle version a été utilisée.

## Défauts connus (audit du 2026-10-06)

- 15,4 % des heures absentes, sous forme de lignes manquantes (aucun NaN).
- Lags et moyennes glissantes calculés par lignes, faux après chaque trou.
- README contredit par le fichier (moyenne, nombre de colonnes, unité du vent).
- Colonne `source` mélangée (OpenAQ, « 5-year+OpenAQ », « 5-year »).
- Fuseau annoncé UTC, mais courbe de température compatible avec l'heure locale.

## Extractions

| Date | Fichier | SHA-256 |
| --- | --- | --- |
| 2026-10-06 | archive Kaggle (téléversée) | à calculer à la copie dans `data/external/kaggle/` |
