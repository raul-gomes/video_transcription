# Chave do Provedor de IA criptografada no banco local e nunca exibida

A pessoa cadastra a chave da Anthropic ou da OpenAI numa tela de configurações. A chave é guardada criptografada (Fernet) no SQLite, com uma chave de cifra gerada no primeiro uso e salva na pasta de dados do app, fora do banco. A API nunca devolve a chave, só uma máscara (`sk-…a1b2`), e para trocar a pessoa cadastra outra. Se a variável existir no `.env`, ela tem prioridade sobre a do banco.

## Opções consideradas

- Só no `.env`: mais simples, mas obriga a pessoa a editar arquivo e reiniciar o Docker para trocar de provedor.
- Banco em texto puro: descartado. Um backup ou uma cópia do `db.sqlite3` vazaria a chave.
