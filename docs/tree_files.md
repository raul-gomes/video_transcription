# Arquivos e responsabilidades

| Caminho | Responsabilidade |
| --- | --- |
| `video_transcription/settings.py` | Configuração do Django, toda vinda do ambiente (`.env.example`). |
| `video_transcription/config.py` | Leitura de variáveis (`env_bool`, `env_list`) e `SECRET_KEY` gerada no primeiro uso. |
| `video_transcription/urls.py` | Rotas do projeto e download dos arquivos gerados (`/media/`). |
| `video_transcription/celery.py` | App Celery. |
| `core/constants.py` | Idiomas, modelos do Whisper (com dica), dispositivos e extensões aceitas. |
| `core/media_analysis.py` | Análise da Mídia: roda o ffprobe e descreve contêiner, vídeo, Faixas de áudio e legendas, com MIME para o `canPlayType` do navegador. |
| `core/models.py` | Job (status, opções, arquivos), Trecho e estado do worker. |
| `core/services.py` | Regras: criar (validação + Análise da Mídia, fica aguardando decisão), confirmar a decisão (entra na fila), cancelar, reprocessar, excluir, Trechos após um tempo, início do worker (GPU + Interrompido). |
| `core/serializers.py` | Payloads da API escritos à mão, no formato de `static/js/contract.js`. |
| `core/permissions.py` | CSRF obrigatório em toda escrita da API (o app não tem login). |
| `core/views.py` | Página e API JSON (`/api/options/`, `/api/jobs/…`). Só HTTP; as regras ficam em `services`. |
| `core/urls.py` | Rotas da página e da API. |
| `core/tasks.py` | Task Celery: pula Job que não está na fila e grava erros inesperados no Job. |
| `core/worker.py` | Hook de início do worker: detecta a GPU num subprocesso e marca Jobs interrompidos. |
| `core/utils.py` | Pipeline (Prévia → extrair a Faixa escolhida → Whisper → Legendas → embutir), cache do modelo por worker e dispositivo, detecção de GPU, falta de memória de vídeo. Escritas de status só valem se o Job ainda estiver ativo. |
| `ai_revision/` | Revisão por IA (vazio até a Fase 3). |
| `templates/core/` | Página única (template Django). |
| `static/js/contract.js` | Contrato da API (JSDoc) e rótulos de status. |
| `static/js/api.js` | Cliente da API (fetch + CSRF). |
| `static/js/main.js` | Entrada da página: opções, histórico, polling a cada 5 s. |
| `static/js/analysis-dialog.js` | Modal da Análise da Mídia: mostra o arquivo, pergunta ao navegador o que ele toca e coleta a decisão. |
| `static/js/upload-view.js` | Card de envio: arquivo, idioma, modelo, dispositivo e validação. |
| `static/js/jobs-view.js` | Histórico: cards por Job, atualizados no lugar. |
| `static/js/job-detail.js` | Card aberto: player e Transcrição com tempo clicável. |
| `static/js/dom.js` | Construtor de DOM sem `innerHTML` e formatação pt-BR. |
| `static/css/style.css` | Estilos (tema claro/escuro). |
| `tests/` | Testes (pytest + pytest-django). `conftest.py` isola `DATA_DIR`, usa Celery em memória e nunca olha o cache do Whisper nem a GPU da máquina. |
| `Dockerfile`, `docker-compose.yml`, `docker-compose.gpu.yml` | Imagem única web/worker, stack local e GPU opcional. |
| `.env.example` | Variáveis aceitas, com padrões seguros. |
| `GLOSSARY.md`, `docs/adr/`, `docs/plano.md` | Termos do domínio, decisões e plano de finalização. |
