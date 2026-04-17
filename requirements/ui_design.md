# Design de l'IHM

Les différents `onglets` suivants sont disposés de manière horizontale.

## Onglet `Settings`

Permet de configurer les API utilisées par l'application.

### LLM Principal

Permet de configurer un fournisseur principal de LLM (Large Language Model).

<table>
    <thead>
        <tr>
            <th>Type</th>
            <th>Label</th>
            <th>Usage</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>champ</td>
            <td>Fournisseur</td>
            <td>permet de sélectionner un fournisseur (Anthropic/Claude, OpenAI/ChatGPT, Google/Gemini, ...).</td>
        </tr>
        <tr>
            <td>champ</td>
            <td>API Key</td>
            <td>permet de saisir la clef de l'API</td>
        </tr>
        <tr>
            <td>bouton</td>
            <td>Enregister</td>
            <td>permet la sauvegarde de la clef en base de données</td>
        </tr>
        <tr>
            <td>bouton</td>
            <td>Tester</td>
            <td>permet de vérifier que la clef est valide</td>
        </tr>
        <tr>
            <td>zone</td>
            <td>Message</td>
            <td>permet de confirmer la connection ou d'afficher un message d'erreur à l'utilisateur</td>
        </tr>
    </tbody>
</table>


### LLM de Secours (fallback)

Permet de configurer un LLM de secours utilisé automatiquement si le LLM principal est indisponible (surcharge, timeout, erreur réseau).

Champs, boutons et zone de messages identiques au LLM principal.

### API de Routage (OpenRouteService)

Clé API optionnelle d'OpenRouteService pour calculer les vrais tracés routiers sur la carte du voyage pour les modes de transport compatibles (à pied, vélo, voiture, taxi, bus).
Si la clé n'est pas fournie, la carte affiche des lignes droites entre les points.

<table>
    <thead>
        <tr>
            <th>Type</th>
            <th>Label</th>
            <th>Usage</th>
        </tr>
    </thead>
        <tr>
            <td>champ</td>
            <td>API Key</td>
            <td>permet de saisir la clef de l'API</td>
        </tr>
        <tr>
            <td>bouton</td>
            <td>Enregister</td>
            <td>permet la sauvegarde de la clef en base de données</td>
        </tr>
        <tr>
            <td>bouton</td>
            <td>Tester</td>
            <td>permet de vérifier que la clef est valide</td>
        </tr>
        <tr>
            <td>zone</td>
            <td>Message</td>
            <td>permet de confirmer la connection ou d'afficher un message d'erreur à l'utilisateur</td>
        </tr>
    </tbody>
</table>

### API Google Maps Directions

Clé API optionnelle de Google Maps Directions pour calculer les vrais tracés des transports publics (métro, train, bus) sur la carte du voyage, avec horaires et durées réels.
Si la clé n'est pas fournie, la carte affiche des lignes droites pour les segments en métro ou en train.

<table>
    <thead>
        <tr>
            <th>Type</th>
            <th>Label</th>
            <th>Usage</th>
        </tr>
    </thead>
        <tr>
            <td>champ</td>
            <td>API Key</td>
            <td>permet de saisir la clef de l'API</td>
        </tr>
        <tr>
            <td>bouton</td>
            <td>Enregister</td>
            <td>permet la sauvegarde de la clef en base de données</td>
        </tr>
        <tr>
            <td>bouton</td>
            <td>Tester</td>
            <td>permet de vérifier que la clef est valide</td>
        </tr>
        <tr>
            <td>zone</td>
            <td>Message</td>
            <td>permet de confirmer la connection ou d'afficher un message d'erreur à l'utilisateur</td>
        </tr>
    </tbody>
</table>

## Onglet `Where to Go`

Permet de saisir une nouvelle `Destination` :

<table>
    <thead>
        <tr>
            <th>Type</th>
            <th>Label</th>
            <th>Usage</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>champ</td>
            <td>Nom</td>
            <td>le nom de la destination</td>
        </tr>
        <tr>
            <td>liste</td>
            <td>Type</td>
            <td>le type de destination : Pays, Région ou Ville</td>
        </tr>
        <tr>
            <td>curseur</td>
            <td>Nb de POI(s)</td>
            <td>le nombre de sites à découvrir</td>
        </tr>
        <tr>
            <td>curseur</td>
            <td>Nb d'activité(s)</td>
            <td>le nombre d'activités à réaliser</td>
        </tr>
        <tr>
            <td>bouton</td>
            <td>Rechercher</td>
            <td>lance la génération des `POI(s)` et des `Activité(s)` via l'API du LLM</td>
        </tr>
    </tbody>
</table>


Les différentes `Destinations` déjà enregistrées sont présentées dans un tableau avec les colonnes :

<table>
    <thead>
        <tr>
            <th>champ</th>
            <th>champ</th>
            <th>champ</th>
            <th>champ</th>
            <th>bouton</th>
            <th>bouton</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>Nom</td>
            <td>Type</td>
            <td>Nb de POI(s)</td>
            <td>Nb d'activité(s)</td>
            <td>Visualiser</td>
            <td>Supprimer</td>
        </tr>
    </tbody>
</table>


## Onglet `Destination`

Permet de visualiser l'ensemble des `POI(s)` et `Activité(s)` pour la `Destination` sélectionnée.
En haut de l'onglet :
- Le nom de la `Destination`, son type, le nombre de POI(s) et le nombre d'activité(s)
- Un `bouton` nommé `Générer le voyage` qui lance la planification jour par jour via l'API du LLM et bascule vers l'onglet `Travel`.

Cet onglet contient trois sous-onglets :

### Sous-onglet `POIs`

La visualisation se fait dans un tableau triable avec les colonnes (Cf concept_model.md) :

<table>
    <thead>
        <tr>
            <th>champ</th>
            <th>champ</th>
            <th>champ</th>
            <th>champ</th>
            <th>champ</th>
            <th>champ</th>
            <th>bouton</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>Rang</td>
            <td>Nom</td>
            <td>Type</td>
            <td>Description</td>
            <td>Latitude</td>
            <td>Longitude</td>
            <td>Supprimer</td>
        </tr>
    </tbody>
</table>

En bas du tableau, un `bouton` nommé `Ajouter un POI` invoque le LLM pour proposer un nouveau POI qui n'est pas déjà dans la liste existante.   
Après l'ajout le Systeme renumérote les POI(s) par ordre de priorité.   

### Sous-onglet `Activités`
La visualisation se fait dans un tableau triable avec les colonnes (Cf concept_model.md) :

<table>
    <thead>
        <tr>
            <th>champ</th>
            <th>champ</th>
            <th>champ</th>
            <th>champ</th>
            <th>champ</th>
            <th>champ</th>
            <th>champ</th>
            <th>bouton</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>Rang</td>
            <td>Nom</td>
            <td>Type</td>
            <td>Description</td>
            <td>Latitude</td>
            <td>Longitude</td>
            <td>Fournisseur</td>
            <td>Supprimer</td>
        </tr>
    </tbody>
</table>

En bas du tableau, un `bouton` nommé `Ajouter une Activité` invoque le LLM pour proposer une nouvelle Activité qui n'est pas déjà dans la liste existante.    
Après l'ajout le Systeme renumérote les Activité(s) par ordre de priorité.   

### Sous-onglet `Carte`

Une carte géographique affiche l'ensemble des `POI(s)` et des `Activité(s)` de la destination.   
L'échelle de la carte est adaptée automatiquement pour visualiser tous les éléments.   
Chaque `POI` est représenté par un marqueur `rouge` `circulaire` contenant son `numéro de rang`. Le marqueur est cliquable et affiche une popup avec le `rang`, le `nom` et le `type`.   
Chaque `Activité` est représenté par un marqueur `orange` `circulaire` contenant son `numéro de rang`. Le marqueur est cliquable et affiche une popup avec le `rang`, le `nom` et le `type`.   
La carte occupe toute la hauteur disponible du navigateur.   

## Onglet `Travel`

Permet de visualiser le **dernier voyage généré** pour la destination sélectionnée.

En haut de l'onglet : nom de la destination, son type, et le nombre de jours du voyage.

Cet onglet contient deux sous-onglets :

### Sous-onglet `Tableau`

Affichage jour par jour (via des `expanders` dépliés par défaut).
Pour chaque `Jour` :
- Affichage sur la même ligne : n° du jour, distance, durée, budget
- Affichage en dessous de quatre sections qui s'affichent dans l'ordre suivant :

**1. Liste des POIs à visiter** *(classés par leur Rang)*
- Liste des `POI(s)` du jour au format : `<Nom> (rang <N>)`

**2. Liste des Activités à réaliser** *(classées par leur Rang)*
- Liste des `Activité(s)` du jour au format : `<Nom> (rang <N>)`

**3. Liste des segments**   
Affichage dans un tableau
- `<From> > <To>`
- `mode de transport`
- `distance`
- `durée`
- `budget`

**4. Logistique du soir**
- **Hôtel** : nom et adresse de l'hôtel recommandé pour la nuit
- **Restaurant** : nom et adresse du restaurant recommandé pour le dîner

### Sous-onglet `Carte`

Affichage sur une carte géographique du parcours complet de chaque journée. Chaque segment est tracé avec la couleur correspondant à son jour, selon le mode de transport et les clés API configurées :

- **à pied, en vélo, voiture (personnelle/location), taxi, bus** : si la clé OpenRouteService est configurée → vrai tracé routier ; sinon → ligne droite pointillée
- **métro, train** : si la clé Google Maps est configurée → vrai tracé transit avec horaires ; sinon fallback sur ORS (tracé routier approximatif) ; sinon ligne droite pointillée
- **avion** : tracé en grand cercle (great-circle) calculé localement, avec distance et durée estimées à partir d'une vitesse moyenne de vol
- **bateau** : ligne droite pointillée (pas de routage maritime)

Les tooltips au survol d'un segment affichent : `From "<label_départ>" to "<label_arrivée>" : <mode> (distance, durée)` où les labels sont `Jn` pour un hôtel du jour N, `POIx` pour un POI de rang x, `Actx` pour une Activité de rang x, et `Resto Jn` pour un restaurant du jour N.

Les marqueurs sur la carte :
- Les `hôtels` : marqueurs bleus avec l'icône "lit"
- Les `restaurants` : marqueurs verts avec l'icône "fourchette"
- Les `POIs` : marqueurs rouges circulaires avec le numéro de rang à l'intérieur
- Les `Activités` : marqueurs orange circulaires avec le numéro de rang à l'intérieur
  
La distance totale et la durée cumulée (pour les segments routables) sont affichées au-dessus de la carte.
La carte occupe toute la hauteur disponible du navigateur.
