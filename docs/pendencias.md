# Pendências

As fases planejadas estão em `docs/plano.md`. Aqui ficam problemas conhecidos e ideias soltas.

## Problemas conhecidos (Fase 1)
- [x] `CELERY_TASK_ALWAYS_EAGER = True`: o upload roda o pipeline inteiro dentro da requisição.
- [x] O JS chama `/api/progress/<id>/` com barra no final; a rota não tem a barra (404).
- [x] Falha ao embutir a Legenda não marca o Job como falho.
- [x] `confidence` sempre nula: o Whisper não devolve essa chave.
- [x] Modelo `medium` carregado a cada Job.
- [x] Upload sem validação de tipo nem limite de tamanho.
- [x] A task do Celery engole exceções e grava o erro só no backend de resultados.

## Infra
- [ ] Imagem Docker grande (PyTorch com suporte a CUDA): avaliar uma imagem só-CPU menor como opção.
- [ ] Na máquina do Raul, a coleta de lixo do cache do BuildKit descarta a camada de dependências (~6,5 GB) entre builds, e cada rebuild leva ~10 min. Disco em 82%, 69 GB de imagens recuperáveis: decisão do Raul (fora do projeto).
- [x] Perfil de GPU testado numa RTX 2060 (6 GB): `small` funciona; `medium` estoura a memória de vídeo com o desktop aberto (o Job falha com mensagem clara).
- [x] CI só roda quando o repo ficar público (resolvido: repo público em 2026-11-19).

## Front
- [x] Ícones do Font Awesome empacotados em `static/vendor/fontawesome/` (antes vinham de CDN). A fonte FKGroteskNeue, carregada de um servidor da Perplexity, foi removida (volta para as fontes do sistema).
- [x] Layout em tela estreita (celular) conferido em 390px (2026-11-19).

## Pipeline
- [ ] Cancelar durante o download do modelo deixa um arquivo parcial no cache; o Whisper baixa de novo (confere o checksum), mas a tela não mostra "Baixando modelo…" nessa segunda vez.
- [x] Teste com vídeo real falado (episódio de 22 min, GPU, 2026-11-19).
- [ ] Repetição da última frase no fim dos Blocos (9 de 48 cortes): correção combinada na ADR 0003, a implementar.
- [ ] Silêncios longos e música: conferir se o Whisper inventa frases ("Pew pew" repetido no fim do episódio).

## Análise da Mídia
- [ ] Conversão da imagem na Prévia (HEVC/AV1) testada só com argv simulado; falta um arquivo HEVC real.
- [ ] Legendas que já vêm no arquivo: hoje só informativas. Ideia: usar uma delas em vez de transcrever.
- [ ] Vídeo legendado em MP4 com legendas de imagem (PGS) no original: a conversão para mov_text falha. MKV não tem esse problema.

## Futuro
- [ ] Gerar áudio a partir do SRT.
- [ ] Editar a legenda enquanto assiste.
- [ ] Retomar Job Interrompido a partir do Bloco onde parou.
