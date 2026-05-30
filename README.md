# Sistema de Controle de EPI - LAB 09

Projeto Flask para controle de colaboradores, EPIs, entrega/empréstimo, relatórios, atualização de empréstimos e, nesta etapa, login/logout com controle de acesso.

## Funcionalidades da etapa final

- Login com e-mail e senha.
- Cadastro público de conta, sempre como perfil USUÁRIO.
- Logout.
- Bloqueio de todas as telas internas para usuários deslogados.
- Controle de usuários para administradores.
- Senhas gravadas com hash usando Werkzeug.
- Usuário administrador inicial.
- Configuração por `.env` para conexão com MySQL.
- Flask-Migrate/Alembic para migrações.
- Compatibilidade com banco antigo das etapas anteriores.

## Usuário inicial

Ao iniciar o sistema, se ainda não existir usuário administrador, ele será criado automaticamente:

- E-mail: `admin@exemplo.com`
- Senha: `admin123`

Depois de entrar, acesse o menu **Usuários** para criar usuários comuns. Colaboradores devem ser criados no menu **Colaboradores**.

## Como rodar no Windows

Dentro da pasta do projeto:

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Acesse no navegador:

```text
http://127.0.0.1:5000
```

## Configuração com MySQL

1. Crie o banco no MySQL:

```sql
CREATE DATABASE controle_epi CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

2. Copie o arquivo `.env.example` para `.env`.

3. Ajuste a linha `DATABASE_URL` conforme seu usuário e senha do MySQL:

```env
DATABASE_URL=mysql+pymysql://root:senha@localhost:3306/controle_epi
```

Exemplo se o MySQL não tiver senha:

```env
DATABASE_URL=mysql+pymysql://root:@localhost:3306/controle_epi
```

4. Rode as migrações:

```powershell
flask --app main.py db upgrade
python create_admin.py
python main.py
```

> Observação: se você não criar o `.env`, o sistema usa SQLite como fallback para facilitar testes locais. Para a entrega do LAB 09, configure o `.env` com MySQL.

## Rotas principais

- `/login` - Login
- `/logout` - Logout
- `/cadastro` - Cadastro público de usuário comum
- `/dashboard` - Tela inicial protegida
- `/colaboradores` - Gerenciamento de colaboradores
- `/equipamentos` - Gerenciamento de EPIs
- `/emprestimos` - Relatórios/listagem de empréstimos
- `/emprestimos/novo` - Entrega de EPI
- `/usuarios` - Controle de usuários, somente ADMIN

## Status dos empréstimos

O sistema usa os status exigidos na atividade:

- Emprestado
- Fornecido
- Devolvido
- Danificado
- Perdido

No cadastro aparecem apenas **Emprestado** e **Fornecido**. Na edição aparecem todos os status. Os campos de devolução aparecem somente para **Devolvido**, **Danificado** e **Perdido**.


## Evidência para entrega do LAB 09

Para comprovar que o projeto está usando MySQL na etapa final, mantenha um arquivo `.env` configurado com `DATABASE_URL=mysql+pymysql://...` antes de executar o sistema.

Fluxo recomendado para apresentação:

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
flask --app main.py db upgrade
python create_admin.py
python main.py
```

O arquivo `DOCUMENTACAO_LAB09.md` resume as funcionalidades implementadas, o controle de acesso, as relações entre tabelas e os comandos de migração.


## Regras finais de acesso

- O perfil **COLABORADOR** não acessa o Dashboard.
- O perfil **COLABORADOR** acessa somente:
  - **Meus Equipamentos**: equipamentos cadastrados pelo próprio usuário;
  - **Meus Empréstimos**: empréstimos vinculados ao próprio usuário;
  - **Pedir Empréstimo**: novo empréstimo vinculado automaticamente ao próprio colaborador.
- O colaborador só pode editar equipamentos que ele mesmo cadastrou.
- O colaborador não consegue visualizar, editar ou acessar diretamente pela URL equipamentos e empréstimos de outros colaboradores.
- O perfil **ADMIN** tem visão geral e cria usuários comuns na tela Usuários. O perfil **USUARIO** é restrito a pedir empréstimo e ver seus próprios empréstimos. Novos cadastros públicos e novos cadastros pela tela Usuários entram sempre como **USUARIO**.
