# Architecture & Déploiement

L'application Travel Planner est livrée sous forme de container Docker.
Pour la déployer sur une machine hôte, suivre les 3 étapes ci-dessous :

1. **Installer les composants prérequis** sur la machine hôte
2. **Déployer le container** Docker
3. **Renseigner les clés API** dans l'onglet `Settings` de l'application

---

## 1. Composants à installer

| Nom | Type | Description | Récupération | Installation | Paramétrage | Vérification |
|---|---|---|---|---|---|---|
| **Git** | Système de gestion de versions | Permet de cloner le dépôt source de l'application | Télécharger depuis [git-scm.com/downloads](https://git-scm.com/downloads) | Lancer l'installeur correspondant à votre OS (Windows / macOS / Linux) et accepter les options par défaut | Configurer l'identité : `git config --global user.name "Prénom Nom"` et `git config --global user.email "email@exemple.com"` | Ouvrir un terminal et exécuter `git --version` — un numéro de version doit s'afficher |
| **Docker Desktop** | Plateforme de conteneurisation | Permet de construire et d'exécuter le container Docker de l'application | Télécharger depuis [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/) | Lancer l'installeur et redémarrer si demandé. Sur Windows, activer WSL2 si proposé | Démarrer Docker Desktop. Aucune configuration spécifique à l'application n'est requise | Ouvrir un terminal et exécuter `docker --version` puis `docker compose version` — les deux doivent renvoyer un numéro de version |
| **Navigateur web** | Client HTTP | Permet d'accéder à l'interface Streamlit de l'application | Pré-installé sur la plupart des OS (Chrome, Firefox, Safari, Edge) | N/A | N/A | Ouvrir une URL quelconque |

---

## 2. Container à déployer

### Installation de Docker Desktop

Voir la section 1 « Composants à installer ».
Avant de poursuivre, vérifier que Docker Desktop est démarré : l'icône baleine doit être présente dans la barre d'état système, et la commande `docker ps` doit s'exécuter sans erreur.

### Récupération de l'image

L'image Docker est construite localement à partir du `Dockerfile` fourni dans le dépôt. Cloner le dépôt et se positionner dans le sous-répertoire `docker/` :

```bash
git clone https://github.com/MyShivaRepo/travel-planner.git
cd travel-planner/docker
```

### Démarrage du container

Depuis le répertoire `docker/`, lancer :

```bash
docker compose up --build -d
```

- `--build` reconstruit l'image à partir du `Dockerfile` (nécessaire au premier lancement et après chaque mise à jour du code source)
- `-d` (detached) lance le container en arrière-plan

Le volume Docker `travel-data` est créé automatiquement et monté sur `/data` dans le container. Il contient la base SQLite `travel_planner.db` qui persiste les destinations, POI, activités, voyages, segments **et les clés API** entre les redémarrages.

Pour arrêter le container : `docker compose down` (le volume `travel-data` et donc les données sont conservés).

### Accès à l'application

Ouvrir un navigateur à l'adresse : **http://localhost:9999**

Au premier lancement, aucune clé n'est configurée : se rendre dans l'onglet `Settings` pour les saisir (cf. section 3).

---

## 3. API Keys à renseigner

L'application requiert au minimum **une clé LLM** (Anthropic, OpenAI ou Google). Les autres clés sont facultatives mais enrichissent l'expérience (vrais tracés routiers et transports publics sur les cartes).

Toutes les clés sont stockées dans la base SQLite du volume `travel-data` ; elles sont préservées entre les redémarrages du container et ne sont jamais transmises à un service autre que le fournisseur de la clé.

### 3.1 Clé LLM (obligatoire — au moins une)

#### Anthropic / Claude

| | |
|---|---|
| **Où la récupérer** | Créer un compte sur [console.anthropic.com](https://console.anthropic.com) puis générer une clé dans `Settings → API Keys`. Format : `sk-ant-...` |
| **Où la saisir** | Onglet `Settings` → section `LLM Principal` → sélectionner « Anthropic / Claude » dans la liste déroulante → coller la clé dans `API Key` → cliquer `Enregistrer` |
| **Comment tester** | Cliquer sur le bouton `Tester` à droite de `Enregistrer`. La zone de message affiche « Clé API valide. » si l'authentification réussit, sinon le motif d'erreur (clé invalide, quota dépassé, timeout, erreur réseau) |

#### OpenAI / ChatGPT

| | |
|---|---|
| **Où la récupérer** | Créer un compte sur [platform.openai.com](https://platform.openai.com) puis générer une clé dans `API Keys`. Format : `sk-...` |
| **Où la saisir** | Onglet `Settings` → section `LLM Principal` (ou `LLM de Secours`) → sélectionner « OpenAI / ChatGPT » → coller la clé → `Enregistrer` |
| **Comment tester** | Cliquer sur `Tester` |

#### Google / Gemini

| | |
|---|---|
| **Où la récupérer** | Créer un projet sur [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) puis générer une clé API. Format : `AIza...` |
| **Où la saisir** | Onglet `Settings` → section `LLM Principal` (ou `LLM de Secours`) → sélectionner « Google / Gemini » → coller la clé → `Enregistrer` |
| **Comment tester** | Cliquer sur `Tester` |

> **LLM de Secours (fallback) — facultatif** : configurer un second fournisseur LLM (différent du principal) dans la section `LLM de Secours` pour basculer automatiquement dessus en cas d'indisponibilité du LLM principal (surcharge, timeout, erreur réseau).

### 3.2 Clé OpenRouteService (facultative)

Permet d'afficher les vrais tracés routiers sur la carte du voyage pour les segments à pied, en vélo, en voiture, en taxi et en bus. Sans cette clé, ces segments sont représentés par des lignes droites pointillées.

| | |
|---|---|
| **Où la récupérer** | Créer un compte gratuit sur [openrouteservice.org/dev/#/signup](https://openrouteservice.org/dev/#/signup) puis copier la clé depuis le `Dashboard`. Quota gratuit : 2 000 requêtes/jour |
| **Où la saisir** | Onglet `Settings` → section `API de routage (OpenRouteService)` → coller la clé → `Enregistrer` |
| **Comment tester** | Cliquer sur `Tester`. L'application tente une route Paris → Versailles à pied. Le message « Clé ORS valide. » confirme la validité |

### 3.3 Clé Google Maps Directions (facultative)

Permet d'afficher les vrais tracés et horaires des transports publics (métro, train) sur la carte du voyage. Sans cette clé, les segments métro/train basculent vers un tracé routier approximatif (si ORS est configurée) ou une ligne droite pointillée.

| | |
|---|---|
| **Où la récupérer** | Sur [console.cloud.google.com](https://console.cloud.google.com), créer un projet, activer l'API « Directions », puis générer une clé dans `APIs & Services → Credentials`. Format : `AIza...` |
| **Où la saisir** | Onglet `Settings` → section `API Google Maps Directions` → coller la clé → `Enregistrer` |
| **Comment tester** | Cliquer sur `Tester`. L'application tente une recherche Paris → Lyon en train. Le message confirme la validité |
