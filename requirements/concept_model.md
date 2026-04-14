# Modèle de concepts

## Destination

Le 1er concept clef est le concept de `Destination`.   
Il est caractérisé par :   
- un `nom` : le nom de la destination (ex: "Italie", "Toscane", "Rome")
- un `type` : Pays, Région, Ville

Une `Destination` contient 1 ou plusieurs `POI(s)` (relation 1-N).   
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

Le concept de `Voyage` représente la planification complète pour une `Destination` avec ses `POIs` associés.        
Il est caractérisé par :   
- une liste de `Segments`  
- chaque `Segment` à un 1 point de départ et 1 point d'arrivée   
- Ces points peuvent être soit des `hotels`, soit des `POIs`   
- Chaque `Segment` a un `mode de transport` : pied, vélo, voiture (personelle, location, taxi), bus, metro , train, bateau, avion.  


## Jour

Le concept de `Jour` est utilisé dans la planification du voyage.       
Il est caractérisé par :   
- un `numéro` : le numéro du jour dans le voyage (Jour 1, Jour 2, ...).    
- une liste de `POIs` à visiter ce jour-là.   
- un `hôtel` : nom, adresse et coordonnées GPS (latitude, longitude) de l'hôtel recommandé pour la nuit.    
- un `restaurant` : nom, adresse et coordonnées GPS (latitude, longitude) du restaurant recommandé pour le dîner.    
