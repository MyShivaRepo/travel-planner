# Design de l'IHM

Les différents `onglets` suivants sont disposés de manière horizontale.

## Onglet `Settings`

Permet de configurer les API utilisées par l'application.

### LLM Principal

Permet de configurer un fournisseur principal de LLM (Large Language Model).

Un champ `Fournisseur` permet de sélectionner un fournisseur (Anthropic/Claude, OpenAI/ChatGPT, Google/Gemini, ...).
Un champ `API Key` permet de saisir la clef.
Un bouton `Enregistrer` permet la sauvegarde de la clef en base de données.
Un bouton `Tester` permet de vérifier que la clef est valide.
Une zone de messages permet de confirmer la connection ou d'afficher un message d'erreur à l'utilisateur.

### LLM de Secours (fallback)

Permet de configurer un LLM de secours utilisé automatiquement si le LLM principal est indisponible (surcharge, timeout, erreur réseau).

Champs, boutons et zone de messages identiques au LLM principal.

### API de Routage (OpenRouteService)

Clé API optionnelle d'OpenRouteService pour calculer les vrais tracés routiers sur la carte du voyage pour les modes de transport compatibles (à pied, vélo, voiture, taxi, bus).
Si la clé n'est pas fournie, la carte affiche des lignes droites entre les points.
Boutons `Enregistrer` et `Tester`.

### API Google Maps Directions

Clé API optionnelle de Google Maps Directions pour calculer les vrais tracés des transports publics (métro, train, bus) sur la carte du voyage, avec horaires et durées réels.
Si la clé n'est pas fournie, la carte affiche des lignes droites pour les segments en métro ou en train.
Boutons `Enregistrer` et `Tester`.

## Onglet `Where to Go`

Permet de saisir une nouvelle `Destination` :
- Champ `Nom` : le nom de la destination
- Champ `Type` : Pays, Région ou Ville (liste déroulante)
- Curseur `Nombre de POIs` : le nombre de sites à découvrir
- Curseur `Nombre d'activités` : le nombre d'activité à réaliser
- Un `bouton` nommé `Rechercher` lance la génération des `POI(s)` et des `Activité(s)` via l'API du LLM

Les différentes `Destinations` déjà enregistrées sont présentées dans un tableau avec les colonnes :
- Nom
- Type
- Nombre de POIs
- Nombre d'activités

Dans la dernière colonne du tableau :
- un `bouton` nommé `Visualiser` permet d'accéder à l'onglet `Destination`)
- un `bouton` nommé `Supprimer` permet de supprimer cette `Destination` (et tous ses `POI(s)` et `Activité(s)` associés)

## Onglet `Destination`

Permet de visualiser l'ensemble des `POI(s)` et `Activité(s)`des pour la `Destination` sélectionnée.
En haut de l'onglet :
- Le nom de la `Destination`, son type, le nombre de POI et le nomre d'activités
- Un `bouton` nommé `Générer le voyage` qui lance la planification jour par jour via l'API du LLM et bascule vers l'onglet `Travel`.

Cet onglet contient trois sous-onglets :

### Sous-onglet `POIs`

La visualisation se fait dans un tableau triable avec les colonnes (Cf concept_model.md) :
- Rang
- Nom
- Type
- Description
- Latitude
- Longitude

Dans la dernière colonne du tableau :
- un `bouton` nommé `Modifier` permet de modifier les attributs de ce `POI`
- un `bouton` nommé `Supprimer` permet de supprimer ce `POI`

En bas du tableau, un `bouton` nommé `Ajouter un POI` invoque le LLM pour proposer un nouveau POI qui n'est pas déjà dans la liste existante.

### Sous-onglet `Activités`
La visualisation se fait dans un tableau triable avec les colonnes (Cf concept_model.md) :
- Rang
- Nom
- Type
- Description
- Latitude
- Longitude

Dans la dernière colonne du tableau :
- un `bouton` nommé `Modifier` permet de modifier les attributs de cette `Activité`
- un `bouton` nommé `Supprimer` permet de supprimer cette `Activité`

En bas du tableau, un `bouton` nommé `Ajouter une Activité` invoque le LLM pour proposer une nouvelle Activité qui n'est pas déjà dans la liste existante.


### Sous-onglet `Carte`

Une carte géographique affiche l'ensemble des `POI(s)` et des `Activité(s)` de la destination.
L'échelle de la carte est adaptée automatiquement pour visualiser tous les éléments.
Chaque `POI` est représenté par un marqueur rouge circulaire contenant son numéro de rang. Le marqueur est cliquable et affiche une popup avec le rang, le nom et le type.
Chaque `Activité` est représenté par un marqueur orange circulaire contenant son numéro de rang. Le marqueur est cliquable et affiche une popup avec le rang, le nom et le type
La carte occupe toute la hauteur disponible du navigateur.

## Onglet `Travel`

Permet de visualiser le **dernier voyage généré** pour la destination sélectionnée.

En haut de l'onglet : nom de la destination, son type, et le nombre de jours du voyage.

Cet onglet contient deux sous-onglets :

### Sous-onglet `Tableau`

Affichage jour par jour (via des `expanders` dépliés par défaut).
Pour chaque `Jour`.
- Affichage sur la même ligne : n° du jour, distance, durée, budget
- Affichage en dessous de trois sections qui s'affichent dans l'ordre suivant :

**1. Liste des sites à visiter** *(classés par leur Rang)*
- Liste des POI du jour au format : `<Nom> (rang <N>)`

**2. Liste des segments**   
Affichage dans un tableau
- `<From> > <To>`
- `mode de transport`
- `distance`
- `durée`
- `budget`

**3. Logistique du soir**
- **Hôtel** : nom et adresse de l'hôtel recommandé pour la nuit
- **Restaurant** : nom et adresse du restaurant recommandé pour le dîner

### Sous-onglet `Carte`

Affichage sur une carte géographique du parcours complet de chaque journée. Chaque segment est tracé avec la couleur correspondant à son jour, selon le mode de transport et les clés API configurées :

- **à pied, en vélo, voiture (personnelle/location), taxi, bus** : si la clé OpenRouteService est configurée → vrai tracé routier ; sinon → ligne droite pointillée
- **métro, train** : si la clé Google Maps est configurée → vrai tracé transit avec horaires ; sinon fallback sur ORS (tracé routier approximatif) ; sinon ligne droite pointillée
- **avion** : tracé en grand cercle (great-circle) calculé localement, avec distance et durée estimées à partir d'une vitesse moyenne de vol
- **bateau** : ligne droite pointillée (pas de routage maritime)

Les tooltips au survol d'un segment affichent : `From "<label_départ>" to "<label_arrivée>" : <mode> (distance, durée)` où les labels sont `Jn` pour un hôtel du jour N, `POIx` pour un POI de rang x, et `Resto Jn` pour un restaurant du jour N.

Les marqueurs sur la carte :
- Les `hôtels` : marqueurs bleus avec l'icône "lit"
- Les `restaurants` : marqueurs verts avec l'icône "fourchette"
- Les `POIs` : marqueurs rouges circulaires avec le numéro de rang à l'intérieur

La distance totale et la durée cumulée (pour les segments routables) sont affichées au-dessus de la carte.
La carte occupe toute la hauteur disponible du navigateur.
