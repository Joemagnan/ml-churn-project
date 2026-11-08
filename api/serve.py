"""Lanceur de production : uvicorn multi-workers avec TCP_NODELAY.

Les tests de charge ont montré qu'avec « uvicorn --workers N » (N > 1), chaque
requête prenait au moins ~48 ms, contre ~7 ms avec un seul worker : les connexions
acceptées par les workers n'avaient pas l'option TCP_NODELAY. L'en-tête et le corps
de la réponse partent alors en deux segments TCP, et l'algorithme de Nagle attend
l'accusé de réception (retardé de ~40 ms par le client) avant d'envoyer le second.

Ce lanceur fait la même chose que « uvicorn --workers », mais active TCP_NODELAY
sur la socket d'écoute ; sous Linux, les connexions acceptées en héritent.

    python -m api.serve            # WEB_CONCURRENCY workers (4 par défaut), port 8000
"""
import os
import socket

import uvicorn
from uvicorn.supervisors import Multiprocess


def main() -> None:
    workers = int(os.getenv("WEB_CONCURRENCY", "4"))
    config = uvicorn.Config(
        "api.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        workers=workers,
        proxy_headers=True,
        forwarded_allow_ips="*",
        access_log=False,  # le middleware de l'API écrit déjà un log JSON par requête
    )
    if workers <= 1:
        uvicorn.Server(config).run()
        return
    # Même enchaînement que uvicorn.main.run (uvicorn 0.54) pour workers > 1
    sock = config.bind_socket()
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    Multiprocess(config, sockets=[sock]).run()


if __name__ == "__main__":
    main()
