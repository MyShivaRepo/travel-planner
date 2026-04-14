# Process

Ce fichier décrit le processus suivi par l'utilisateur pour planifier son voyage.

## 1. Configuration des API

Dans l'onglet `Settings`, l'utilisateur configure au moins une clé API d'un fournisseur de LLM (Anthropic, OpenAI, Google).
Optionnellement, il peut configurer un LLM de secours (fallback) utilisé automatiquement en cas d'échec du LLM principal.
Optionnellement, il peut configurer une clé OpenRouteService pour afficher les vrais tracés routiers sur les cartes du voyage.

## 2. Saisie de la destination

L'utilisateur saisit sa `Destination` (nom et type) dans l'onglet `Where to Go`.
(Ce peut être un pays, une région ou bien une ville)
L'utilisateur indique également le nombre de `POI` souhaités.

## 3. Génération des POI

Le système interroge l'API du LLM pour déterminer les sites "à ne pas manquer" (`POI`) pour cette destination.
Le nombre de POI générés correspond au nombre indiqué par l'utilisateur.
En cas d'erreur de l'API (clé invalide, quota dépassé, timeout, surcharge), le système bascule automatiquement sur le LLM de secours si configuré, sinon affiche un message d'erreur explicite.

## 4. Visualisation et modification des POI

Dans l'onglet `Destination`, le système présente les sites (`POI`) dans un tableau triable :
- Rang du site
- Nom du site
- Type de site (Nature, Histoire, Architecture, ...)
- Description
- Latitude
- Longitude

Ce tableau peut être trié selon chaque colonne en cliquant sur l'en-tête de colonne.

Le système positionne également ces sites sur une carte géographique (sous-onglet `Carte`) dont l'échelle est adaptée pour visualiser l'ensemble des POI.

L'utilisateur peut :
- Modifier manuellement un POI existant
- Supprimer un POI
- Ajouter un nouveau POI via le LLM (qui propose un site supplémentaire non déjà présent dans la liste)

## 5. Sélection du mode de transport

Avant de générer le voyage, l'utilisateur choisit le `mode de transport` qu'il compte utiliser :
à pied, vélo, voiture, train, bateau, transport public, ou mixte.
Ce mode influence la manière dont le LLM regroupera les POI par jour (rayon de déplacement compatible avec le mode choisi).

## 6. Génération du voyage

Lorsque l'utilisateur clique sur le bouton `Générer le voyage`, le système interroge l'API du LLM pour générer une proposition de voyage jour par jour, en tenant compte du mode de transport.
Pour chaque jour, le système propose :
- Quel(s) site(s) (`POI`) visiter (regroupés par proximité géographique compatible avec le mode de transport)
- Dans quel hôtel séjourner le soir (nom, adresse, coordonnées GPS)
- Dans quel restaurant (bien noté) se restaurer le soir (nom, adresse, coordonnées GPS)

## 7. Visualisation du voyage

Dans l'onglet `Travel`, l'utilisateur visualise le voyage jour par jour dans deux sous-onglets :
- `Tableau` : description détaillée de chaque journée
- `Carte` : tracé géographique du parcours complet de chaque journée, avec le vrai routage si la clé OpenRouteService est configurée et le mode de transport compatible
