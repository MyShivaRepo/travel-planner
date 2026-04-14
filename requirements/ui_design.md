# Design de l'IHM

Les différents `onglets` suivants sont disposés de manière horizontale.    

## Onglet `Settings`

Permet de saisir l'`API Key` d'un fournisseur de LLM (Large Language Model).
Sélectionner un fournisseur (Anthropic/Claude, OpenAI/ChatGPT, Google/Gemini, ...).   
Entrer la clef.   
Un bouton `Tester` permet de vérifier que la clé est valide.   
Un message de confirmation ou d'erreur est affiché à l'utilisateur.   

## Onglet `Where to Go`

Permet de saisir une nouvelle `Destination` :   
- Champ `Nom` : le nom de la destination   
- Champ `Type` : Pays, Région ou Ville (liste déroulante)   
- Champ `Nombre de POI` : le nombre de sites à découvrir   
- Un `bouton` nommé `Rechercher` lance la génération des POI via l'API Claude   

Les différentes `Destinations` déjà enregistrées sont présentées dans un tableau avec les colonnes :   
- Nom   
- Type   

Dans la dernière colonne du tableau :   
- un `bouton` nommé `Modifier` permet d'accéder à la liste des `POI` pour cette `Destination` (bascule vers l'onglet `Destination`)   
- un `bouton` nommé `Supprimer` permet de supprimer cette `Destination` et tous ses `POI` associés   

## Onglet `Destination`

Permet de visualiser l'ensemble des `POI` pour la destination sélectionnée.   
Cet onglet contient deux sous-onglets :   

### Sous-onglet `Tableau`

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

En bas du tableau, un `bouton` nommé `Ajouter` permet d'ajouter un nouveau `POI`.   

### Sous-onglet `Carte`

Une carte géographique affiche l'ensemble des `POI` de la destination.   
L'échelle de la carte est adaptée automatiquement pour visualiser tous les `POI`.   
Chaque `POI` est représenté par un marqueur cliquable affichant son nom et sa description.   

### Génération du voyage

Un `bouton` nommé `Générer le voyage` permet de lancer la planification jour par jour via l'API Claude.   
Ce bouton bascule ensuite vers l'onglet `Travel`.   

## Onglet `Travel`

Permet de visualiser le voyage `Jour` par `Jour`.   
Pour chaque `Jour` :   
- le système affiche les `POI` à visiter   
- propose un hôtel dans lequel séjourner (nom, adresse)   
- propose un restaurant dans lequel dîner (nom, adresse)   
