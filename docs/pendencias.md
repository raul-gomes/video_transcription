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
- [x] Perfil de GPU testado numa RTX 2060 (6 GB): `small` funciona; `medium` estoura a memória de vídeo com o desktop aberto (o Job falha com mensagem clara).
- [ ] CI só roda quando o repo ficar público (cobrança do GitHub Actions em repo privado).

## Front
- [ ] Ícones do Font Awesome vêm de CDN: sem internet a página fica sem ícones. Empacotar no projeto antes de publicar.
- [ ] Layout em tela estreita (celular) não conferido no navegador.

## Pipeline
- [ ] Cancelar durante o download do modelo deixa um arquivo parcial no cache; o Whisper baixa de novo (confere o checksum), mas a tela não mostra "Baixando modelo…" nessa segunda vez.
- [ ] Teste de ponta a ponta só com vídeos sem fala (tom puro). Falta conferir a qualidade com um vídeo real falado.

## Análise da Mídia
- [ ] Conversão da imagem na Prévia (HEVC/AV1) testada só com argv simulado; falta um arquivo HEVC real.
- [ ] Legendas que já vêm no arquivo: hoje só informativas. Ideia: usar uma delas em vez de transcrever.
- [ ] Vídeo legendado em MP4 com legendas de imagem (PGS) no original: a conversão para mov_text falha. MKV não tem esse problema.

## Futuro
- [ ] Gerar áudio a partir do SRT.
- [ ] Editar a legenda enquanto assiste.
- [ ] Retomar Job Interrompido a partir do Bloco onde parou.
