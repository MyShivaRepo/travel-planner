# Exigences techniques

## Déploiement

L'application est développée dans une `image` Docker.   
Le `container` Docker est accessible à l'adresse http://localhost:9999.   
Les données de l'application (destinations, POI, voyages, segments, clés API) doivent être rendues pérennes via un `volume` Docker.   
Les modifications de l'interface utilisateur ne doivent pas impacter les données de l'application.   

## Configuration des API

Dans l'onglet `Settings`, l'utilisateur configure au moins une clé API d'un fournisseur de LLM (Anthropic, OpenAI, Google).
Optionnellement, il peut configurer :
- Un LLM de secours (fallback) utilisé automatiquement en cas d'échec du LLM principal.
- Une clé OpenRouteService pour afficher les vrais tracés routiers sur les cartes du voyage.
- Une clé Google Maps Directions pour afficher les vrais tracés des transports publics (métro, train, bus).

Toutes les clés API sont persistées en base de données afin d'être préservées entre les redémarrages du container.

## Migration de schéma de base de données

Toute évolution du schéma de la base de données doit être non destructive :
les migrations doivent utiliser `ALTER TABLE ADD COLUMN` ou la recréation sélective de table (copy → drop → rename) pour préserver les données existantes.

## Fournisseurs LLM supportés

L'application doit supporter plusieurs fournisseurs de LLM :
- Anthropic (Claude)
- OpenAI (ChatGPT)
- Google (Gemini)

L'utilisateur peut configurer :
- Un LLM principal (obligatoire)
- Un LLM de secours (optionnel), utilisé automatiquement en cas d'indisponibilité du LLM principal

## Gestion des erreurs API LLM

L'application doit gérer les erreurs liées aux API LLM :
- Clé API invalide ou manquante
- Quota dépassé
- Timeout de la requête
- Erreur réseau
- Surcharge (erreur 529 / rate limit)

En cas d'erreur :
- Si un LLM de secours est configuré, l'application tente automatiquement de basculer sur celui-ci
- Sinon, un message d'erreur explicite est affiché à l'utilisateur

## APIs de routage

### OpenRouteService (ORS)

Modes supportés (routage réel) :
- à pied
- en vélo
- voiture personnelle, voiture de location, taxi (tous mappés sur `driving-car`)
- bus (mappé sur `driving-car` car ORS n'a pas de profil bus)

Le paramètre `radiuses: [-1]` est utilisé pour permettre à ORS de chercher le point routable le plus proche sans limite de rayon (utile pour les POI en montagne, forêt, etc. qui ne sont pas sur une route).

### Google Maps Directions

Modes supportés (routage transit avec horaires réels) :
- métro
- train

Décodage local du polyline encodé retourné par l'API.

Le module implémente également le mode `bus` au niveau du mapping Google Directions, mais ce mode n'est pas activé dans le dispatch de routage : conformément au design UI, les segments `bus` sont routés via OpenRouteService (profil `driving-car`). Le mapping GMaps pour `bus` est réservé à une éventuelle évolution future.

### Great-circle (calcul local, sans API)

Mode supporté :
- avion

Calcul basé sur la formule de Haversine pour la distance et interpolation sphérique pour le tracé. La durée est estimée à partir d'une vitesse de croisière moyenne de 800 km/h.

### Dispatch et fallback

Le routage est effectué segment par segment : si un segment échoue, seul celui-ci est affiché en ligne droite, les autres restent en tracé réel.

## Persistance

Les données suivantes sont persistées en base SQLite :
- Destinations
- POI (rattachés à une Destination)
- Activités (rattachées à une Destination)
- Voyages (1 par Destination)
- Jours de voyage
- Hôtels (rattachés à un Jour : nom, adresse, coordonnées GPS, budget)
- Restaurants (rattachés à un Jour : nom, adresse, coordonnées GPS, budget)
- Segments (points de départ/arrivée avec coordonnées GPS, mode de transport, distance, durée, budget)
- Clés API (LLM principal, LLM de secours, OpenRouteService, Google Maps)
- Préférence du LLM principal et du LLM de secours

## Modes de transport par segment

Chaque segment a un unique mode de transport parmi :
- à pied
- en vélo
- voiture personnelle
- voiture de location
- taxi
- bus
- métro
- train
- bateau
- avion

Le mode de transport est initialement proposé par le LLM puis peut être modifié par l'utilisateur dans l'onglet `Travel` (sous-onglet `Tableau`).

## Coordonnées GPS

Toutes les coordonnées GPS (`latitude`, `longitude`) utilisées dans l'application sont exprimées en WGS84 en degrés décimaux.

Le couple `(0, 0)` — dit "Null Island" — est conventionnellement considéré comme une coordonnée **absente** : un POI, une Activité, un Hôtel, un Restaurant ou une extrémité de segment dont les coordonnées sont `(0, 0)` n'est ni affiché sur les cartes, ni utilisé dans les calculs de routage, ni pris en compte dans le tri.

Cette convention implique par construction :
- que les rangs (`rang`) des `POI` et `Activité` sont toujours ≥ 1 (jamais 0),
- que les latitudes et longitudes des entités valides sont toujours non-nulles et non-zéro,
- et que les tris sur les colonnes numériques (rang, latitude, longitude) ne mélangent jamais types numériques et valeurs "vides".
