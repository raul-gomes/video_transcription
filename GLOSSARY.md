# Video Transcription

App local que transforma a fala de um vídeo ou áudio em legendas e texto, com revisão opcional por IA. Roda na máquina de quem usa, para uma pessoa só.

## Mídia e processamento

**Mídia**:
O arquivo de vídeo ou áudio que a pessoa envia para transcrever.
_Evite_: arquivo, upload, vídeo (quando também pode ser áudio)

**Job**:
Um pedido de transcrição de uma Mídia, do envio até o fim, com status e progresso próprios.
_Evite_: tarefa, processo, transcrição (como sinônimo do pedido)

**Bloco**:
Um pedaço de 30 segundos do áudio da Mídia, transcrito de cada vez para que o texto apareça enquanto o Job anda.
_Evite_: chunk, parte, fatia

**Sobreposição**:
Os segundos que um Bloco repete do Bloco anterior para não cortar uma palavra ao meio.
_Evite_: overlap, margem

**Trecho**:
Uma frase com tempo de início e fim, como o Whisper devolve. É a unidade da legenda e a fonte da verdade do texto.
_Evite_: segmento, linha, legenda (para um item só)

**Dispositivo**:
Onde o Whisper roda num Job: CPU, GPU ou Automático.
_Evite_: hardware, aceleração

**Modelo de transcrição**:
O tamanho do Whisper escolhido para o Job (tiny, base, small, medium, large).
_Evite_: modelo (sozinho, porque confunde com o modelo de LLM)

## Status do Job

**Na fila**:
O Job foi criado e espera um worker livre.

**Interrompido**:
O Job estava em andamento quando o app parou. Só sai desse estado se a pessoa pedir para reprocessar.
_Evite_: falho (falho é erro durante o processamento)

**Cancelado**:
A pessoa mandou parar o Job. Os Trechos já transcritos ficam.

## Saídas

**Legenda**:
O arquivo de legenda gerado a partir dos Trechos (SRT ou VTT).

**Transcrição**:
O texto corrido dos Trechos, sem tempos (TXT).

**Vídeo legendado**:
A Mídia de vídeo com a Legenda embutida como faixa que o player liga e desliga.
_Evite_: vídeo final, vídeo processado

## Revisão por IA

**Revisão**:
Uma passada da IA sobre os Trechos de um Job terminado, que gera Sugestões. É opcional e começa só quando a pessoa pede.
_Evite_: correção, ai_revision (fora do código)

**Sugestão**:
Uma proposta da IA de novo texto para um Trecho, com o motivo. Fica pendente até a pessoa aceitar ou recusar.
_Evite_: correção, edição

**Contexto do vídeo**:
O texto opcional em que a pessoa conta o assunto e lista nomes e termos para orientar a Revisão.
_Evite_: prompt, glossário (este arquivo é o glossário do projeto)

**Provedor de IA**:
O serviço de LLM que faz a Revisão: Anthropic, OpenAI ou Ollama.
_Evite_: modelo, API

**Versão revisada**:
As Legendas e a Transcrição geradas com as Sugestões aceitas. Ficam ao lado das originais, que nunca são apagadas.
_Evite_: versão corrigida, versão final
