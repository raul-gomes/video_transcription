# Transcrição ao vivo em Blocos de 30s com 2s de Sobreposição

Para a pessoa acompanhar o texto enquanto o Job anda, o áudio é cortado em Blocos de 30s e cada Bloco transcrito já grava seus Trechos, com o tempo ajustado à Mídia. Cada Bloco repete os 2s finais do anterior (Sobreposição), e os Trechos que começam dentro dessa faixa já coberta são descartados, para não cortar palavra nem duplicar texto. A tela busca os Trechos novos a cada 5s (polling), em vez de SSE ou WebSocket, para continuar no Django/DRF síncrono, sem servidor ASGI.

## Consequências

- Os Trechos do banco são a fonte da verdade: Legendas, Revisão e, no futuro, a geração de áudio e a edição durante a reprodução partem deles.
- O Vídeo legendado só é gerado no fim do Job.
