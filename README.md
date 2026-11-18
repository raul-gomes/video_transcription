# Video Transcription

Transforme a fala de um vídeo ou áudio em legendas e texto, direto na sua máquina. A transcrição usa o [Whisper](https://github.com/openai/whisper) localmente: nada é enviado para a internet e não há custo de API.

**Saídas:** legenda SRT e VTT, transcrição em TXT e JSON e o vídeo com a legenda embutida (faixa que o player liga e desliga).

> Em desenvolvimento. O plano das próximas fases (transcrição ao vivo, revisão por IA) está em [`docs/plano.md`](docs/plano.md).

## Como rodar

Você precisa só do [Docker](https://docs.docker.com/get-docker/) com o Compose.

```bash
git clone https://github.com/raul-gomes/video_transcription.git
cd video_transcription
docker compose up -d --build
```

Abra http://127.0.0.1:8000.

- A primeira transcrição baixa o modelo do Whisper (centenas de MB) e guarda para as próximas.
- Os vídeos e as legendas ficam no volume Docker `app_data`. `docker compose down` mantém os dados; `docker compose down -v` apaga tudo.
- Configurações opcionais: copie `.env.example` para `.env`.

### Com GPU NVIDIA (opcional)

Com o [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/) instalado, a transcrição fica bem mais rápida:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```

## Segurança

O app foi feito para uma pessoa só, na própria máquina, e **não tem login**. Por isso ele aceita conexões apenas de `127.0.0.1`. Não exponha a porta na rede.

## Desenvolvimento

Comandos de desenvolvimento, testes e qualidade em [`docs/comandos.md`](docs/comandos.md). Decisões de arquitetura em [`docs/adr/`](docs/adr/) e termos do domínio em [`GLOSSARY.md`](GLOSSARY.md).

Stack: Python 3.13, Django 5 + DRF, Celery + Redis, Whisper, ffmpeg, SQLite.
