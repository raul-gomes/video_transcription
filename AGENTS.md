# AGENTS.md

Orientações para agentes neste repositório.

## Práticas gerais
As regras transversais (TDD, segurança, qualidade, git flow, documentação viva) ficam no segundo cérebro do Raul: `~/HD_Repos/cerebro/20_Praticas/Praticas-Essenciais.md`. Este arquivo só traz o que é específico deste projeto e prevalece em caso de conflito.

## O que é
App **local, de uma pessoa só, sem login** (ADR 0001) que transcreve a fala de vídeos e áudios com Whisper, gera Legendas (SRT/VTT), Transcrição (TXT/JSON) e o Vídeo legendado, com Revisão opcional por IA. Termos do domínio em `GLOSSARY.md`; plano e fases em `docs/plano.md`; decisões em `docs/adr/`.

## Documentação viva (no mesmo commit da mudança)
`docs/comandos.md` (todo comando útil) · `docs/lineage.md` (schema e migrations) · `docs/tree_files.md` (responsabilidade dos arquivos) · `docs/pendencias.md` · `GLOSSARY.md` · `docs/adr/`.

## Invariantes
1. O servidor escuta só em `127.0.0.1`. Nunca mude o padrão de `ALLOWED_HOSTS` nem a porta do compose para expor na rede.
2. A chave do Provedor de IA nunca volta numa resposta da API, nunca vai para log e fica criptografada no banco (ADR 0004).
3. A Revisão por IA só cria Sugestões. Ela nunca altera tempos, quantidade ou ordem dos Trechos, e nunca apaga a Legenda original (ADR 0005).
4. Dado da API entra na página com `textContent`/`createElement`, nunca `innerHTML` (ADR 0006).
5. ffmpeg é chamado com argv fixo, sem shell.

## Stack e convenções
- Python 3.13 + uv, Django 5 + DRF, Celery + Redis (um Job por vez, ADR 0002), Whisper local, ffmpeg, SQLite em `DATA_DIR`.
- Front sem build: templates Django + JS em módulos ES + CSS puro.
- Código, comentários, testes e commits em inglês. UI em pt-BR.
- Dependência: `uv add` (manifesto + `uv.lock` no mesmo commit).

## Testes
- `uv run pytest --cov --cov-fail-under=90`. Testes em `tests/`.
- ffmpeg, Whisper e LLM são sempre simulados. Nada de rede, Redis real ou download de modelo nos testes (o `tests/conftest.py` isola `DATA_DIR` e usa Celery em memória).

## Git
`feature/*` a partir de `develop`, PR de volta. `master` só recebe release e hotfix.
