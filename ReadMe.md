# TravelPlanner – POI Finder

Application de préparation de voyages basée sur l'IA (Claude d'Anthropic).

## Fonctionnalités

- Saisir une destination (pays, région, ville) et un nombre de POI souhaités
- Génération automatique des sites incontournables avec coordonnées GPS
- Affichage d'un tableau exportable en CSV
- Carte interactive avec les POI positionnés

## Lancement via Docker

```bash
docker compose up --build
```

L'application est accessible sur **http://localhost:8501**.

## Stack technique

- Python 3.12
- Streamlit
- Claude API (Anthropic)
- Folium
- Docker
