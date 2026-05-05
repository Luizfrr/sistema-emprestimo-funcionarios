# Sistema de Empréstimos - CRUD de Colaboradores

Projeto Flask ajustado para seguir o modelo de banco de dados da atividade, sem telas ou tabelas do antigo sistema de hotel.

## Modelo implementado

Tabelas criadas conforme o DER:

- `usuario`: `id_usuario`, `nome`, `email`, `senha`, `tipo`
- `funcionario`: `id_usuario`, `cpf`, `data_nascimento`, `endereco`
- `telefone`: telefones multivalorados do funcionário
- `email_funcionario`: e-mails adicionais multivalorados do funcionário
- `emprestimo`: empréstimos realizados por usuários
- `equipamento`: equipamentos disponíveis
- `item_emprestimo`: itens de cada empréstimo

A tela solicitada na Etapa 2 implementa CRUD de colaboradores/funcionários usando as tabelas `usuario`, `funcionario`, `telefone` e `email_funcionario`.

## Funcionalidades da tela de colaboradores

- Cadastro de novo colaborador.
- Mensagem Bootstrap de sucesso ou falha ao cadastrar.
- Após o cadastro, o sistema permanece na tela de cadastro.
- Listagem de colaboradores.
- Pesquisa por nome.
- Tela de edição parecida com a tela de cadastro, já preenchida com os dados do colaborador.
- Exclusão com modal de confirmação.
- Persistência em banco SQLite (`emprestimos.db`).

## Como executar localmente

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
python main.py
```

Depois, acesse:

```text
http://localhost:5000
```

O banco é criado automaticamente na primeira execução.

## Como executar com Docker

```bash
docker build -t sistema-emprestimos .
docker run -p 5000:5000 sistema-emprestimos
```

Depois, acesse:

```text
http://localhost:5000
```

## Controle de versão

Exemplo de envio para GitHub:

```bash
git init
git add .
git commit -m "Ajusta projeto para sistema de emprestimos"
git branch -M main
git remote add origin URL_DO_REPOSITORIO
git push -u origin main
```
