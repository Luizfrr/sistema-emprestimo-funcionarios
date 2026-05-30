# Documentação LAB 09 - Controle de EPI

## Objetivo da etapa

Nesta etapa final do projeto Controle de EPI foram implementadas as funcionalidades de autenticação, logout, controle de acesso por usuário logado, controle de usuários e conexão com banco de dados MySQL utilizando migrações.

## Funcionalidades obrigatórias atendidas

### Tela base
O sistema possui um template base reutilizado pelas demais telas, com menu lateral, identificação do usuário logado e navegação entre as funcionalidades disponíveis conforme o perfil do usuário.

### Gerenciamento de colaboradores
O sistema permite cadastrar, listar, editar e excluir colaboradores. Os campos possuem validações e formatações, incluindo CPF/CNPJ, e-mail e telefone.

### Gerenciamento de EPIs
O sistema permite cadastrar, listar, editar e excluir equipamentos de proteção individual, controlando quantidade total e quantidade disponível.

### Entrega de EPI
O sistema permite registrar a entrega/empréstimo de EPI para um colaborador, com data prevista de devolução posterior à data e hora atuais, seleção de equipamentos e validação de estoque.

### Relatórios de EPI
O sistema possui tela de relatórios/listagem histórica dos empréstimos, mostrando colaborador, EPIs, datas, status e filtros por colaborador, equipamento e status.

### Atualização de empréstimo de EPI
O sistema permite atualizar o status do empréstimo. Os campos de colaborador, equipamento, quantidade, data de empréstimo e data prevista ficam bloqueados durante a edição, conforme requisito.

### Login
O sistema possui tela de login com e-mail e senha. As senhas são armazenadas com hash. Também existe tela de cadastro público; todo cadastro feito por ela entra automaticamente como perfil USUARIO.

### Logout
O sistema possui funcionalidade de logout que encerra a sessão do usuário.

### Controle de usuário
O sistema possui controle de usuários com perfis. A tela administrativa de usuários cria usuários comuns; colaboradores são criados pela tela de Colaboradores:

- ADMIN: acesso total ao sistema, incluindo gerenciamento de usuários.
- USUARIO: pode apenas pedir empréstimo e visualizar seus próprios empréstimos.
- COLABORADOR: não acessa dashboard; registra e edita apenas seus próprios EPIs e registra/consulta seus próprios empréstimos.

Nenhum usuário deslogado consegue acessar as telas internas do sistema.

## Controle de acesso

Todas as rotas internas são protegidas por verificação de sessão. Caso o usuário não esteja logado, ele é redirecionado para a tela de login.

O menu lateral também é exibido conforme o perfil do usuário logado. Administradores acessam tudo, colaboradores acessam apenas seus próprios EPIs e seus próprios empréstimos; usuários acessam apenas pedido e consulta de seus próprios empréstimos, sem acesso ao gerenciamento de usuários.

## Banco de dados MySQL

O sistema está configurado para usar MySQL através da variável `DATABASE_URL` no arquivo `.env`.

Exemplo:

```env
SECRET_KEY=troque-esta-chave
DATABASE_URL=mysql+pymysql://root:senha@localhost:3306/controle_epi
```

Antes de rodar as migrações, o banco deve ser criado no MySQL:

```sql
CREATE DATABASE controle_epi CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

## Migrações

O projeto utiliza Flask-Migrate/Alembic para criação e atualização das tabelas.

Comandos principais:

```powershell
flask --app main.py db upgrade
python create_admin.py
python main.py
```

## Usuário administrador inicial

O projeto possui script para criação do usuário administrador inicial:

- E-mail: admin@exemplo.com
- Senha: admin123

Após o primeiro acesso, recomenda-se alterar a senha.

## Relações entre tabelas

As tabelas possuem relações com chaves primárias e estrangeiras:

- usuario: armazena os dados de login e perfil.
- funcionario: usa `id_usuario` como chave primária e estrangeira para usuario.
- telefone: vinculado ao colaborador.
- email_funcionario: vinculado ao colaborador.
- equipamento: armazena os EPIs.
- emprestimo: vinculado ao usuário/colaborador.
- item_emprestimo: vincula empréstimos aos equipamentos.

Essas relações permitem controlar corretamente qual colaborador recebeu cada EPI e quais equipamentos fazem parte de cada empréstimo.


## Regras finais de acesso

- O perfil **COLABORADOR** não acessa o Dashboard.
- O perfil **COLABORADOR** acessa somente:
  - **Meus Equipamentos**: equipamentos cadastrados pelo próprio usuário;
  - **Meus Empréstimos**: empréstimos vinculados ao próprio usuário;
  - **Pedir Empréstimo**: novo empréstimo vinculado automaticamente ao próprio colaborador.
- O colaborador só pode editar equipamentos que ele mesmo cadastrou.
- O colaborador não consegue visualizar, editar ou acessar diretamente pela URL equipamentos e empréstimos de outros colaboradores.
- O perfil **ADMIN** tem visão geral e cria usuários comuns na tela Usuários. O perfil **USUARIO** é restrito a pedir empréstimo e ver seus próprios empréstimos. Novos cadastros públicos e novos cadastros pela tela Usuários entram sempre como **USUARIO**.
