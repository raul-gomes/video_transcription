"""Aguarda o PostgreSQL e o Redis ficarem prontos antes de iniciar os serviços.

Usa apenas bibliotecas já instaladas no projeto (psycopg2), evitando depender
do cliente de linha de comando `psql` que não está presente na imagem.
"""
import os
import socket
import sys
import time

import psycopg2


def wait_for_db(max_attempts: int = 60) -> None:
    url = os.environ.get("DATABASE_URL")
    for _ in range(max_attempts):
        try:
            if url:
                conn = psycopg2.connect(url, connect_timeout=3)
            else:
                conn = psycopg2.connect(
                    dbname=os.environ.get("POSTGRES_DB", "video_transcription"),
                    user=os.environ.get("POSTGRES_USER", "postgres"),
                    password=os.environ.get("POSTGRES_PASSWORD", "postgres"),
                    host=os.environ.get("DB_HOST", "db"),
                    port=os.environ.get("DB_PORT", "5432"),
                    connect_timeout=3,
                )
            conn.close()
            return
        except Exception:
            print("    Banco ainda nao esta pronto. Tentando novamente em 2s...", flush=True)
            time.sleep(2)
    print("Banco de dados nao ficou pronto a tempo.", flush=True)
    sys.exit(1)


def wait_for_redis(max_attempts: int = 60) -> None:
    host = os.environ.get("REDIS_HOST", "redis")
    port = int(os.environ.get("REDIS_PORT", "6379"))
    for _ in range(max_attempts):
        try:
            with socket.create_connection((host, port), timeout=3):
                return
        except OSError:
            print("    Redis ainda nao esta pronto. Tentando novamente em 2s...", flush=True)
            time.sleep(2)
    print("Redis nao ficou pronto a tempo.", flush=True)
    sys.exit(1)


if __name__ == "__main__":
    print(">>> Aguardando banco de dados...", flush=True)
    wait_for_db()
    print(">>> Banco de dados esta pronto!", flush=True)
    print(">>> Aguardando Redis...", flush=True)
    wait_for_redis()
    print(">>> Redis esta pronto!", flush=True)
