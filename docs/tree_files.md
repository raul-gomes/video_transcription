# Arquivos e responsabilidades

| Caminho | Responsabilidade |
| --- | --- |
| `video_transcription/settings.py` | Configuração do Django, toda vinda do ambiente (`.env.example`). |
| `video_transcription/config.py` | Leitura de variáveis (`env_bool`, `env_list`) e `SECRET_KEY` gerada no primeiro uso. |
| `video_transcription/urls.py` | Rotas do projeto e download dos arquivos gerados (`/media/`). |
| `video_transcription/celery.py` | App Celery. |
| `core/models.py` | Job e Trecho. |
| `core/views.py` | Página inicial, upload e progresso. |
| `core/tasks.py` | Task Celery que roda o pipeline de um Job e grava qualquer erro no próprio Job. |
| `core/utils.py` | Cache do modelo Whisper por worker (`get_model`), confiança (`confidence_from_logprob`) e o pipeline: extrair áudio (ffmpeg) → transcrever (Whisper) → gerar Legendas → embutir no vídeo. |
| `ai_revision/` | Revisão por IA (vazio até a Fase 3). |
| `templates/core/` | Páginas (template Django). |
| `static/js/app.js`, `static/css/style.css` | Front sem build. |
| `tests/` | Testes (pytest + pytest-django). `conftest.py` isola `DATA_DIR` e usa Celery em memória. |
| `Dockerfile`, `docker-compose.yml`, `docker-compose.gpu.yml` | Imagem única web/worker, stack local e GPU opcional. |
| `.env.example` | Variáveis aceitas, com padrões seguros. |
| `GLOSSARY.md`, `docs/adr/`, `docs/plano.md` | Termos do domínio, decisões e plano de finalização. |
