# Pendências

As fases planejadas estão em `docs/plano.md`. Aqui ficam problemas conhecidos e ideias soltas.

## Problemas conhecidos (corrigidos na Fase 1)
- [ ] `CELERY_TASK_ALWAYS_EAGER = True`: o upload roda o pipeline inteiro dentro da requisição.
- [ ] O JS chama `/api/progress/<id>/` com barra no final; a rota não tem a barra (404).
- [ ] Falha ao embutir a Legenda não marca o Job como falho.
- [ ] `confidence` sempre nula: o Whisper não devolve essa chave.
- [ ] Modelo `medium` carregado a cada Job.
- [ ] Upload sem validação de tipo nem limite de tamanho.
- [ ] A task do Celery engole exceções e grava o erro só no backend de resultados.

## Infra
- [ ] Imagem Docker grande (PyTorch com suporte a CUDA): avaliar uma imagem só-CPU menor como opção.
- [ ] Perfil de GPU (`docker-compose.gpu.yml`) não testado em máquina com NVIDIA.
- [ ] CI só roda quando o repo ficar público (cobrança do GitHub Actions em repo privado).

## Futuro
- [ ] Gerar áudio a partir do SRT.
- [ ] Editar a legenda enquanto assiste.
- [ ] Retomar Job Interrompido a partir do Bloco onde parou.
