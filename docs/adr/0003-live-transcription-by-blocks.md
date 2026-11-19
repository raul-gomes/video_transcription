# Transcrição ao vivo em Blocos de 30s com 2s de Sobreposição

Para a pessoa acompanhar o texto enquanto o Job anda, o áudio extraído é carregado uma vez e transcrito em fatias de 30s (Blocos). Cada Bloco repete os 2s finais do anterior (Sobreposição) e já grava seus Trechos, com o tempo ajustado à Mídia. A tela busca os Trechos novos a cada 5s (polling), em vez de SSE ou WebSocket, para continuar no Django/DRF síncrono, sem servidor ASGI.

Refinado no grilling de 2026-11-19, antes da implementação:

- **Fronteira da transcrição:** um Trecho novo só entra se começar depois do fim do último Trecho aceito. Usar o fim do último Trecho, e não o corte fixo de 30s, evita repetir ou perder a palavra que atravessa o corte.
- **Contexto entre Blocos:** cada Bloco recebe como `initial_prompt` os últimos ~200 caracteres do texto do anterior, para manter nomes e grafia.
- **Idioma no Automático:** detectado no primeiro Bloco com fala, fixado nos seguintes e gravado no Job. Detectar em todo Bloco poderia trocar o idioma no meio da Mídia.
- **Legendas parciais:** depois de cada Bloco, o SRT e o VTT são regravados com o que já saiu; JSON, TXT e o Vídeo legendado só no fim. O progresso avança por Bloco ("Transcrevendo bloco N de M").
- **Cancelar e falhar:** o Whisper não para no meio de um Bloco, então o cancelamento vale ao fim do Bloco atual. Um Job cancelado ou falho mantém os Trechos e o SRT parcial até ali. Reprocessar recomeça do zero.
- **Player:** o play fica liberado desde o primeiro Trecho; ao chegar na Fronteira da transcrição ele pausa ("Aguardando a transcrição…") e retoma quando houver pelo menos 3s à frente. Se a pessoa adiantar além da Fronteira, a pausa automática fica desligada até ela voltar para trás dela. A trilha de legenda é trocada pela VTT parcial nova a cada Bloco.
- **Ordem:** a Prévia continua antes da transcrição, porque o player precisa dela para acompanhar a legenda.

## Consequências

- Os Trechos do banco são a fonte da verdade: Legendas, Revisão e, no futuro, a geração de áudio e a edição durante a reprodução partem deles.
- O Vídeo legendado só é gerado no fim do Job.
- O cancelamento pode levar até a duração de um Bloco para valer.
- Blocos curtos podem aumentar frases inventadas pelo Whisper em silêncio; os filtros padrão dele ficam como estão até um teste com Mídia real.
