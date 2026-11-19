# Celery + Redis, com um Job por vez

Mesmo sendo um app local, os Jobs rodam num worker Celery com Redis, e não numa thread ou numa fila no SQLite. A transcrição é longa e pesada, precisa sobreviver ao fim da requisição e ser cancelável, e o Celery já resolve isso. Por padrão, o worker processa **um Job por vez** (`WORKER_CONCURRENCY=1`): o Whisper ocupa muita memória, e dois Jobs juntos podem travar a máquina. Os outros ficam "Na fila".

## Consequências

- O worker carrega o Modelo de transcrição uma vez e o reaproveita entre Jobs.
- Um Job que estava rodando quando o app parou fica "Interrompido" ao reiniciar, e não é retomado sozinho.
