# Travel Planner

Application de planification de voyages basée sur l'IA (Claude d'Anthropic).

## Fonctionnalités

- **Settings** : configuration et test de la clé API Claude
- **Where to Go** : saisir une destination (pays, région, ville) et un nombre de POI souhaités, génération automatique des sites incontournables
- **Destination** : tableau CRUD des POI (ajouter, modifier, supprimer) et carte interactive
- **Travel** : planification jour par jour avec hôtels et restaurants recommandés

## Lancement via Docker

```bash
cd docker
docker compose up --build
```

L'application est accessible sur **http://localhost:9999**.

Les données sont persistées dans un volume Docker (`travel-data`).

## Stack technique

- Python 3.12
- Streamlit
- Claude API (Anthropic)
- Folium (cartes interactives)
- SQLite (persistance)
- Docker
