# Plano de finalização

Fechado com o Raul em 2026-11-18 (sessão de grilling). As decisões estão nas ADRs em `docs/adr/` e os termos em `GLOSSARY.md`. Um PR por fase para a `develop`, com TDD. Telas novas começam com o layout sobre dados simulados para validação.

## Fase 0: base
- [x] `develop`, `AGENTS.md`, glossário, ADRs e documentação viva (`comandos`, `lineage`, `tree_files`, `pendencias`).
- [x] Configurações pelo `.env`: `SECRET_KEY` gerada no primeiro uso se faltar, `DEBUG` desligado por padrão e `ALLOWED_HOSTS` local.
- [x] Remover a dependência do Postgres (`psycopg2-binary`) e o `main.py` de exemplo.
- [x] pytest + pytest-django com cobertura mínima de 90% e ruff (lint + format).
- [x] Dockerfile + Compose: web, worker, Redis e ffmpeg. Portas só em `127.0.0.1`, volume para dados e para os modelos do Whisper, perfil `gpu` opcional.
- [x] CI no GitHub Actions (passa a rodar quando o repo ficar público).

## Fase 1: correções e base do produto
- [x] Celery assíncrono de verdade e um Job por vez (configurável).
- [x] Rota de progresso sem 404.
- [x] Falha ao embutir a Legenda marca o Job como falho.
- [x] Confiança dos Trechos calculada a partir do que o Whisper devolve.
- [x] Modelo de transcrição carregado uma vez por worker.
- [x] Upload de vídeo (mp4, mkv, mov, webm) ou áudio (mp3, wav, m4a, ogg) até 2 GB (configurável). Áudio pula a extração e o Vídeo legendado.
- [x] Na tela de upload: idioma, Modelo de transcrição (padrão `small`) e Dispositivo (Automático/CPU/GPU, com a GPU habilitada só se o worker detectar uma).
- [x] Histórico de Jobs com exclusão completa (pede confirmação), Cancelar, e Interrompido → Reprocessar. Clicar no card abre o player com a Transcrição (um card aberto por vez).
- [x] Status "Na fila" e "Baixando modelo…".
- [ ] Repo público com licença MIT ao fim da fase.

## Fase 2: transcrição ao vivo
- [ ] Blocos de 30s com 2s de Sobreposição. Trechos gravados e SRT/VTT parciais a cada Bloco.
- [ ] `GET /api/jobs/<id>/segments?after=<s>`; a tela busca a cada 5s.
- [ ] SRT parcial para baixar durante o Job. Vídeo legendado só no fim.

## Fase 3: Revisão por IA (`ai_revision`, LangChain)
- [ ] Configurações: Provedor de IA (Anthropic, OpenAI ou Ollama), modelo (texto com sugestão), chave criptografada e mascarada (o `.env` tem prioridade), URL do Ollama e "Testar conexão".
- [ ] Ao terminar o Job, os arquivos aparecem para baixar com um botão opcional "Revisar com IA".
- [ ] Campo opcional "Contexto do vídeo", com o texto de ajuda.
- [ ] Sugestões por Trecho, com motivo e sem mudar os tempos. Aceitar ou recusar.
- [ ] Versão revisada (SRT, VTT, TXT) ao lado da original. Vídeo legendado revisado sob demanda.

## Fase 4: portfólio
- [ ] Números medidos, `docs/portfolio.md` e página pt/en na `home`, com o texto validado pelo Raul.

## Futuro
- Gerar áudio a partir do SRT (texto revisado → voz).
- Editar a legenda enquanto assiste.
- Retomar um Job Interrompido a partir do Bloco onde parou.
