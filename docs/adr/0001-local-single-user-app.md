# App local, de uma pessoa só, sem login

O app é baixado e roda na máquina de quem usa, com `docker compose up`. Não tem login nem contas: tudo o que está no banco é da pessoa que roda o app. Para compensar a falta de autenticação, o servidor escuta só em `127.0.0.1`. Expor na rede exige mudar isso de propósito no `.env`, e a documentação avisa que, com isso, qualquer pessoa na rede usa a chave de IA cadastrada.

## Opções consideradas

- Login do Django com dados separados por usuário: descartado porque não há mais de uma pessoa usando a mesma instalação.
- Banco SQLite em vez de Postgres: escolhido porque é um arquivo local e não exige um serviço a mais.
