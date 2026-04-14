# Design de l'IHM

Les différents `onglets` suivants sont disposés de manière horizontale.

## Onglet `Settings`

Permet de configurer les API utilisées par l'application.

### LLM Principal

Permet de saisir l'`API Key` d'un fournisseur de LLM (Large Language Model).
Sélectionner un fournisseur (Anthropic/Claude, OpenAI/ChatGPT, Google/Gemini, ...).
Entrer la clef.
Un bouton `Enregistrer` sauvegarde la clé en base de données.
Un bouton `Tester` permet de vérifier que la clé est valide.
Un message de confirmation ou d'erreur est affiché à l'utilisateur.

### LLM de Secours (fallback)

Permet de configurer un LLM de secours utilisé automatiquement si le LLM principal est indisponible (surcharge, timeout, erreur réseau).
Sélection d'un fournisseur parmi la même liste, ou `Aucun`.
Entrer la clef.
Boutons `Enregistrer` et `Tester` identiques au LLM principal.

### API de Routage (OpenRouteService)

Clé API optionnelle d'OpenRouteService pour calculer les vrais tracés routiers sur la carte du voyage.
Si la clé n'est pas fournie, la carte affiche des lignes droites entre les points.
Boutons `Enregistrer` et `Tester`.

## Onglet `Where to Go`

Permet de saisir une nouvelle `Destination` :
- Champ `Nom` : le nom de la destination
- Champ `Type` : Pays, Région ou Ville (liste déroulante)
- Champ `Nombre de POI` : le nombre de sites à découvrir
- Un `bouton` nommé `Rechercher` lance la génération des POI via l'API du LLM

Les différentes `Destinations` déjà enregistrées sont présentées dans un tableau avec les colonnes :
- Nom
- Type
- Nombre de POI

Dans la dernière colonne du tableau :
- un `bouton` nommé `Visualiser` permet d'accéder à la liste des `POI` pour cette `Destination` (bascule vers l'onglet `Destination`)
- un `bouton` nommé `Supprimer` permet de supprimer cette `Destination` et tous ses `POI` associés

## Onglet `Destination`

Permet de visualiser l'ensemble des `POI` pour la destination sélectionnée.
En haut de l'onglet :
- Le nom de la destination et son type
- Une liste déroulante `Mode de transport` (à pied, vélo, voiture, train, bateau, transport public, mixte)
- Un `bouton` nommé `Générer le voyage` qui lance la planification jour par jour via l'API du LLM et bascule vers l'onglet `Travel`

Cet onglet contient deux sous-onglets :

### Sous-onglet `Tableau`

La visualisation se fait dans un tableau triable avec les colonnes (Cf concept_model.md) :
- Rang
- Nom
- Type
- Description
- Latitude
- Longitude

Le tableau est trié en cliquant sur l'en-tête de chaque colonne (tri croissant/décroissant).

Dans la dernière colonne du tableau :
- un `bouton` nommé `Modifier` permet de modifier les attributs de ce `POI`
- un `bouton` nommé `Supprimer` permet de supprimer ce `POI`

En bas du tableau, un `bouton` nommé `Ajouter un POI` invoque le LLM pour proposer un nouveau POI qui n'est pas déjà dans la liste existante.

### Sous-onglet `Carte`

Une carte géographique affiche l'ensemble des `POI` de la destination.
L'échelle de la carte est adaptée automatiquement pour visualiser tous les `POI`.
Chaque `POI` est représenté par un marqueur rouge circulaire contenant son numéro de rang. Le marqueur est cliquable et affiche une popup avec le nom, le type et la description.
La carte occupe toute la hauteur disponible du navigateur.

## Onglet `Travel`

Permet de visualiser le voyage jour par jour.
En haut de l'onglet : nom de la destination, nombre de jours, mode de transport.
Cet onglet contient deux sous-onglets :

### Sous-onglet `Tableau`

Affichage jour par jour (expanders). Pour chaque `Jour` :
- Les `POI` à visiter (rang, nom, type, description)
- L'hôtel (nom, adresse)
- Le restaurant (nom, adresse)

### Sous-onglet `Carte`

Affichage sur une carte géographique du parcours complet de chaque journée :
- Pour chaque jour : hôtel du matin → POIs (dans l'ordre) → restaurant → hôtel du soir
- Une couleur différente par jour pour distinguer les trajets
- Si la clé OpenRouteService est configurée et le mode de transport est compatible (à pied, vélo, voiture) : le vrai tracé routier est affiché, avec la distance et la durée réelles dans les tooltips
- Sinon : des lignes droites pointillées sont affichées

Les marqueurs sur la carte :
- Les `hôtels` : marqueurs bleus avec l'icône "lit"
- Les `restaurants` : marqueurs verts avec l'icône "fourchette"
- Les `POIs` : marqueurs rouges circulaires avec le numéro de rang à l'intérieur

La distance totale et la durée cumulée sont affichées au-dessus de la carte (si routage réel disponible).
La carte occupe toute la hauteur disponible du navigateur.
