# Process

Ce fichier décrit le processus suivi par l'utilisateur pour planifier son voyage.   

## 1. Saisie de la destination

L'utilisateur saisit sa `Destination` (nom et type).   
(Ce peut être un pays, une région ou bien une ville)   
L'utilisateur indique également le nombre de `POI` souhaités.   

## 2. Génération des POI

Le système interroge l'API Claude pour déterminer les sites "à ne pas manquer" (`POI`) pour cette destination.   
Le nombre de POI générés correspond au nombre indiqué par l'utilisateur.   
En cas d'erreur de l'API (clé invalide, quota dépassé, timeout), le système affiche un message d'erreur explicite à l'utilisateur.   

## 3. Visualisation des POI

Le système présente les sites (`POI`) dans un tableau triable :   
- Rang du site   
- Nom du site   
- Description   
- Type de site (Nature, Histoire, Architecture, ...)   
- Latitude   
- Longitude   

Ce tableau peut être trié selon chaque colonne en cliquant sur l'en-tête de colonne.   

Le système positionne également ces sites sur une carte géographique (dans l'onglet `Destination`) dont l'échelle est adaptée pour visualiser l'ensemble des POI.   

## 4. Modification des POI

L'utilisateur peut modifier, supprimer ou ajouter des POI avant de valider.   

## 5. Génération du voyage

Lorsque l'utilisateur clique sur le bouton `Générer le voyage`, le système interroge l'API Claude pour générer une proposition de voyage jour par jour.   
Pour chaque jour, le système propose :   
- Quel(s) site(s) (`POI`) visiter   
- Dans quel hôtel séjourner le soir (nom, adresse)   
- Dans quel restaurant (bien noté) se restaurer le soir (nom, adresse)   
