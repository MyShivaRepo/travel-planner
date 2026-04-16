# Travel Planner

Application de planification de voyages basée sur l'Inteligence Artificielle (IA).

## Fonctionnalités

L'Utilisateur sélectionne une `Destination` (Pays, Région, Ville) et défini un nombre de `POI` (Point Of Interest) à visiter et un nombre d'`Activité` à réaliser.   
En retour, le Système propose un `Voyage` composé de N `Jours`.   
Chaque `Jour` comprenant :   
- Une liste de `POI(s)` à visiter   
- Une liste d'`Activité(s)` à réaliser   
- Une liste de `Segment(s)` à suivre (Trajet(s) d'un point A à un point B)  
- Un `Hôtel` du soir et un `Restaurant` pour diner  

## Implémentation technique

Il s'agit d'une application web qui est livrée via une `image` Docker.   
Le `container` Docker est accessible sur <a href="http://localhost:9999">http://localhost:9999</a>.    
Les données de l'application sont persistées dans un `volume` Docker (`travel-data`).   
Rq : Les modifications de l'IHM (Interface Homme-Machine) ne doivent pas impacter les données.   

## Stack technique

**Application** : Python 3.12, Streamlit, SQLite, Folium   
**APIs LLM** : Anthropic (Claude), OpenAI (ChatGPT), Google (Gemini)   
**APIs routage** : OpenRouteService, Google Maps Directions   
**Déploiement** : Docker
