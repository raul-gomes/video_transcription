# Lineage do banco

Atualizado em 2026-11-18. Fonte da verdade: as migrations em `core/migrations/`. Banco: SQLite em `DATA_DIR/db.sqlite3`.

## core_transcriptionjob (Job)
| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `id` | UUID (PK) | Identificador do Job. |
| `media_file` | arquivo | Mídia enviada, vídeo ou áudio (`media/videos/<id>.<ext>`). |
| `original_filename` | texto(255) | Nome do arquivo como a pessoa enviou (exibido na tela). |
| `media_kind` | texto(10) | `video` ou `audio`. Áudio não gera Vídeo legendado. |
| `language` | texto(10) | Código do idioma (`pt`, `en`, `es`) ou `auto`. |
| `detected_language` | texto (vazio) | No Automático, idioma que o Whisper achou no primeiro Bloco com fala (ADR 0003). Limpo ao Reprocessar. |
| `model_name` | texto(20) | Modelo de transcrição: `tiny`, `base`, `small`, `medium`, `large`. |
| `device` | texto(10) | Dispositivo: `auto`, `cpu` ou `gpu`. |
| `status` | texto(20) | `awaiting_decision` (padrão), `queued`, `preparing_preview`, `downloading_model`, `extracting`, `transcribing`, `generating`, `completed`, `failed`, `cancelled`, `interrupted`. |
| `progress_percentage` | inteiro | Progresso de 0 a 100. |
| `current_step` | texto(100) | Etapa atual em pt-BR, exibida na tela. |
| `error_message` | texto | Mensagem em pt-BR quando o Job falha. |
| `celery_task_id` | texto(64) | Task do Celery, usada para cancelar. |
| `analysis` | JSON, nulo | Análise da Mídia (contêiner, vídeo, Faixas de áudio, legendas embutidas), gravada no upload. Formato em `static/js/contract.js` (`MediaAnalysis`). |
| `audio_stream_index` | inteiro, nulo | Índice da Faixa de áudio escolhida (stream do arquivo). Nulo = escolha do ffmpeg. |
| `make_preview` | booleano | A pessoa pediu a Prévia para o navegador. |
| `convert_video` | booleano | A Prévia também converte a imagem (lento). |
| `preview_file` | arquivo | Prévia: imagem copiada (ou convertida) + Faixa de áudio em AAC estéreo (`media/previews/`). |
| `audio_file` | arquivo | WAV mono 16 kHz extraído (`media/audio/`). |
| `srt_file`, `vtt_file`, `json_file` | arquivo | Legendas e Trechos em JSON (`media/subtitles/`). |
| `transcript_file` | arquivo | Transcrição em TXT (`media/transcripts/`). |
| `final_video` | arquivo | Vídeo legendado (`media/processed/`): todas as faixas originais + a nossa legenda como padrão. MKV continua MKV; o resto vira MP4. Vazio para áudio ou sem fala. |
| `duration_seconds` | real, nulo | Duração da Mídia, lida do WAV extraído. |
| `created_at`, `updated_at` | data/hora | Criação e última alteração. |

Ordem padrão: `-created_at`.

## core_subtitlesegment (Trecho)
| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `id` | inteiro (PK) | |
| `job_id` | FK → Job, `CASCADE` | Job dono do Trecho. |
| `start_time`, `end_time` | real | Início e fim em segundos. |
| `text` | texto | Texto do Trecho. |
| `confidence` | real, nulo | Confiança de 0 a 1, calculada como `exp(avg_logprob)` do Whisper. |

Ordem padrão: `start_time`.

## core_workerstate (estado do worker)
Linha única (`id = 1`), gravada pelo worker ao iniciar.

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `id` | inteiro (PK) | Sempre 1. |
| `gpu_available` | booleano | O worker consegue usar uma GPU NVIDIA. |
| `updated_at` | data/hora | Última vez que um worker iniciou. |

## Migrations
| Migration | O que faz |
| --- | --- |
| `core/0001_initial` | Cria Job e Trecho. |
| `core/0003_media_analysis_and_preview` | Análise da Mídia, decisão (faixa, Prévia, conversão de imagem), arquivo da Prévia; status `awaiting_decision` (novo padrão) e `preparing_preview`. |
| `core/0004_job_detected_language` | Idioma detectado no primeiro Bloco com fala (`detected_language`). |
| `core/0002_job_options_statuses_worker_state` | Renomeia `video_file` → `media_file`; adiciona nome original, tipo de mídia, idioma, modelo, dispositivo, erro e task; novos status (`pending` vira `queued`); cria o estado do worker. |
