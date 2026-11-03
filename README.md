# Video Transcription

Sistema de **transcrição automática de vídeos** com geração de legendas, construído com **Django**, **Whisper (IA)** e **Celery**. Todo o ambiente de execução (Django, Celery worker, Celery beat, Redis e PostgreSQL) roda em **containers Docker**.

---

## 1. Análise do Projeto

### 1.1 Objetivo

Receber o upload de um vídeo, extrair o áudio, transcrevê-lo com o modelo **Whisper** (OpenAI), gerar arquivos de legenda e devolver ao usuário:

- Vídeo final com legendas embutidas (soft subtitles)
- Legenda `.srt`
- Legenda `.vtt`
- Transcrição em texto puro `.txt`
- Metadados em `.json`

### 1.2 Stack Tecnológica

| Camada | Tecnologia |
|--------|-----------|
| Backend | Django (>= 5.2), Django REST Framework |
| IA / Transcrição | OpenAI Whisper (`medium`, idioma `pt`) |
| Processamento de mídia | FFmpeg |
| Fila de tarefas | Celery |
| Agendador | Celery Beat |
| Broker / Cache | Redis 7 |
| Banco de dados | PostgreSQL 15 |
| Infraestrutura | Docker / Docker Compose |
| Logs | Loguru |

### 1.3 Estrutura de Apps

- **`core`** — núcleo do sistema: modelo de dados, upload, progresso, tarefas Celery e pipeline de processamento de vídeo.
- **`ai_revision`** — app reservado para futuras revisões assistidas por IA.

### 1.4 Fluxo de Processamento

```
 Upload do vídeo
       │
       ▼
 [core.views.UploadVideoView]  ──► cria TranscriptionJob (status=pending)
       │
       ▼
 process_video_task.delay()  ──► enfileira tarefa no Redis (Celery)
       │
       ▼
 [Celery Worker] VideoProcessor.process()
       1. extrai_audio()            (FFmpeg  → WAV 16kHz mono)       20%
       2. transcribe_audio()        (Whisper medium, pt)             60%
       3. generate_subtitle_files() (SRT / VTT / JSON / TXT)         80%
       4. mux_soft_subtitle()       (FFmpeg  → MP4 com legenda)      90%
       5. status=completed                                           100%
       │
       ▼
 Frontend consulta o progresso via polling (GET /api/progress/<id>/)
 e libera player + downloads.
```

### 1.5 Modelo de Dados

- **`TranscriptionJob`** — um job de transcrição: arquivo de vídeo, status, progresso, arquivos gerados (áudio, srt, vtt, json, txt, vídeo final) e timestamps.
- **`SubtitleSegment`** — cada trecho transcrito (início, fim, texto, confiança), ligado a um `TranscriptionJob`.

---

## 2. Execução com Docker (recomendado)

### 2.1 Serviços

O `docker-compose.yml` sobe **5 serviços**:

| Serviço | Descrição | Porta |
|---------|-----------|-------|
| `db` | PostgreSQL 15 | 5432 |
| `redis` | Redis 7 (broker/result backend) | 6379 |
| `web` | Django (Gunicorn/`runserver`) | 8000 |
| `worker` | Celery worker (processa os vídeos) | — |
| `beat` | Celery Beat (agendador) | — |

### 2.2 Subir o projeto

```bash
docker compose up -d
```

Acesse: **http://localhost:8000**

O entrypoint (`entrypoint.sh`) automaticamente:

1. Aguarda PostgreSQL e Redis ficarem prontos (`wait_for_services.py`);
2. Aplica as migrações (somente o serviço `web`);
3. Coleta os arquivos estáticos;
4. Inicia o serviço correspondente (web / worker / beat).

### 2.3 Superusuário (Admin)

Já existe um superusuário criado para o portfólio:

| Campo | Valor |
|-------|-------|
| Usuário | `admin` |
| Senha | `admin123` |
| E-mail | `admin@portifolio.com` |
| URL | http://localhost:8000/admin/ |

Para criar/recriar manualmente:

```bash
docker compose exec -e DJANGO_SUPERUSER_PASSWORD=admin123 web \
  python manage.py createsuperuser --noinput \
  --username admin --email admin@portifolio.com
```

### 2.4 Comandos úteis

```bash
# Ver status dos containers
docker compose ps

# Acompanhar logs
docker compose logs -f web
docker compose logs -f worker

# Abrir shell do Django
docker compose exec web python manage.py shell

# Parar tudo (mantendo dados)
docker compose down

# Parar tudo e apagar volumes (banco, mídia, cache)
docker compose down -v
```

---

## 3. Variáveis de Ambiente

Definidas em `.env` (veja `.env.example`):

| Variável | Descrição |
|----------|-----------|
| `DJANGO_SECRET_KEY` | Chave secreta do Django |
| `DEBUG` | Modo debug (`True`/`False`) |
| `ALLOWED_HOSTS` | Hosts permitidos |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | Credenciais do banco |
| `DATABASE_URL` | URL completa do PostgreSQL |
| `REDIS_URL` | URL do Redis |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | Configuração do Celery |
| `WHISPER_MODEL` | Tamanho do modelo Whisper (`tiny`, `base`, `small`, `medium`, `large`). Padrão: `small` |
| `WHISPER_LANGUAGE` | Idioma padrão da transcrição: `auto` (detecta sozinho), `pt`, `en`, `es`, `fr`, `de`, `it`, `ja`, `zh`, `ru`. Padrão: `auto`. A escolha feita na tela de upload tem prioridade sobre esta variável |
| `CELERY_WORKER_CONCURRENCY` | Processos paralelos do worker. Padrão: `1` (recomendado com pouca RAM) |

---

## 5. Interface

O layout foi pensado para acompanhar a transcrição em tempo real:

- **Barra geral no topo** — progresso percentual, etapa atual e status.
- **Player à esquerda** — o vídeo começa a tocar **assim que os primeiros trechos da legenda ficam prontos**, sem esperar a transcrição inteira. Se o vídeo alcançar o ponto até onde já existe legenda, ele **pausa sozinho** ("Aguardando a transcrição…") e **retoma automaticamente** quando novos trechos chegam — assim a legenda nunca sai de sincronia. O jogador também **retoma de onde você parou**.
- **Barra lateral à direita** — os trechos da legenda vão aparecendo conforme o Whisper transcreve, com o horário de cada trecho.
- **Sincronização ao vivo** — o trecho correspondente ao momento atual do vídeo é destacado automaticamente (e a legenda aparece sobre o player). Clicar em um trecho pula o vídeo para aquele instante.
- **Downloads** — ao concluir, libera o vídeo com legendas, `.srt`, `.vtt` e `.txt`.
- **Idioma** — a transcrição funciona para **qualquer idioma suportado pelo Whisper** (português, inglês, espanhol, etc.). Por padrão o idioma é **detectado automaticamente** (somando as probabilidades das primeiras janelas de áudio, para ser robusto em vídeos com trechos em outro idioma). Na tela de upload há um seletor para **forçar** um idioma quando a detecção não for a desejada; o idioma usado aparece como um selo ao lado de "Transcrição" e nos cartões da biblioteca.

As legendas aparecem progressivamente porque o worker grava cada trecho no banco **à medida que transcreve** (de 30 em 30 segundos de áudio), e o frontend consulta o progresso a cada 2 segundos.

### 5.1 Página "Meus vídeos" (`/videos/`)

Uma biblioteca com **todos os vídeos enviados**, mostrando para cada um: nome, status, percentual de progresso (atualizado automaticamente), duração, quantidade de trechos e a data do envio. Ao clicar em um cartão, abre-se o player daquele vídeo em `/videos/<job_id>/`.

O player na página de detalhe **retoma de onde você parou** (posição guardada no navegador) e mantém a mesma sincronização com a legenda da página inicial.

---

## 6. Endpoints da API

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/` | Página principal (upload) |
| GET | `/videos/` | Biblioteca com todos os vídeos enviados e o progresso |
| GET | `/videos/<job_id>/` | Player de um vídeo específico (com legendas) |
| POST | `/api/upload/` | Envia o vídeo e inicia o processamento |
| GET | `/api/jobs/` | Lista de jobs (usada para atualizar a biblioteca) |
| GET | `/api/progress/<job_id>/` | Status/progresso do job (inclui `segments` e `video_url`) |
| GET | `/api/transcription/<job_id>/download_video/` | Baixa o vídeo com legendas |
| GET | `/api/transcription/<job_id>/download_srt/` | Baixa a legenda `.srt` |
| GET | `/api/transcription/<job_id>/download_vtt/` | Baixa a legenda `.vtt` |
| GET | `/api/transcription/<job_id>/download_transcript/` | Baixa a transcrição `.txt` |

---

## 7. Observações de Performance

- A imagem instala o **PyTorch CPU-only** (`--index-url https://download.pytorch.org/whl/cpu`) para evitar o download de ~2 GB de bibliotecas CUDA.
- O modelo Whisper é baixado na primeira transcrição e fica em cache no container. Por padrão usa-se o **`small`** (~460 MB), que roda bem em máquinas com ~3–4 GB de RAM. Defina `WHISPER_MODEL=medium` se tiver mais memória.
- O worker roda com **concurrency = 1** e é reciclado a cada tarefa (`max-tasks-per-child=1`), pois cada instância do Whisper consome bastante RAM.
- A mídia é servida por uma view própria (`core.views.serve_media`) com suporte a **HTTP Range** (`206 Partial Content`). O servidor padrão do Django (`django.views.static.serve`) não implementa Range, o que impedia o *seek* em vídeos grandes (o vídeo "voltava ao início"). Com Range, funcionam o clique-para-pular, a retomada de posição e a pausa na fronteira da transcrição.
- **Vídeos sem faixa de áudio** não podem ser transcritos. Isso é comum em downloads de vídeo de streams DASH (que trazem só a faixa de vídeo). O sistema detecta a ausência de áudio via `ffprobe` (`VideoProcessor.has_audio_stream`) e mostra uma mensagem clara ("O vídeo não possui faixa de áudio…"), em vez de um erro genérico.
- O código é montado por bind mount (`.:/app`), portanto alterações no código refletem sem rebuild. Rebuild é necessário apenas ao alterar `requirements.txt`/`Dockerfile`:

```bash
docker compose up -d --build
```

---

## 8. Documentação de Arquitetura

Veja [`docs/arquitetura.md`](docs/arquitetura.md) para o detalhamento da arquitetura, decisões de projeto e diagramas.
