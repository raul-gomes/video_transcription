# Análise da Mídia antes da fila e Prévia separada do arquivo final

Arquivos reais trazem várias Faixas de áudio e codecs que o navegador não toca (caso real: MKV com duas faixas E-AC-3 5.1, sem som no player). Por isso todo upload passa por uma Análise da Mídia (ffprobe) e o Job fica "Aguardando sua decisão" até a pessoa confirmar, num modal, a Faixa de áudio, o idioma e se quer uma Prévia. Quem diz se um codec toca é o próprio navegador (`canPlayType`), não uma lista fixa. A Prévia é um arquivo separado (imagem copiada + áudio convertido para AAC estéreo) usado só pelo player, e o Vídeo legendado para download mantém a imagem e todas as Faixas de áudio e legendas originais, sem conversão.

## Opções consideradas

- Áudio convertido separado, tocando junto com o vídeo mudo: ocupa ~20 MB em vez do tamanho do vídeo, mas dessincroniza em pausas e avanços. Descartado por confiabilidade.
- Converter a imagem sempre: resolve HEVC/AV1, mas pode demorar mais que a transcrição. Fica como opção desmarcada no modal.
- Analisar no navegador antes do upload: o navegador não lê as faixas de um MKV de forma confiável.
