# Comandos

## Rodar com Docker (caminho principal)
| Comando | O que faz |
| --- | --- |
| `cp .env.example .env` | Cria o arquivo de configuração (opcional; tudo tem padrão). |
| `docker compose up -d --build` | Sobe web, worker e Redis. App em http://127.0.0.1:8000 |
| `PORT=8010 docker compose up -d` | Mesmo, em outra porta (quando a 8000 já está em uso). |
| `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build` | Mesmo, com o worker usando a GPU NVIDIA (precisa do NVIDIA Container Toolkit). Testado numa RTX 2060 (6 GB). |
| `docker compose -f docker-compose.yml -f docker-compose.gpu.yml restart worker` | Reinicia o worker (Jobs em andamento ficam "Interrompido"). |
| `docker compose logs -f worker` | Acompanha o processamento dos Jobs. |
| `docker compose down` | Para tudo (os dados ficam no volume `app_data`). |
| `docker compose down -v` | Para tudo e **apaga** dados, modelos baixados e fila. |

## Desenvolvimento local (sem Docker)
Precisa de ffmpeg e de um Redis (`docker compose up -d redis` não expõe a porta; use `docker run --rm -p 127.0.0.1:6379:6379 redis:7-alpine`).

| Comando | O que faz |
| --- | --- |
| `uv sync` | Instala dependências (inclui as de desenvolvimento). |
| `uv run python manage.py migrate` | Cria/atualiza o banco em `./data/db.sqlite3`. |
| `DJANGO_DEBUG=true uv run python manage.py runserver 127.0.0.1:8000` | Servidor de desenvolvimento. |
| `uv run celery -A video_transcription worker -l info --concurrency 1` | Worker que processa os Jobs. |

## Qualidade
| Comando | O que faz |
| --- | --- |
| `uv run pytest` | Testes. |
| `uv run pytest --cov --cov-fail-under=90` | Testes com cobertura mínima de 90% (igual ao CI). |
| `uv run python manage.py makemigrations --check --dry-run` | Confere se os models batem com as migrations. |
| `uv run ruff check .` | Lint. |
| `uv run ruff format --check .` | Confere a formatação (`uv run ruff format .` aplica). |
