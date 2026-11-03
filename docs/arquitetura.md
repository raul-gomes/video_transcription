# Arquitetura — Video Transcription

Documento de arquitetura do sistema de transcrição automática de vídeos.

---

## 1. Visão Geral

O sistema é uma aplicação **Django** com processamento assíncrono de vídeos delegado a um **worker Celery**. O trabalho pesado (extração de áudio, transcrição com IA e geração de legendas) roda **fora do ciclo de requisição HTTP**, garantindo que o upload responda rapidamente e que o usuário acompanhe o progresso via polling.

Toda a infraestrutura roda em containers orquestrados pelo Docker Compose.

---

## 2. Diagrama de Componentes

```
                        ┌──────────────────────────┐
                        │        Navegador          │
                        │  (upload + polling + UI)  │
                        └────────────┬─────────────┘
                                     │ HTTP :8000
                                     ▼
        ┌────────────────────────────────────────────────┐
        │                    web (Django)                 │
        │  • IndexView            (página de upload)       │
        │  • LibraryView          (GET  /videos/)          │
        │  • VideoDetailView      (GET  /videos/<id>/)      │
        │  • UploadVideoView      (POST /api/upload/)      │
        │  • JobListView          (GET  /api/jobs/)         │
        │  • JobProgressView      (GET  /api/progress/)    │
        │  • Download*View        (GET  /download_*/)      │
        │  • Admin Django                                  │
        └───────┬───────────────────────────────┬────────┘
                │ ORM (SQL)                      │ enfileira tarefa
                ▼                                ▼
        ┌───────────────┐                 ┌───────────────┐
        │   PostgreSQL  │                 │     Redis     │
        │   (db :5432)  │                 │ (broker :6379)│
        └───────▲───────┘                 └───────┬───────┘
                │ ORM                             │ consome tarefa
                │                                 ▼
        ┌───────┴────────────────────────────────────────┐
        │                 worker (Celery)                │
        │           VideoProcessor.process()             │
        │   FFmpeg → Whisper → SRT/VTT/JSON/TXT → FFmpeg │
        └────────────────────────────────────────────────┘
                                     ▲
                                     │ agenda tarefas periódicas
                              ┌──────┴──────┐
                              │    beat     │
                              │ (Celery Beat)│
                              └─────────────┘
```

---

## 3. Componentes

### 3.1 `web` — Aplicação Django

- Expõe a interface (template `core/index.html`) e a API REST.
- Persiste jobs no PostgreSQL via ORM.
- Enfileira o processamento com `process_video_task.delay(<job_id>)` no Redis.
- É o **único** serviço que aplica migrações no start (evita corrida de migrações concorrentes).

### 3.2 `worker` — Celery Worker

- Consome tarefas da fila Redis.
- Executa `VideoProcessor.process()`, o pipeline de mídia:

  | Etapa | Ação | Ferramenta | Progresso |
  |-------|------|-----------|-----------|
  | 1 | Extração de áudio (WAV 16 kHz mono) | FFmpeg | 20% |
  | 2 | Transcrição (progressiva, em janelas de 30s) | Whisper `small`, idioma automático | 60–80% |
  | 3 | Geração de SRT / VTT / JSON / TXT | Python | 80% |
  | 4 | Mux de legendas no MP4 | FFmpeg (`mov_text`) | 90% |
  | 5 | Finalização | — | 100% |

- Cada etapa atualiza `TranscriptionJob.status`, `progress_percentage` e `current_step`.

**Transcrição progressiva (tempo real).** O áudio é carregado uma vez e dividido em janelas de 30 s (o mesmo tamanho da janela interna do Whisper). A cada janela, os trechos são gravados em `SubtitleSegment` e o progresso avança de 60% a 80%. Assim o frontend consegue exibir as legendas **enquanto** o vídeo ainda está sendo transcrito, em vez de esperar o fim do processamento. O contexto entre janelas é mantido via `condition_on_previous_text` + `initial_prompt`.

**Idioma.** O Whisper é multilíngue. A ordem de prioridade do idioma é: escolha do usuário (campo `TranscriptionJob.language`, preenchido pelo seletor em `/api/upload/`) → variável `WHISPER_LANGUAGE` → **automático**. No modo automático, o idioma é detectado somando as probabilidades (`model.detect_language`) das **primeiras 4 janelas** (até 2 min) e escolhendo a mais provável — olhar só a primeira janela é frágil quando o vídeo começa com um trecho em outro idioma. O idioma detectado é salvo no job e exibido na interface.

### 3.3 `beat` — Celery Beat

- Agendador de tarefas periódicas. Usa o `PersistentScheduler` (arquivo `celerybeat-schedule`), sem dependência de tabelas extras no banco.

### 3.4 `db` — PostgreSQL 15

- Fonte de verdade dos dados (`TranscriptionJob`, `SubtitleSegment`, usuários, etc.).
- Healthcheck via `pg_isready`; os demais serviços só iniciam após `service_healthy`.

### 3.5 `redis` — Redis 7

- Broker de mensagens do Celery e result backend.
- Healthcheck via `redis-cli ping`.

### 3.6 Interface (frontend)

Construída em HTML + **Tailwind CSS** (via CDN) + JavaScript puro (sem framework):

- **Topo:** barra de progresso geral, etapa atual e status.
- **Esquerda:** player de vídeo (`<video>`), carregado logo após o upload (via `URL.createObjectURL` para reprodução imediata). A reprodução começa assim que o primeiro trecho transcrito existe e é interrompida caso o vídeo alcance a "fronteira" já transcrita — retomando sozinha quando novos trechos chegam. Assim o vídeo nunca fica dessincronizado da legenda.
- **Direita:** painel de transcrição que recebe os trechos via *polling* (2 s) do endpoint de progresso.
- **Sincronização:** a cada `timeupdate` do player, o trecho correspondente é destacado na lista e exibido sobre o vídeo; clicar em um trecho reposiciona o vídeo.

A comunicação é feita por *polling* HTTP simples (`GET /api/progress/<id>/`), retornando `status`, `progress_percentage`, `video_url` e a lista de `segments` já disponíveis.

#### 3.6.1 Páginas

| Página | Rota | Descrição |
|--------|------|-----------|
| Upload | `/` | Envio do vídeo e acompanhamento em tempo real (`app.js`) |
| Biblioteca | `/videos/` | Lista todos os envios com progresso ao vivo, via `GET /api/jobs/` (`library.js`) |
| Player | `/videos/<job_id>/` | Reprodução com legendas sincronizadas; retoma da última posição (localStorage) (`detail.js`) |

Os scripts são carregados por página através do bloco `{% block scripts %}` do template base, evitando que `app.js` (específico do upload) rode nas demais páginas.

#### 3.6.2 Reprodução progressiva ("streaming")

O player e a transcrição evoluem juntos:

1. O áudio é transcrito em janelas de 30 s e cada trecho é gravado no banco assim que fica pronto.
2. O frontend faz *polling* a cada 2 s e vai preenchendo a lista de legendas.
3. Assim que existe **pelo menos um trecho**, a reprodução é liberada (sem esperar o fim).
4. Define-se a **fronteira** = `fim do último trecho transcrito`. Ao atingi-la, o vídeo é pausado ("Aguardando a transcrição…") e **retomado automaticamente** quando o *polling* traz trechos além do ponto atual (`horizonte > tempo + 3s`).

Dessa forma o vídeo nunca ultrapassa o que já foi transcrito, mantendo a legenda sempre sincronizada.

#### 3.6.3 Mídia com HTTP Range

Em desenvolvimento, `django.views.static.serve` não implementa *Range requests*, o que impede o *seek* em vídeos grandes (o vídeo "volta ao início"). Por isso a mídia é servida por `core.views.serve_media`, que responde `206 Partial Content`, envia `Content-Range`/`Accept-Ranges` e faz *streaming* apenas do intervalo pedido. Isso é pré-requisito para o clique-para-pular, a retomada de posição e a pausa na fronteira.

---

## 4. Fluxo de uma Requisição

```
1. Usuário seleciona o vídeo e clica em "Processar".
2. POST /api/upload/ → cria TranscriptionJob(pending) → .delay(job_id) → responde {job_id}.
3. Worker consome a tarefa e processa o vídeo passo a passo.
4. Frontend faz polling em GET /api/progress/<job_id>/ a cada 2 s.
5. Ao concluir (status=completed), a API retorna as URLs dos arquivos.
6. Usuário baixa vídeo legendado, .srt, .vtt e .txt.
```

---

## 5. Decisões de Arquitetura

| Decisão | Justificativa |
|---------|---------------|
| **Processamento assíncrono (Celery)** | Transcrição é custosa (segundos/minutos); o HTTP não pode bloquear. |
| **PostgreSQL em vez de SQLite** | Concorrência entre `web` e `worker` e ambiente mais próximo de produção. |
| **Whisper em CPU** | Roda sem GPU; evita o download de ~2 GB de bibliotecas CUDA (usa PyTorch CPU-only). |
| **Bind mount do código (`.:/app`)** | Facilita desenvolvimento: alterações refletem sem rebuild. |
| **Migrações só no serviço `web`** | Evita condição de corrida que corrompe `django_migrations`. |
| **`wait_for_services.py` (Python) em vez de `psql`** | A imagem não inclui o cliente `psql`; o script usa `psycopg2` já instalado. |
| **FFmpeg no container** | Processamento de mídia isolado e reprodutível. |
| **Modelo Whisper `small` por padrão** | O `medium` (~1.5 GB) causava OOM numa VM de ~3,5 GB. O `small` (~460 MB) cabe e ainda tem boa qualidade em português; o modelo é configurável por `WHISPER_MODEL`. |
| **Worker com `concurrency=1` + reciclo por tarefa** | Cada instância do Whisper consome muita RAM; evitar vários processos previne OOM. |
| **`CELERY_TASK_ACKS_LATE=False`** | Se o processo morrer por OOM, a tarefa não entra em loop infinito de reentrega. |
| **Transcrição em janelas de 30s** | Permite exibir as legendas em tempo real, gravando os trechos progressivamente. |
| **Detecção automática de idioma** | O idioma fixo (`pt`) fazia vídeos em inglês saírem em português. Agora o Whisper detecta o idioma somando as probabilidades das primeiras janelas; o usuário ainda pode forçar um idioma no upload. |

---

## 6. Volumes e Persistência

| Volume | Conteúdo |
|--------|----------|
| `postgres_data` | Dados do PostgreSQL |
| `redis_data` | Dados do Redis |
| `media_data` | Vídeos enviados e arquivos gerados |
| `static_data` | Arquivos estáticos coletados |

Remover tudo: `docker compose down -v`.

---

## 7. Segurança / Produção

O ambiente atual é de **desenvolvimento** (`DEBUG=True`, `runserver`, credenciais padrão). Para produção recomenda-se:

- `DEBUG=False` e `DJANGO_SECRET_KEY` forte;
- Servir via Gunicorn/uWSGI atrás de um proxy reverso (Nginx);
- `ALLOWED_HOSTS` restrito;
- Credenciais em secrets, não no `.env`;
- HTTPS e política de CSRF/cookies endurecida.
