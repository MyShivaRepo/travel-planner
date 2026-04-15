# Process

Ce fichier décrit le processus suivi par l'utilisateur pour planifier son voyage.

## 1. Saisie de la destination

L'Utilisateur saisit sa `Destination` (nom et type) dans l'onglet `Where to Go`.
(Ce peut être un pays, une région ou bien une ville)
L'Utilisateur indique également le nombre de `POI(s)` et le nombre d'`Activité(s)` souhaités.

## 2. Génération des POIs

Le Système interroge l'API du LLM pour déterminer les sites "à ne pas manquer" (`POIs`) pour cette `Destination`.       
Le nombre de `POI(s)` générés correspond au nombre indiqué par l'utilisateur.   

## 3. Génération des Activités

Le Système interroge l'API du LLM pour déterminer les `Activités` caractéristiques de cette `Destination`.    
Le nombre d'`Activité(s)` générés correspond au nombre indiqué par l'utilisateur.   
Le Système propose une localisation précise pour réaliser chaque `Activité`.   

## 4. Visualisation et modification des POIs et des Activités

Dans l'onglet `Destination`, sous-onglet "POIs", le Système présente les sites (`POI`) dans un tableau triable :
- Rang du site
- Nom du site
- Type de site (Nature, Histoire, Architecture, ...)
- Description
- Latitude
- Longitude

L'Utilisateur peut :
- Modifier manuellement un `POI` existant
- Supprimer un `POI`
- Ajouter un nouveau `POI` via le LLM (qui propose un `POI` supplémentaire non déjà présent dans la liste)

Dans l'onglet `Destination`, sous-onglet "Activités", le Système présente les `Activités` dans un tableau triable :
- Rang de l'activité 
- Nom de l'activité
- Type d'activité (Sport, Culture, Cuisine, ...)
- Description
- Latitude
- Longitude
- Fournisseur (lien hypertexte)

L'Utilisateur peut :
- Modifier manuellement une `Activité` existante
- Supprimer une `Activité`
- Ajouter une nouvelle `Activité` via le LLM (qui propose une `Activité` supplémentaire non déjà présent dans la liste)
- Un champ "Commentaire" permet à l'Utilisateur de préciser au Système l'`Activité` qu'il souhaite.

Le Système positionne par ailleurs (sous-onglet "carte") les `POIs` et les `Activités` sur une carte géographique dont l'échelle est adaptée.

## 5. Génération d'un voyage

Lorsque l'Utilisateur clique sur le bouton `Générer le voyage`, le système interroge l'API du LLM pour générer une proposition de voyage jour par jour.

Pour chaque `Jour`, le LLM propose :
- Quel(s) site(s) (`POI(s)`) visiter et quelle(s) `Activité(s)` à réaliser (regroupés par proximité géographique)
- Dans quel hôtel séjourner le soir (nom, adresse, coordonnées GPS)
- Dans quel restaurant (bien noté) se restaurer le soir (nom, adresse, coordonnées GPS)
- La liste ordonnée des `Segments` de la journée (hôtel du matin → `POI(s)` et/ou `Activité(s)` → hôtel du soir)
(L'hôtel du matin et l'hôtel du soir peuvent être les mêmes)
- Pour chaque segment, le mode de transport le plus pertinent (parmi : à pied, en vélo, voiture personnelle, voiture de location, taxi, bus, métro, train, bateau, avion)

## 6. Visualisation et ajustement du voyage

Dans l'onglet `Travel`, l'utilisateur consulte le `Voyage` généré dans deux sous-onglets :
- `Tableau` : description détaillée de chaque journée avec : Liste des `POI(s)`, liste des `Activités`, liste des `Segments`, Logistique du soir (Restaurant et Hôtel)
- `Carte` : tracé géographique du parcours complet de chaque journée, avec le vrai routage si la clé OpenRouteService est configurée et le mode de transport compatible
