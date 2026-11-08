import os

import pytest

# Les tests ne doivent pas écrire dans logs/api.log (fichier lu par Logstash).
os.environ.setdefault("LOG_FILE", "")

PAYLOAD = {
    "age": 35,
    "anciennete": 5,
    "revenu": 450000,
    "nb_reclamations": 2,
    "montant_mensuel": 25000,
    "retards_paiement": 2,
}


@pytest.fixture
def payload():
    """Client d'exemple du sujet (copie modifiable dans chaque test)."""
    return dict(PAYLOAD)
