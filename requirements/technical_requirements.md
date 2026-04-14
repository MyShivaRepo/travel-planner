# Exigences techniques

L'application est développée dans une `image` Docker.   
Le `container` Docker est accessible à l'adresse http://localhost:9999.   
Les données de l'application doivent être rendues pérennes via un `volume` Docker.   
(Les modifications de l'interface utilisateur ne doivent pas impacter les données de l'application.)   

## Gestion des erreurs API

L'application doit gérer les erreurs liées à l'API Claude :   
- Clé API invalide ou manquante   
- Quota dépassé   
- Timeout de la requête   
- Erreur réseau   

Dans chaque cas, un message d'erreur explicite est affiché à l'utilisateur.   
