# Modèle de concepts

## Destination

Le 1er concept clef est le concept de `Destination`.   
Il est caractérisé par :
- un `nom` : le nom de la destination (ex: "Italie", "Toscane", "Rome")
- un `type` : Pays, Région, Ville

Une `Destination` contient plusieurs `POI` (relation 1-N).   
Une `Destination` peut avoir un `Voyage` associé (relation 1-1).

## POI (Point Of Interest)

Le 2nd concept clef est le concept de `POI` (Point Of Interest).
Il est caractérisé par :
- un `rang` : ordre de priorité du site à visiter
- un `nom` : le nom du site
- un `type` : Nature, Architecture, Histoire, ...
- une `description`
- une `latitude`
- une `longitude`

Un `POI` appartient à une seule `Destination` (relation N-1).

## Voyage

Le concept de `Voyage` représente la planification complète pour une `Destination`.   
Il est caractérisé par :
- un `mode de transport` : à pied, en vélo, voiture, train, bus, bateau
- une liste de `Jour` (relation 1-N)

## Jour

Le concept de `Jour` est utilisé dans la planification du voyage.       
Il est caractérisé par :   
- un `numéro` : le numéro du jour dans le voyage (Jour 1, Jour 2, ...).    
- une liste de `POI` à visiter ce jour-là.   
- un `hôtel` : nom, adresse et coordonnées GPS (latitude, longitude) de l'hôtel recommandé pour la nuit.    
- un `restaurant` : nom, adresse et coordonnées GPS (latitude, longitude) du restaurant recommandé pour le dîner.    
