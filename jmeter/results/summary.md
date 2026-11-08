# Résultats des tests de charge JMeter

POST /predict, ramp-up 10 s, 10 boucles par utilisateur.

## 1 avant optimisation

| Utilisateurs | Requêtes | Moyenne (ms) | Médiane (ms) | p90 (ms) | p95 (ms) | p99 (ms) | Max (ms) | Débit (req/s) | Erreurs (%) | Erreurs |
|---|---|---|---|---|---|---|---|---|---|---|
| 100 | 1000 | 2541.4 | 2399 | 3791 | 4053 | 4337 | 4887 | 29.5 | 0.0 | – |
| 500 | 5000 | 13298.0 | 12922 | 20357 | 21253 | 21782 | 22178 | 36.0 | 0.94 | HttpHostConnectException × 47 |
| 1000 | 10000 | 22756.7 | 22742 | 30014 | 30017 | 30024 | 30617 | 41.3 | 27.6 | HttpHostConnectException × 404, SocketTimeoutException × 2356 |

## 2 apres optimisation

| Utilisateurs | Requêtes | Moyenne (ms) | Médiane (ms) | p90 (ms) | p95 (ms) | p99 (ms) | Max (ms) | Débit (req/s) | Erreurs (%) | Erreurs |
|---|---|---|---|---|---|---|---|---|---|---|
| 100 | 1000 | 4.0 | 4 | 6 | 6 | 7 | 57 | 101.7 | 0.0 | – |
| 500 | 5000 | 5.8 | 5 | 8 | 11 | 24 | 73 | 510.7 | 0.0 | – |
| 1000 | 10000 | 17.3 | 11 | 40 | 52 | 87 | 185 | 1017.8 | 0.0 | – |

## 3 stress 1000 utilisateurs x50

| Utilisateurs | Requêtes | Moyenne (ms) | Médiane (ms) | p90 (ms) | p95 (ms) | p99 (ms) | Max (ms) | Débit (req/s) | Erreurs (%) | Erreurs |
|---|---|---|---|---|---|---|---|---|---|---|
| 1000 | 50000 | 637.7 | 687 | 866 | 897 | 946 | 1035 | 1149.6 | 0.0 | – |
