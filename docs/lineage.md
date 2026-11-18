# Lineage do banco

Atualizado em 2026-11-18. Fonte da verdade: as migrations em `core/migrations/` e `ai_revision/migrations/`. Banco: SQLite em `DATA_DIR/db.sqlite3`.

## core_transcriptionjob (Job)
| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `id` | UUID (PK) | Identificador do Job. |
| `video_file` | arquivo | Mídia enviada (`media/videos/`). |
| `status` | texto(20) | `pending`, `extracting`, `transcribing`, `generating`, `completed`, `failed`. |
| `progress_percentage` | inteiro | Progresso de 0 a 100. |
| `current_step` | texto(100) | Etapa atual ou mensagem de erro, exibida na tela. |
| `audio_file` | arquivo | WAV mono 16 kHz extraído (`media/audio/`). |
| `srt_file`, `vtt_file`, `json_file` | arquivo | Legendas e Trechos em JSON (`media/subtitles/`). |
| `transcript_file` | arquivo | Transcrição em TXT (`media/transcripts/`). |
| `final_video` | arquivo | Vídeo legendado (`media/processed/`). |
| `duration_seconds` | real, nulo | Duração da Mídia (ainda não preenchida). |
| `created_at`, `updated_at` | data/hora | Criação e última alteração. |

## core_subtitlesegment (Trecho)
| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `id` | inteiro (PK) | |
| `job_id` | FK → Job, `CASCADE` | Job dono do Trecho. |
| `start_time`, `end_time` | real | Início e fim em segundos. |
| `text` | texto | Texto do Trecho. |
| `confidence` | real, nulo | Confiança (hoje sempre nula; corrigido na Fase 1). |

Ordem padrão: `start_time`.

## Migrations
| Migration | O que faz |
| --- | --- |
| `core/0001_initial` | Cria Job e Trecho. |
