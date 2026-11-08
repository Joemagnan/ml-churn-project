# Préparation de la soutenance – réponses aux questions (PARTIE 28)

Projet fil rouge MLOps – prédiction du churn télécom – Joe MAGNAN – MDSIA 2

## Data Science

**Pourquoi ce problème est-il pertinent ?**
Acquérir un nouvel abonné coûte bien plus cher que d'en garder un. Repérer à
l'avance les clients à risque permet à l'opérateur de cibler ses actions de
rétention (offre, appel du service client) sur les bons clients, au lieu d'arroser
toute la base. Le modèle sert à prioriser, pas à décider à la place d'un humain.

**Quelle est la variable cible ?**
`churn` : 1 si le client résilie, 0 sinon. Les six autres colonnes (âge, ancienneté,
revenu, réclamations, montant mensuel, retards de paiement) sont les variables explicatives.

**Pourquoi s'agit-il d'une classification ?**
La cible est discrète et binaire (résilie / ne résilie pas) : on prédit une classe et
une probabilité d'appartenance à cette classe, pas une valeur continue. C'est de la
classification binaire supervisée, puisque l'on dispose d'exemples étiquetés.

**Comment avez-vous séparé train et test ?**
`train_test_split` à 80 % / 20 % (1 600 / 400 clients), **stratifié** sur `churn` pour
garder 43 % de churn dans les deux jeux, avec `random_state=42` pour la
reproductibilité. Le choix du modèle se fait par validation croisée stratifiée à 5
plis **sur le jeu d'entraînement uniquement** ; le jeu de test ne sert qu'une fois,
à l'évaluation finale. Le scaler est dans le Pipeline : il est ajusté sur chaque pli
d'entraînement, ce qui évite toute fuite d'information du test vers l'entraînement.

**Pourquoi avoir choisi Random Forest ?**
Le sujet l'impose, mais je l'ai mis en concurrence avec les deux autres modèles et
les mesures donnent l'avantage à la **régression logistique** (F1 CV 0,523 contre 0,488
pour le Random Forest, ROC-AUC CV 0,655 contre 0,622). C'est logique : le générateur
de données du sujet est une fonction logistique des variables, exactement l'hypothèse
de ce modèle. Elle est aussi plus rapide, plus légère (7 coefficients contre 200
arbres) et interprétable. Le Random Forest reste disponible avec
`python src/train.py --model random_forest`. Il serait le bon choix si les relations
étaient non linéaires ou faisaient intervenir des interactions entre variables.

## API

**Pourquoi transformer le modèle en API ?**
Un fichier `.pkl` n'est utilisable que dans un script Python. Une API HTTP le rend
accessible à n'importe quelle application (CRM, interface web, batch) quel que soit
son langage, découple le modèle de ses consommateurs (on peut changer de modèle sans
les toucher), et permet de le déployer, le tester, le monitorer et le faire monter en
charge comme n'importe quel service.

**Pourquoi FastAPI ?**
Validation automatique des entrées avec Pydantic (erreur 422 claire en cas de champ
manquant ou de valeur négative), documentation Swagger générée automatiquement,
bonnes performances (ASGI), typage Python, client de test intégré, et un écosystème
qui inclut l'export Prometheus en une ligne.

**Quelle différence entre /health et /predict ?**
`/health` est un endpoint technique et léger : il dit seulement si le service est
vivant et si le modèle est chargé (200 `UP` / 503 `DOWN`). Il est appelé en continu
par le healthcheck Docker, docker-compose et un éventuel répartiteur de charge.
`/predict` est l'endpoint métier : il reçoit les données d'un client, exécute le
modèle et renvoie la prédiction. Il est plus coûteux et ne doit pas servir de sonde.

## Tests

**Pourquoi Pytest ?**
C'est le standard Python : syntaxe simple (`assert`), fixtures réutilisables,
paramétrage (`@pytest.mark.parametrize` pour tester 6 champs manquants en une
fonction), marqueurs (`e2e`, `integration`), couverture avec pytest-cov, rapport
JUnit lisible par la CI.

**Pourquoi Selenium ?**
Pytest teste l'API, mais pas ce que voit l'utilisateur. Selenium pilote un vrai
navigateur : il ouvre l'interface, saisit les données, clique sur « Prédire » et
vérifie le résultat affiché. Il vérifie ainsi que l'interface, le JavaScript, le
proxy et l'API fonctionnent ensemble.

**Quelle différence entre test unitaire, intégration et E2E ?**
- **Unitaire** : une fonction isolée, sans dépendance externe, très rapide
  (ex. `test_generated_values_are_valid`, `test_formatter_produces_json_with_extra_fields`).
- **Intégration** : plusieurs composants ensemble (ex. `train.py` qui lit un CSV,
  entraîne et écrit les artefacts ; dans la CI, l'API conteneurisée lue par Prometheus).
- **E2E (de bout en bout)** : tout le système du point de vue de l'utilisateur, via
  l'interface (tests Selenium). Le plus réaliste, mais aussi le plus lent et le plus fragile.

C'est la pyramide des tests : beaucoup de tests unitaires, moins d'intégration, peu d'E2E.

## Performance

**Pourquoi JMeter ?**
Outil open source de référence pour les tests de charge : il simule des centaines
d'utilisateurs simultanés, mesure temps de réponse, percentiles, débit et erreurs,
s'utilise en mode graphique pour concevoir le plan et en ligne de commande pour
l'exécuter (CI, serveur), et génère un rapport HTML.

**Quelle différence entre charge, stress et endurance ?**
- **Charge** : le trafic attendu en production (ex. 100 utilisateurs) ; on vérifie que
  les objectifs de temps de réponse sont tenus.
- **Stress** : on dépasse volontairement la capacité (500, 1000 utilisateurs) pour
  trouver le point de rupture et voir comment le service se dégrade (erreurs,
  délais d'attente, reprise après le pic).
- **Endurance** (*soak test*) : une charge normale pendant longtemps (plusieurs heures)
  pour détecter les fuites mémoire, la saturation des disques par les logs, la dégradation lente.
  Plan prêt dans le projet : `jmeter/endurance_test_plan.jmx` (100 utilisateurs, 1 h par défaut).

Dans ce projet : la série 100 / 500 / 1000 utilisateurs (10 boucles) est un test de
charge croissante ; « 1000 utilisateurs × 50 boucles » est un test de stress (saturation
à environ 1 150 req/s, sans erreur, p95 de 897 ms).

**Que signifie le 95e percentile du temps de réponse ?**
95 % des requêtes ont été servies en moins de cette durée ; les 5 % restantes ont été
plus lentes. Il décrit l'expérience des utilisateurs les moins bien servis, alors que
la moyenne masque les pics : une moyenne de 50 ms peut cacher un p95 de 2 s. Les
objectifs de service (SLO) s'expriment donc en percentiles (ex. « p95 < 300 ms »).

## DevOps

**Pourquoi Git ?**
Historique complet et traçable de chaque modification (qui, quand, pourquoi), retour
arrière possible, travail à plusieurs sans s'écraser, revue de code par Pull Request,
et déclencheur de toute la chaîne CI/CD.

**Pourquoi utiliser des branches ?**
Isoler le travail en cours : `main` contient ce qui est livrable, `develop` ce qui est
intégré et testé, et chaque fonctionnalité a sa branche `feature/...`. Une
fonctionnalité inachevée ne casse pas la version stable ; elle est fusionnée par Pull
Request après le passage de la CI.

**Pourquoi Docker ?**
L'image embarque le code, le modèle, Python et les bibliothèques aux versions
exactes : le service se comporte de la même façon sur mon poste, en CI et sur le
serveur (fini le « ça marche chez moi »). Le démarrage est rapide, l'isolation
garantie, et docker-compose décrit toute l'architecture (8 services) dans un seul fichier.

**Pourquoi la CI/CD ?**
Chaque push déclenche automatiquement les mêmes vérifications : données
reproductibles, garde-fou sur la qualité du modèle, tests, tests E2E, build Docker,
tests d'intégration. Une régression est détectée en quelques minutes, avant la
fusion, et non en production. La partie CD publie automatiquement une image
versionnée, prête à être déployée.

## Observabilité

**Quelle différence entre logs et métriques ?**
- **Logs** : un événement détaillé et individuel (« la requête abc a prédit CHURN à
  0,60 avec le modèle 1.0.0 en 2 ms »). On s'en sert pour **comprendre** un incident
  précis et pour l'audit.
- **Métriques** : des valeurs numériques agrégées dans le temps (requêtes/s, p95,
  taux d'erreur). On s'en sert pour **détecter** un problème, suivre les tendances et
  déclencher des alertes. Elles coûtent peu à stocker.

On détecte avec les métriques, puis on diagnostique avec les logs (grâce au `request_id`).

**Pourquoi ELK ?**
Centraliser les logs de tous les conteneurs au même endroit, les rendre
consultables (recherche plein texte, filtres `level : "ERROR"`, `model_version : "1.0.0"`)
et construire des visualisations. Logstash collecte et transforme les logs, Elasticsearch
les indexe, Kibana permet de les explorer.

**Pourquoi Prometheus ?**
Base de données de séries temporelles conçue pour les métriques : il interroge
`/metrics` toutes les 5 s (modèle *pull*), stocke efficacement, offre un langage de
requête (PromQL) pour calculer débit, percentiles et taux d'erreur, et évalue des
règles d'alerte.

**Pourquoi Grafana ?**
Pour visualiser les métriques de Prometheus dans des dashboards lisibles en temps
réel, partageables et versionnés (le dashboard du projet est un fichier JSON
provisionné automatiquement).

**Que surveilleriez-vous sur une API ML en production ?**
- **Technique** : disponibilité (`up`, `/health`), débit, temps de réponse p95/p99,
  taux d'erreurs 4xx/5xx, CPU, mémoire, saturation.
- **Modèle** : volume de prédictions, répartition CHURN / NO_CHURN, distribution des
  probabilités (déjà dans Grafana), dérive des données d'entrée (âge, ancienneté…
  comparés au jeu d'entraînement), version servie.
- **Métier** (avec délai) : précision réelle une fois le churn observé, taux de
  rétention des clients contactés.

## MLOps

**Comment versionner le modèle ?**
Chaque entraînement produit une version sémantique (`--version 1.1.0`) archivée dans
`models/registry/v1.1.0/` avec `metadata.json` : date, métriques, variables, seuil,
empreinte SHA-256 du dataset, versions de Python et scikit-learn. La version est
exposée par `/model/info`, renvoyée dans chaque réponse, présente dans chaque log et
dans la métrique `churn_model_info`. L'image Docker est taguée avec cette version.
En entreprise, on utiliserait un registre de modèles (MLflow Model Registry) et DVC
pour versionner les données.

**Que faire si un nouveau modèle est moins performant ?**
Ne pas le promouvoir. C'est automatisé dans `train.py` : le nouveau modèle est
archivé, mais il ne remplace `models/model.pkl` que si son F1 n'est pas inférieur à
celui du modèle en production (tolérance 0,01). En dessous du seuil absolu
(`--min-f1`), le script échoue et la CI devient rouge. On analyse ensuite les causes
(données, hyperparamètres) avant de réentraîner.

**Comment détecter une dégradation du modèle ?**
- À court terme, sans les vraies réponses : surveiller la **dérive** des entrées et
  des sorties. Le dashboard suit la probabilité moyenne prédite et une alerte
  Prometheus se déclenche si elle sort de [0,20 ; 0,65] alors que le taux
  d'entraînement est de 43 %. On peut aussi comparer les distributions des variables
  (test de Kolmogorov-Smirnov, PSI, Evidently).
- À moyen terme, avec les vraies réponses : recalculer précision, rappel et F1 sur les
  clients dont on connaît désormais le comportement, et alerter sous un seuil.

**Comment gérer plusieurs versions du modèle ?**
Chaque version a son dossier dans le registre et son tag d'image Docker. On peut
servir deux versions en parallèle (deux conteneurs derrière un répartiteur) pour un
déploiement **canary** (5 % du trafic sur la nouvelle version) ou un **A/B test** ;
le champ `model_version` dans les logs et les métriques permet de comparer les deux
dans Kibana et Grafana. L'API lit le chemin du modèle dans la variable `MODEL_PATH`.

**Comment revenir à une ancienne version ?**
Plusieurs niveaux, du plus rapide au plus complet :
1. Redéployer l'image Docker précédente (`ghcr.io/joemagnan/ml-churn-api:1.0.0`).
2. Restaurer le modèle archivé : copier `models/registry/v1.0.0/*` dans `models/`
   (ou pointer `MODEL_PATH` dessus) et redémarrer l'API.
3. Redéployer un tag Git : `BRANCH=v1.0.0 bash deploy/deploy.sh`.
Dans tous les cas, `/model/info` permet de vérifier immédiatement la version servie.
