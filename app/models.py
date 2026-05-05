from app import db


class Usuario(db.Model):
    __tablename__ = 'usuario'

    id_usuario = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True)
    senha = db.Column(db.String(255), nullable=False)
    tipo = db.Column(db.String(30), nullable=False, default='FUNCIONARIO')

    funcionario = db.relationship(
        'Funcionario',
        back_populates='usuario',
        cascade='all, delete-orphan',
        uselist=False,
    )
    emprestimos = db.relationship('Emprestimo', back_populates='usuario', cascade='all, delete-orphan')


class Funcionario(db.Model):
    __tablename__ = 'funcionario'

    id_usuario = db.Column(
        db.Integer,
        db.ForeignKey('usuario.id_usuario', ondelete='CASCADE'),
        primary_key=True,
    )
    cpf = db.Column(db.String(14), nullable=False, unique=True)
    data_nascimento = db.Column(db.Date, nullable=False)
    endereco = db.Column(db.String(150), nullable=False)

    usuario = db.relationship('Usuario', back_populates='funcionario')
    telefones = db.relationship('Telefone', back_populates='funcionario', cascade='all, delete-orphan')
    emails = db.relationship('EmailFuncionario', back_populates='funcionario', cascade='all, delete-orphan')


class Telefone(db.Model):
    __tablename__ = 'telefone'

    id_telefone = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('funcionario.id_usuario', ondelete='CASCADE'), nullable=False)
    numero = db.Column(db.String(20), nullable=False)

    funcionario = db.relationship('Funcionario', back_populates='telefones')


class EmailFuncionario(db.Model):
    __tablename__ = 'email_funcionario'

    id_email = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('funcionario.id_usuario', ondelete='CASCADE'), nullable=False)
    email = db.Column(db.String(120), nullable=False)

    funcionario = db.relationship('Funcionario', back_populates='emails')


class Emprestimo(db.Model):
    __tablename__ = 'emprestimo'

    id_emprestimo = db.Column(db.Integer, primary_key=True)
    data_hora_inicio = db.Column(db.DateTime, nullable=False)
    data_hora_fim_prevista = db.Column(db.DateTime, nullable=False)
    data_hora_fim_real = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='ATIVO')
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuario.id_usuario', ondelete='CASCADE'), nullable=False)

    usuario = db.relationship('Usuario', back_populates='emprestimos')
    itens = db.relationship('ItemEmprestimo', back_populates='emprestimo', cascade='all, delete-orphan')


class Equipamento(db.Model):
    __tablename__ = 'equipamento'

    id_equipamento = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(80), nullable=False)
    marca = db.Column(db.String(80), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    quantidade_total = db.Column(db.Integer, nullable=False)
    tamanho = db.Column(db.String(50), nullable=True)
    peso = db.Column(db.String(50), nullable=True)
    validade = db.Column(db.Date, nullable=True)

    itens = db.relationship('ItemEmprestimo', back_populates='equipamento')


class ItemEmprestimo(db.Model):
    __tablename__ = 'item_emprestimo'

    id_item = db.Column(db.Integer, primary_key=True)
    quantidade = db.Column(db.Integer, nullable=False)
    observacao = db.Column(db.Text, nullable=True)
    id_emprestimo = db.Column(db.Integer, db.ForeignKey('emprestimo.id_emprestimo', ondelete='CASCADE'), nullable=False)
    id_equipamento = db.Column(db.Integer, db.ForeignKey('equipamento.id_equipamento'), nullable=False)

    emprestimo = db.relationship('Emprestimo', back_populates='itens')
    equipamento = db.relationship('Equipamento', back_populates='itens')


# Compatibilidade com nomes usados anteriormente na tela.
Funcionario.telefones_rel = Funcionario.telefones
Funcionario.emails_rel = Funcionario.emails
