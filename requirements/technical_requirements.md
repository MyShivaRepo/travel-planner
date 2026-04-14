# Exigences techniques

## Déploiement

L'application est développée dans une `image` Docker.
Le `container` Docker est accessible à l'adresse http://localhost:9999.
Les données de l'application (destinations, POI, voyages, segments, clés API) doivent être rendues pérennes via un `volume` Docker.
Les modifications de l'interface utilisateur ne doivent pas impacter les données de l'application.

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

## API de routage

L'application peut utiliser OpenRouteService (ORS) pour calculer les vrais tracés routiers sur les cartes du voyage.

Modes supportés par ORS (routage réel) :
- à pied
- en vélo
- voiture personnelle, voiture de location, taxi (tous mappés sur `driving-car`)
- bus (mappé sur `driving-car` car ORS n'a pas de profil bus)

Modes non supportés par ORS (affichage en lignes droites) :
- métro
- train
- bateau
- avion

Le routage est effectué segment par segment : si un segment échoue, seul celui-ci est affiché en ligne droite, les autres restent en tracé réel.
Le paramètre `radiuses: [-1]` est utilisé pour permettre à ORS de chercher le point routable le plus proche sans limite de rayon (utile pour les POI en montagne, forêt, etc. qui ne sont pas sur une route).

## Persistance

Les données suivantes sont persistées en base SQLite :
- Destinations et POI
- Voyages (1 destination peut avoir plusieurs voyages, chacun avec date de création)
- Jours de voyage (incluant hôtel avec GPS, restaurant avec GPS)
- Segments (avec points de départ/arrivée, coordonnées GPS, et mode de transport par segment)
- Clés API (LLM principal, LLM de secours, OpenRouteService)
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
