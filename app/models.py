from app import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash


STATUS_CADASTRO_EMPRESTIMO = ['EMPRESTADO', 'FORNECIDO']
STATUS_EDICAO_EMPRESTIMO = ['EMPRESTADO', 'FORNECIDO', 'DEVOLVIDO', 'DANIFICADO', 'PERDIDO']
STATUS_COM_DEVOLUCAO = ['DEVOLVIDO', 'DANIFICADO', 'PERDIDO']
STATUS_BAIXA_ESTOQUE = ['EMPRESTADO', 'FORNECIDO', 'DANIFICADO', 'PERDIDO']



class Usuario(db.Model):
    __tablename__ = 'usuario'

    id_usuario = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True)
    senha = db.Column(db.String(255), nullable=False)
    tipo = db.Column(db.String(30), nullable=False, default='USUARIO')
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.now)
    ultimo_login = db.Column(db.DateTime, nullable=True)

    funcionario = db.relationship(
        'Funcionario',
        back_populates='usuario',
        cascade='all, delete-orphan',
        uselist=False,
    )
    emprestimos = db.relationship('Emprestimo', back_populates='usuario', cascade='all, delete-orphan')
    equipamentos_criados = db.relationship('Equipamento', back_populates='criador')

    @property
    def is_admin(self):
        return self.tipo == 'ADMIN'

    def definir_senha(self, senha_plana):
        self.senha = generate_password_hash(senha_plana)

    def conferir_senha(self, senha_plana):
        if not self.senha:
            return False
        # Compatibilidade com os usuários antigos que estavam com senha em texto puro.
        if self.senha.startswith(('pbkdf2:', 'scrypt:')):
            return check_password_hash(self.senha, senha_plana)
        return self.senha == senha_plana


class Funcionario(db.Model):
    __tablename__ = 'funcionario'

    id_usuario = db.Column(
        db.Integer,
        db.ForeignKey('usuario.id_usuario', ondelete='CASCADE'),
        primary_key=True,
    )
    cpf = db.Column(db.String(18), nullable=False, unique=True)  # CPF ou CNPJ
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
    data_hora_inicio = db.Column(db.DateTime, nullable=False, default=datetime.now)
    data_hora_fim_prevista = db.Column(db.DateTime, nullable=False)
    data_hora_fim_real = db.Column(db.DateTime, nullable=True)
    observacao_devolucao = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='EMPRESTADO')
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuario.id_usuario', ondelete='CASCADE'), nullable=False)

    usuario = db.relationship('Usuario', back_populates='emprestimos')
    itens = db.relationship('ItemEmprestimo', back_populates='emprestimo', cascade='all, delete-orphan')
    
    @property
    def status_display(self):
        status_map = {
            'EMPRESTADO': 'Emprestado',
            'FORNECIDO': 'Fornecido',
            'DEVOLVIDO': 'Devolvido',
            'DANIFICADO': 'Danificado',
            'PERDIDO': 'Perdido'
        }
        return status_map.get(self.status, self.status)

    @property
    def exige_devolucao(self):
        return self.status in STATUS_COM_DEVOLUCAO
    
    @property
    def pode_finalizar(self):
        return self.status == 'EMPRESTADO'
    
    def verificar_atraso(self):
        # A atividade avaliativa não pede um status "atrasado".
        # Mantido apenas para compatibilidade com chamadas antigas.
        return False


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
    id_usuario_criador = db.Column(db.Integer, db.ForeignKey('usuario.id_usuario'), nullable=True)

    criador = db.relationship('Usuario', back_populates='equipamentos_criados')
    itens = db.relationship('ItemEmprestimo', back_populates='equipamento')
    
    @property
    def quantidade_disponivel(self):
        emprestado = db.session.query(db.func.sum(ItemEmprestimo.quantidade)).join(
            Emprestimo, ItemEmprestimo.id_emprestimo == Emprestimo.id_emprestimo
        ).filter(
            ItemEmprestimo.id_equipamento == self.id_equipamento,
            Emprestimo.status.in_(STATUS_BAIXA_ESTOQUE)
        ).scalar() or 0
        return self.quantidade_total - emprestado


class ItemEmprestimo(db.Model):
    __tablename__ = 'item_emprestimo'

    id_item = db.Column(db.Integer, primary_key=True)
    quantidade = db.Column(db.Integer, nullable=False)
    observacao = db.Column(db.Text, nullable=True)
    id_emprestimo = db.Column(db.Integer, db.ForeignKey('emprestimo.id_emprestimo', ondelete='CASCADE'), nullable=False)
    id_equipamento = db.Column(db.Integer, db.ForeignKey('equipamento.id_equipamento'), nullable=False)

    emprestimo = db.relationship('Emprestimo', back_populates='itens')
    equipamento = db.relationship('Equipamento', back_populates='itens')


Funcionario.telefones_rel = Funcionario.telefones
Funcionario.emails_rel = Funcionario.emails