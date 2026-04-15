# Modèle de concepts

Le modèle de concepts s'articule autour de 3 concepts qui incarnent le `besoin` (les exigences du voyage) ...    
... et de 3 concepts qui incarnent la `solution` (la planification du voyage).

Les concepts `besoin` sont :
- La `Destination`
- Le `POI (Point Of Interest)`
- L'`Activité`

Les concepts `solution` sont :
- La `Voyage`
- Le `Jour`
- Le `Segment`

## Les concepts qui incarnent le `besoin`

### Destination

Le 1er concept est le concept de `Destination`.   
Il est caractérisé par :   
- un `nom` : le nom de la destination (ex: "Italie", "Toscane", "Rome")
- un `type` : Pays, Région, Ville

Une `Destination` contient 1 ou plusieurs `POI(s)` associé(s) : relation 1-N.   
Une `Destination` à 1 unique `Voyage` associé : relation 1-1.

### POI (Point Of Interest)

Le 2nd concept est le concept de `POI` (Point Of Interest).
Il est caractérisé par :   
- un `rang` : ordre de priorité du site à visiter
- un `nom` : le nom du site
- un `type` : Nature, Architecture, Histoire, ...
- une `description`
- une `latitude`
- une `longitude`

Un `POI` appartient à une seule `Destination` (relation N-1).

### Activité

Le 3eme concept est le concept d'`Activité`
Il est caractérisé par :   
- un `rang` : ordre de priorité du site à visiter


## Les concepts qui incarnet la solution

### Voyage

Le concept de `Voyage` représente la planification complète pour une `Destination` avec ses `POIs` associés.        
Il est caractérisé par :   
- une liste de `Jours` (numérotés de 1 à N)

### Jour

Le concept de `Jour` est utilisé pour la planification du voyage.   
Un `Jour` contient un nombre fini de `Segment`, qui incarne le trajet d'un `hotel` de départ à un `hotel` d'arrivée en passant par 0, 1 ou plusieurs `POI(s)`   
Il est caractérisé par :   
- un `numéro` : le numéro du jour dans le voyage (Jour 1, Jour 2, ...).    
- une liste de `POIs` à visiter ce jour-là.   
- un `hôtel` : `nom`, `adresse` et `coordonnées GPS` (latitude, longitude) de l'hôtel recommandé pour la nuit, `budget`.      
- un `restaurant` : `nom`, `adresse` et `coordonnées GPS` (latitude, longitude) du restaurant recommandé pour le dîner, `budget`.     
Chaque `Jour` est caratérisé en outre par la somme des `distances` et `durées` de chaque `Segment` et par la somme du `budget` de chaque `Segment`, `hotel` et `restaurant`.

### Segment
Chaque `Segment` à un 1 point de départ et 1 point d'arrivée   
- ces points peuvent être soit des `hotels`, soit des `POIs`   
Chaque `Segment` a un `mode de transport` affecté : pied, vélo, voiture (personelle, location, taxi), bus, metro, train, bateau, avion.  
Chaque `Segment` est caratérisé par :
- Une `distance` (en km)
- Une `durée` (en heure)
- Un `budget` (en Euro)
