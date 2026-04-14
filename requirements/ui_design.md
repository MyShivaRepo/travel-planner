# Design de l'IHM

Un `onglet` nommé `Settings` permet de saisir l'API Key de Claude.   

Un `onglet` nommé `Where to Go` permet de saisir la  `Destination` et le nombre de `POI` à visiter. 
Les différentes `Destinations` sont présentées dans un tableau avec autant de colonnes que d'attributs (Cf concept_model.md).   
Dans la dernière colonne du tableau :
 - un `bouton` nommé `Modifier` permet d'accéder à la liste des `POI` pour cette `Destination`.   
 - un `bouton` nommé `Supprimer` permet de supprimer cette `Destination`.   

Un `onglet` nommé `Destination` permet de visualiser l'ensemble des `POI` pour cette destination.   
La visualisation se fait dans un tableau avec autant de colonnes que d'attributs (Cf concept_model.md).   
Dans la dernière colonne du tableau : 
 - un `bouton` nommé `Supprimer` permet de supprimer ce `POI`.
En bas du tableau `bouton` nommé `Ajouter` permet d'ajoyter un nouveau `POI`.

Un `onglet` nommé `Travel` permet de visualiser le vogage `Jour` par `Jour`
Pour chaque `Jour` : 
  - le système affiche les `POI` à visiter
  - propose un hotel dans lequel séjourner
  - propose un restaurant dans lequel diner
