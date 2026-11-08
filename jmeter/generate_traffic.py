"""Trafic de démonstration varié pour les dashboards Grafana et Kibana.

Le plan JMeter du sujet envoie toujours le même client (probabilité 0,599, donc
toujours CHURN). Ce script envoie des profils aléatoires tirés comme dans le
générateur de données, plus une petite part de requêtes invalides (422), pour que
les dashboards montrent les deux classes, la distribution des probabilités et des
erreurs client.

    python jmeter/generate_traffic.py --url http://localhost:8000 --requests 2000
"""
import argparse
import json
import random
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor


def random_client(rng: random.Random) -> dict:
    return {
        "age": rng.randint(18, 69),
        "anciennete": rng.randint(1, 119),
        "revenu": rng.randint(150_000, 999_999),
        "nb_reclamations": min(int(rng.expovariate(1 / 2)), 10),
        "montant_mensuel": rng.randint(5_000, 74_999),
        "retards_paiement": min(int(rng.expovariate(1)), 6),
    }


def send(url: str, payload: dict, client_id: str) -> int:
    request = urllib.request.Request(
        f"{url}/predict", data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json", "X-Client-ID": client_id})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--requests", type=int, default=2000)
    parser.add_argument("--invalid-ratio", type=float, default=0.02)
    parser.add_argument("--workers", type=int, default=10)
    args = parser.parse_args()

    rng = random.Random(42)
    jobs = []
    for i in range(args.requests):
        payload = random_client(rng)
        if rng.random() < args.invalid_ratio:
            payload["age"] = rng.choice([5, -1, 150])  # refusé par la validation
        jobs.append((payload, f"agence-{i % 5 + 1}"))

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        codes = list(pool.map(lambda job: send(args.url, *job), jobs))
    summary = {code: codes.count(code) for code in sorted(set(codes))}
    print(f"{len(codes)} requêtes envoyées, codes HTTP : {summary}")


if __name__ == "__main__":
    main()
