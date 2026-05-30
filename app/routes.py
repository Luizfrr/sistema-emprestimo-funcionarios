from datetime import datetime
import re
from flask import flash, redirect, render_template, request, url_for, session, jsonify
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text, inspect
from functools import wraps

from app import app, db
from app.models import (
    EmailFuncionario, Funcionario, Telefone, Usuario, Equipamento,
    Emprestimo, ItemEmprestimo, STATUS_CADASTRO_EMPRESTIMO,
    STATUS_EDICAO_EMPRESTIMO, STATUS_COM_DEVOLUCAO
)


def _date(value):
    return datetime.strptime(value, '%Y-%m-%d').date() if value else None


def _datetime(value):
    return datetime.strptime(value, '%Y-%m-%dT%H:%M') if value else None


def _items(value):
    return [v.strip() for v in (value or '').split(',') if v.strip()]


def _somente_digitos(value):
    return re.sub(r'\D', '', value or '')


def _formatar_cpf_cnpj(value):
    digitos = _somente_digitos(value)
    if len(digitos) == 11:
        return f'{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}'
    if len(digitos) == 14:
        return f'{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:]}'
    return value or ''


def _cpf_cnpj_formato_valido(value):
    # Para a atividade, a exigência é aceitar e formatar CPF/CNPJ.
    # Não bloqueia por dígito verificador; valida apenas a quantidade de números.
    return len(_somente_digitos(value)) in (11, 14)


def _email_valido(value):
    return bool(re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', value or ''))


def _telefone_valido(value):
    digitos = _somente_digitos(value)
    return len(digitos) in (10, 11)


def _formatar_telefone(value):
    digitos = _somente_digitos(value)
    if len(digitos) == 11:
        return f'({digitos[:2]}) {digitos[2:7]}-{digitos[7:]}'
    if len(digitos) == 10:
        return f'({digitos[:2]}) {digitos[2:6]}-{digitos[6:]}'
    return value or ''


def _validar_dados_pessoa(nome, email_login, cpf=None, telefones=None, emails_adicionais=None, senha=None, exigir_senha=False):
    erros = []
    if not nome or len(nome) < 3:
        erros.append('Informe um nome com pelo menos 3 caracteres.')
    if not _email_valido(email_login):
        erros.append('Informe um e-mail de login válido.')
    if cpf is not None and not _cpf_cnpj_formato_valido(cpf):
        erros.append('Informe um CPF ou CNPJ com 11 ou 14 números.')
    if exigir_senha and (not senha or len(senha) < 6):
        erros.append('A senha deve possuir pelo menos 6 caracteres.')
    for telefone in telefones or []:
        if not _telefone_valido(telefone):
            erros.append(f'Telefone inválido: {telefone}. Use DDD + número.')
    for email in emails_adicionais or []:
        if not _email_valido(email):
            erros.append(f'E-mail adicional inválido: {email}.')
    return erros


def usuario_atual():
    usuario_id = session.get('usuario_id')
    return Usuario.query.get(usuario_id) if usuario_id else None


def perfil_operacional():
    return session.get('usuario_tipo') == 'ADMIN'


def perfil_colaborador():
    return session.get('usuario_tipo') == 'COLABORADOR'


def perfil_pode_cadastrar_epi():
    return session.get('usuario_tipo') in ['ADMIN', 'COLABORADOR']


def perfil_pode_emprestimo():
    return session.get('usuario_tipo') in ['ADMIN', 'COLABORADOR', 'USUARIO']


def rota_inicial_usuario():
    if session.get('usuario_tipo') in ['COLABORADOR', 'USUARIO']:
        return 'listar_emprestimos'
    return 'dashboard'


def _consulta_equipamentos_com_acesso():
    consulta = Equipamento.query
    if session.get('usuario_tipo') == 'COLABORADOR':
        consulta = consulta.filter(Equipamento.id_usuario_criador == session.get('usuario_id'))
    elif session.get('usuario_tipo') == 'USUARIO':
        consulta = consulta.filter(False)
    return consulta


def _garantir_acesso_equipamento(equipamento):
    if session.get('usuario_tipo') == 'USUARIO':
        flash('Acesso negado. Usuário comum não gerencia equipamentos.', 'danger')
        return False
    if session.get('usuario_tipo') == 'COLABORADOR' and equipamento.id_usuario_criador != session.get('usuario_id'):
        flash('Acesso negado. Você só pode acessar equipamentos cadastrados por você.', 'danger')
        return False
    return True


def _consulta_emprestimos_com_acesso():
    consulta = Emprestimo.query.join(Usuario)
    if session.get('usuario_tipo') in ['COLABORADOR', 'USUARIO']:
        consulta = consulta.filter(Emprestimo.id_usuario == session.get('usuario_id'))
    return consulta


def _garantir_acesso_emprestimo(emprestimo):
    if session.get('usuario_tipo') in ['COLABORADOR', 'USUARIO'] and emprestimo.id_usuario != session.get('usuario_id'):
        flash('Acesso negado. Você só pode visualizar seus próprios empréstimos.', 'danger')
        return False
    return True


def _migrar_banco_emprestimo():
    """
    Compatibilidade simples para bancos antigos usados nas etapas anteriores.
    As migrações oficiais do LAB 09 ficam na pasta migrations/.
    """
    try:
        inspector = inspect(db.engine)
        if not inspector.has_table('emprestimo'):
            return

        colunas_emprestimo = [col['name'] for col in inspector.get_columns('emprestimo')]
        colunas_usuario = [col['name'] for col in inspector.get_columns('usuario')] if inspector.has_table('usuario') else []
        colunas_equipamento = [col['name'] for col in inspector.get_columns('equipamento')] if inspector.has_table('equipamento') else []
        dialect = db.engine.dialect.name

        if 'observacao_devolucao' not in colunas_emprestimo:
            db.session.execute(text('ALTER TABLE emprestimo ADD COLUMN observacao_devolucao TEXT'))

        if inspector.has_table('equipamento') and 'id_usuario_criador' not in colunas_equipamento:
            if dialect == 'mysql':
                db.session.execute(text('ALTER TABLE equipamento ADD COLUMN id_usuario_criador INT NULL'))
            else:
                db.session.execute(text('ALTER TABLE equipamento ADD COLUMN id_usuario_criador INTEGER'))

        if inspector.has_table('funcionario'):
            try:
                if dialect == 'mysql':
                    db.session.execute(text('ALTER TABLE funcionario MODIFY COLUMN cpf VARCHAR(18) NOT NULL'))
            except Exception as erro:
                print(f'Aviso: ajuste CPF/CNPJ ignorado: {erro}')

        if inspector.has_table('usuario'):
            if 'ativo' not in colunas_usuario:
                tipo_boolean = 'TINYINT(1)' if dialect == 'mysql' else 'BOOLEAN'
                db.session.execute(text(f'ALTER TABLE usuario ADD COLUMN ativo {tipo_boolean} NOT NULL DEFAULT 1'))
            if 'criado_em' not in colunas_usuario:
                tipo_datetime = 'DATETIME'
                db.session.execute(text(f'ALTER TABLE usuario ADD COLUMN criado_em {tipo_datetime}'))
            if 'ultimo_login' not in colunas_usuario:
                db.session.execute(text('ALTER TABLE usuario ADD COLUMN ultimo_login DATETIME'))

        if inspector.has_table('usuario'):
            db.session.execute(text("UPDATE usuario SET tipo = 'COLABORADOR' WHERE tipo = 'FUNCIONARIO'"))
            db.session.execute(text("UPDATE usuario SET tipo = 'USUARIO' WHERE tipo = 'OPERADOR'"))

        # Converte status antigos para os status exigidos pela atividade avaliativa.
        db.session.execute(text("UPDATE emprestimo SET status = 'EMPRESTADO' WHERE status IN ('ATIVO', 'ATRASADO')"))
        db.session.execute(text("UPDATE emprestimo SET status = 'DEVOLVIDO' WHERE status = 'FINALIZADO'"))
        db.session.execute(text("UPDATE emprestimo SET status = 'PERDIDO' WHERE status = 'CANCELADO'"))
        db.session.commit()
    except Exception as erro:
        db.session.rollback()
        print(f'Aviso: migração automática ignorada: {erro}')

def _datetime_local(value):
    return value.strftime('%Y-%m-%dT%H:%M') if value else ''

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            flash('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            flash('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('login', next=request.path))
        if session.get('usuario_tipo') != 'ADMIN':
            flash('Acesso negado. Esta área é exclusiva para administradores.', 'danger')
            return redirect(url_for(rota_inicial_usuario()))
        return f(*args, **kwargs)
    return decorated_function


def operacional_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            flash('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('login', next=request.path))
        if not perfil_operacional():
            flash('Acesso negado. Esta ação é permitida apenas para administrador.', 'danger')
            return redirect(url_for('listar_emprestimos'))
        return f(*args, **kwargs)
    return decorated_function


def epi_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            flash('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('login', next=request.path))
        if not perfil_pode_cadastrar_epi():
            flash('Acesso negado. Esta área é permitida para administrador ou colaborador.', 'danger')
            return redirect(url_for(rota_inicial_usuario()))
        return f(*args, **kwargs)
    return decorated_function


def emprestimo_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            flash('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('login', next=request.path))
        if not perfil_pode_emprestimo():
            flash('Acesso negado. Esta área é permitida para administrador, colaborador ou usuário.', 'danger')
            return redirect(url_for(rota_inicial_usuario()))
        return f(*args, **kwargs)
    return decorated_function


def perfil_pode_alterar_emprestimo():
    return session.get('usuario_tipo') in ['ADMIN', 'COLABORADOR']


@app.context_processor
def variaveis_globais():
    return dict(perfil_operacional=perfil_operacional(), perfil_colaborador=perfil_colaborador(), perfil_pode_cadastrar_epi=perfil_pode_cadastrar_epi(), perfil_pode_emprestimo=perfil_pode_emprestimo(), perfil_pode_alterar_emprestimo=perfil_pode_alterar_emprestimo(), usuario_atual=usuario_atual())


@app.before_request
def criar_banco():
    db.create_all()
    _migrar_banco_emprestimo()
    
    # Criar usuário admin se não existir
    admin = Usuario.query.filter_by(email='admin@exemplo.com').first()
    if not admin:
        admin = Usuario(
            nome='Administrador',
            email='admin@exemplo.com',
            senha='',
            tipo='ADMIN',
            ativo=True
        )
        admin.definir_senha('admin123')
        db.session.add(admin)
        db.session.commit()
        print("Usuário admin criado automaticamente!")


@app.route('/')
def home():
    if 'usuario_id' in session:
        return redirect(url_for(rota_inicial_usuario()))
    return redirect(url_for('login'))


@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro_usuario():
    if 'usuario_id' in session:
        return redirect(url_for(rota_inicial_usuario()))

    if request.method == 'POST':
        dados = request.form
        try:
            nome = dados.get('nome', '').strip()
            email = dados.get('email', '').strip().lower()
            senha = dados.get('senha', '').strip()
            confirmar_senha = dados.get('confirmar_senha', '').strip()

            if not all([nome, email, senha, confirmar_senha]):
                flash('Preencha nome, e-mail, senha e confirmação de senha.', 'danger')
                return render_template('cadastro.html', form=dados)

            if senha != confirmar_senha:
                flash('A confirmação de senha não confere.', 'danger')
                return render_template('cadastro.html', form=dados)

            erros = _validar_dados_pessoa(nome, email, senha=senha, exigir_senha=True)
            if erros:
                for erro in erros:
                    flash(erro, 'danger')
                return render_template('cadastro.html', form=dados)

            usuario = Usuario(nome=nome, email=email, senha='', tipo='USUARIO', ativo=True)
            usuario.definir_senha(senha)
            db.session.add(usuario)
            db.session.commit()

            flash('Cadastro realizado com sucesso. Agora faça login.', 'success')
            return redirect(url_for('login'))
        except IntegrityError:
            db.session.rollback()
            flash('Já existe um usuário com este e-mail.', 'danger')
        except Exception as erro:
            db.session.rollback()
            flash(f'Falha ao realizar cadastro: {erro}', 'danger')

    return render_template('cadastro.html', form={})


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        senha = request.form.get('senha', '').strip()
        
        usuario = Usuario.query.filter_by(email=email).first()

        if usuario and usuario.ativo and usuario.conferir_senha(senha):
            # Se a senha antiga estava em texto puro, atualiza para hash após o primeiro login.
            if not usuario.senha.startswith(('pbkdf2:', 'scrypt:')):
                usuario.definir_senha(senha)
            usuario.ultimo_login = datetime.now()
            db.session.commit()

            session['usuario_id'] = usuario.id_usuario
            session['usuario_nome'] = usuario.nome
            session['usuario_email'] = usuario.email
            session['usuario_tipo'] = usuario.tipo
            flash(f'Bem-vindo, {usuario.nome}!', 'success')
            destino = request.args.get('next') or url_for(rota_inicial_usuario())
            return redirect(destino)

        flash('E-mail ou senha inválidos ou usuário inativo.', 'danger')
    
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    session.clear()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    if session.get('usuario_tipo') in ['COLABORADOR', 'USUARIO']:
        flash('Seu perfil não acessa o dashboard. Use as opções disponíveis no menu.', 'warning')
        return redirect(url_for('listar_emprestimos'))

    total_funcionarios = Funcionario.query.count()
    total_equipamentos = Equipamento.query.count()
    emprestimos_ativos = Emprestimo.query.filter(Emprestimo.status.in_(['EMPRESTADO', 'FORNECIDO'])).count()
    emprestimos_devolvidos = Emprestimo.query.filter_by(status='DEVOLVIDO').count()
    ultimos_emprestimos = Emprestimo.query.order_by(Emprestimo.id_emprestimo.desc()).limit(5).all()
    
    #equipamentos com baixo estoque
    equipamentos_baixo_estoque = []
    for eq in Equipamento.query.all():
        if eq.quantidade_disponivel <= 5 and eq.quantidade_disponivel > 0:
            equipamentos_baixo_estoque.append(eq)
    
    return render_template('dashboard.html',
                         total_funcionarios=total_funcionarios,
                         total_equipamentos=total_equipamentos,
                         emprestimos_ativos=emprestimos_ativos,
                         emprestimos_devolvidos=emprestimos_devolvidos,
                         ultimos_emprestimos=ultimos_emprestimos,
                         equipamentos_baixo_estoque=equipamentos_baixo_estoque)

@app.route('/colaboradores')
@app.route('/funcionarios')
@operacional_required
def listar_funcionarios():
    pesquisa = request.args.get('q', '').strip()
    consulta = Funcionario.query.join(Usuario)

    if pesquisa:
        consulta = consulta.filter(Usuario.nome.ilike(f'%{pesquisa}%'))

    funcionarios = consulta.order_by(Usuario.nome.asc()).all()
    return render_template('manage_emp.html', funcionarios=funcionarios, pesquisa=pesquisa)


@app.route('/colaboradores/novo', methods=['GET', 'POST'])
@app.route('/funcionarios/novo', methods=['GET', 'POST'])
@operacional_required
def criar_funcionario():
    if request.method == 'POST':
        dados = request.form
        try:
            nome = dados.get('nome', '').strip()
            email_login = dados.get('email', '').strip().lower()
            senha = dados.get('senha', '').strip()
            cpf = dados.get('cpf', '').strip()
            data_nascimento = _date(dados.get('data_nascimento'))
            endereco = dados.get('endereco', '').strip()
            telefones = _items(dados.get('telefones'))
            emails = _items(dados.get('emails_adicionais'))

            if not all([nome, email_login, senha, cpf, data_nascimento, endereco]):
                flash('Falha ao cadastrar: preencha todos os campos obrigatórios.', 'danger')
                return render_template('employee.html', funcionario=None, form=dados, modo='create')

            erros = _validar_dados_pessoa(nome, email_login, cpf, telefones, emails, senha, exigir_senha=True)
            if erros:
                for erro in erros:
                    flash(erro, 'danger')
                return render_template('employee.html', funcionario=None, form=dados, modo='create')

            cpf = _formatar_cpf_cnpj(cpf)
            telefones = [_formatar_telefone(t) for t in telefones]
            emails = [e.lower() for e in emails]

            usuario = Usuario(nome=nome, email=email_login, senha='', tipo='COLABORADOR', ativo=True)
            usuario.definir_senha(senha)
            db.session.add(usuario)
            db.session.flush()

            funcionario = Funcionario(
                id_usuario=usuario.id_usuario,
                cpf=cpf,
                data_nascimento=data_nascimento,
                endereco=endereco,
            )
            db.session.add(funcionario)
            db.session.flush()

            for numero in telefones:
                db.session.add(Telefone(id_usuario=funcionario.id_usuario, numero=numero))
            for email in emails:
                db.session.add(EmailFuncionario(id_usuario=funcionario.id_usuario, email=email.lower()))

            db.session.commit()
            flash('Colaborador cadastrado com sucesso.', 'success')
            return redirect(url_for('criar_funcionario'))
        except IntegrityError:
            db.session.rollback()
            flash('Falha ao cadastrar: CPF/CNPJ ou e-mail já cadastrado.', 'danger')
            return render_template('employee.html', funcionario=None, form=dados, modo='create')
        except Exception as erro:
            db.session.rollback()
            flash(f'Falha ao cadastrar colaborador: {erro}', 'danger')
            return render_template('employee.html', funcionario=None, form=dados, modo='create')

    return render_template('employee.html', funcionario=None, form={}, modo='create')


@app.route('/colaboradores/<int:id_usuario>/editar', methods=['GET', 'POST'])
@app.route('/funcionarios/<int:id_usuario>/editar', methods=['GET', 'POST'])
@operacional_required
def editar_funcionario(id_usuario):
    funcionario = Funcionario.query.get_or_404(id_usuario)

    if request.method == 'POST':
        dados = request.form
        try:
            nome = dados.get('nome', '').strip()
            email_login = dados.get('email', '').strip().lower()
            senha = dados.get('senha', '').strip()
            cpf = dados.get('cpf', '').strip()
            data_nascimento = _date(dados.get('data_nascimento'))
            endereco = dados.get('endereco', '').strip()
            telefones = _items(dados.get('telefones'))
            emails = _items(dados.get('emails_adicionais'))

            if not all([nome, email_login, cpf, data_nascimento, endereco]):
                flash('Falha ao atualizar: preencha todos os campos obrigatórios.', 'danger')
                return render_template('employee.html', funcionario=funcionario, form=dados, modo='edit')

            erros = _validar_dados_pessoa(nome, email_login, cpf, telefones, emails, senha, exigir_senha=False)
            if senha and len(senha) < 6:
                erros.append('A nova senha deve possuir pelo menos 6 caracteres.')
            if erros:
                for erro in erros:
                    flash(erro, 'danger')
                return render_template('employee.html', funcionario=funcionario, form=dados, modo='edit')

            cpf = _formatar_cpf_cnpj(cpf)
            telefones = [_formatar_telefone(t) for t in telefones]
            emails = [e.lower() for e in emails]

            funcionario.usuario.nome = nome
            funcionario.usuario.email = email_login
            if senha:
                funcionario.usuario.definir_senha(senha)
            funcionario.usuario.tipo = 'COLABORADOR'
            funcionario.cpf = cpf
            funcionario.data_nascimento = data_nascimento
            funcionario.endereco = endereco

            Telefone.query.filter_by(id_usuario=id_usuario).delete()
            EmailFuncionario.query.filter_by(id_usuario=id_usuario).delete()
            for numero in telefones:
                db.session.add(Telefone(id_usuario=id_usuario, numero=numero))
            for email in emails:
                db.session.add(EmailFuncionario(id_usuario=id_usuario, email=email.lower()))

            db.session.commit()
            flash('Colaborador atualizado com sucesso.', 'success')
            return redirect(url_for('listar_funcionarios'))
        except IntegrityError:
            db.session.rollback()
            flash('Falha ao atualizar: CPF/CNPJ ou e-mail já utilizado por outro colaborador.', 'danger')
            return render_template('employee.html', funcionario=funcionario, form=dados, modo='edit')
        except Exception as erro:
            db.session.rollback()
            flash(f'Falha ao atualizar colaborador: {erro}', 'danger')
            return render_template('employee.html', funcionario=funcionario, form=dados, modo='edit')

    return render_template('employee.html', funcionario=funcionario, form={}, modo='edit')


@app.route('/colaboradores/<int:id_usuario>/excluir', methods=['POST'])
@app.route('/funcionarios/<int:id_usuario>/excluir', methods=['POST'])
@operacional_required
def excluir_funcionario(id_usuario):
    funcionario = Funcionario.query.get_or_404(id_usuario)
    try:
        db.session.delete(funcionario.usuario)
        db.session.commit()
        flash('Colaborador excluído com sucesso.', 'success')
    except Exception as erro:
        db.session.rollback()
        flash(f'Falha ao excluir colaborador: {erro}', 'danger')
    return redirect(url_for('listar_funcionarios'))

@app.route('/usuarios')
@admin_required
def listar_usuarios():
    pesquisa = request.args.get('q', '').strip()
    consulta = Usuario.query

    if pesquisa:
        consulta = consulta.filter(
            db.or_(
                Usuario.nome.ilike(f'%{pesquisa}%'),
                Usuario.email.ilike(f'%{pesquisa}%'),
                Usuario.tipo.ilike(f'%{pesquisa}%')
            )
        )

    usuarios = consulta.order_by(Usuario.nome.asc()).all()
    return render_template('usuarios_list.html', usuarios=usuarios, pesquisa=pesquisa)


@app.route('/usuarios/novo', methods=['GET', 'POST'])
@admin_required
def criar_usuario():
    if request.method == 'POST':
        dados = request.form
        try:
            nome = dados.get('nome', '').strip()
            email = dados.get('email', '').strip().lower()
            senha = dados.get('senha', '').strip()
            tipo = 'USUARIO'
            ativo = bool(dados.get('ativo'))

            if not all([nome, email, senha]):
                flash('Preencha nome, e-mail e senha.', 'danger')
                return render_template('usuario_form.html', usuario=None, form=dados, modo='create')

            erros = _validar_dados_pessoa(nome, email, senha=senha, exigir_senha=True)
            if erros:
                for erro in erros:
                    flash(erro, 'danger')
                return render_template('usuario_form.html', usuario=None, form=dados, modo='create')

            usuario = Usuario(nome=nome, email=email, senha='', tipo=tipo, ativo=ativo)
            usuario.definir_senha(senha)
            db.session.add(usuario)
            db.session.commit()
            flash('Usuário criado com sucesso.', 'success')
            return redirect(url_for('listar_usuarios'))
        except IntegrityError:
            db.session.rollback()
            flash('Já existe um usuário com este e-mail.', 'danger')
        except Exception as erro:
            db.session.rollback()
            flash(f'Falha ao criar usuário: {erro}', 'danger')

    return render_template('usuario_form.html', usuario=None, form={}, modo='create')


@app.route('/usuarios/<int:id_usuario>/editar', methods=['GET', 'POST'])
@admin_required
def editar_usuario(id_usuario):
    usuario = Usuario.query.get_or_404(id_usuario)

    if request.method == 'POST':
        dados = request.form
        try:
            nome = dados.get('nome', '').strip()
            email = dados.get('email', '').strip().lower()
            senha = dados.get('senha', '').strip()
            tipo = usuario.tipo
            ativo = bool(dados.get('ativo'))

            if not all([nome, email]):
                flash('Preencha nome e e-mail.', 'danger')
                return render_template('usuario_form.html', usuario=usuario, form=dados, modo='edit')

            erros = _validar_dados_pessoa(nome, email, senha=senha, exigir_senha=False)
            if senha and len(senha) < 6:
                erros.append('A nova senha deve possuir pelo menos 6 caracteres.')
            if erros:
                for erro in erros:
                    flash(erro, 'danger')
                return render_template('usuario_form.html', usuario=usuario, form=dados, modo='edit')

            usuario.nome = nome
            usuario.email = email
            usuario.tipo = tipo
            usuario.ativo = ativo
            if senha:
                usuario.definir_senha(senha)

            db.session.commit()
            if session.get('usuario_id') == usuario.id_usuario:
                session['usuario_nome'] = usuario.nome
                session['usuario_email'] = usuario.email
                session['usuario_tipo'] = usuario.tipo
            flash('Usuário atualizado com sucesso.', 'success')
            return redirect(url_for('listar_usuarios'))
        except IntegrityError:
            db.session.rollback()
            flash('Já existe outro usuário com este e-mail.', 'danger')
        except Exception as erro:
            db.session.rollback()
            flash(f'Falha ao atualizar usuário: {erro}', 'danger')

    return render_template('usuario_form.html', usuario=usuario, form={}, modo='edit')


@app.route('/usuarios/<int:id_usuario>/excluir', methods=['POST'])
@admin_required
def excluir_usuario(id_usuario):
    if session.get('usuario_id') == id_usuario:
        flash('Você não pode excluir o próprio usuário logado.', 'warning')
        return redirect(url_for('listar_usuarios'))

    usuario = Usuario.query.get_or_404(id_usuario)
    try:
        db.session.delete(usuario)
        db.session.commit()
        flash('Usuário excluído com sucesso.', 'success')
    except Exception as erro:
        db.session.rollback()
        flash(f'Falha ao excluir usuário: {erro}', 'danger')
    return redirect(url_for('listar_usuarios'))



@app.route('/equipamentos')
@epi_required
def listar_equipamentos():
    pesquisa = request.args.get('q', '').strip()
    consulta = _consulta_equipamentos_com_acesso()
    
    if pesquisa:
        consulta = consulta.filter(
            db.or_(
                Equipamento.nome.ilike(f'%{pesquisa}%'),
                Equipamento.categoria.ilike(f'%{pesquisa}%'),
                Equipamento.marca.ilike(f'%{pesquisa}%')
            )
        )
    
    equipamentos = consulta.order_by(Equipamento.nome.asc()).all()
    return render_template('equipamentos.html', equipamentos=equipamentos, pesquisa=pesquisa)


@app.route('/equipamentos/novo', methods=['GET', 'POST'])
@epi_required
def criar_equipamento():
    if request.method == 'POST':
        dados = request.form
        try:
            nome = dados.get('nome', '').strip()
            categoria = dados.get('categoria', '').strip()
            marca = dados.get('marca', '').strip()
            quantidade_total = int(dados.get('quantidade_total', 0))
            descricao = dados.get('descricao', '').strip()
            tamanho = dados.get('tamanho', '').strip()
            peso = dados.get('peso', '').strip()
            validade = _date(dados.get('validade'))
            
            if not all([nome, categoria, marca, quantidade_total]):
                flash('Falha ao cadastrar: preencha todos os campos obrigatórios.', 'danger')
                return render_template('equipamento_form.html', equipamento=None, form=dados, modo='create')
            
            equipamento = Equipamento(
                nome=nome,
                categoria=categoria,
                marca=marca,
                quantidade_total=quantidade_total,
                descricao=descricao,
                tamanho=tamanho,
                peso=peso,
                validade=validade,
                id_usuario_criador=session.get('usuario_id') if session.get('usuario_tipo') == 'COLABORADOR' else None
            )
            
            db.session.add(equipamento)
            db.session.commit()
            flash('Equipamento cadastrado com sucesso!', 'success')
            return redirect(url_for('listar_equipamentos'))
            
        except Exception as erro:
            db.session.rollback()
            flash(f'Falha ao cadastrar equipamento: {erro}', 'danger')
            return render_template('equipamento_form.html', equipamento=None, form=dados, modo='create')
    
    return render_template('equipamento_form.html', equipamento=None, form={}, modo='create')


@app.route('/equipamentos/<int:id_equipamento>/editar', methods=['GET', 'POST'])
@epi_required
def editar_equipamento(id_equipamento):
    equipamento = Equipamento.query.get_or_404(id_equipamento)
    if not _garantir_acesso_equipamento(equipamento):
        return redirect(url_for('listar_equipamentos'))
    
    if request.method == 'POST':
        dados = request.form
        try:
            nome = dados.get('nome', '').strip()
            categoria = dados.get('categoria', '').strip()
            marca = dados.get('marca', '').strip()
            quantidade_total = int(dados.get('quantidade_total', 0))
            descricao = dados.get('descricao', '').strip()
            tamanho = dados.get('tamanho', '').strip()
            peso = dados.get('peso', '').strip()
            validade = _date(dados.get('validade'))
            
            if not all([nome, categoria, marca, quantidade_total]):
                flash('Falha ao atualizar: preencha todos os campos obrigatórios.', 'danger')
                return render_template('equipamento_form.html', equipamento=equipamento, form=dados, modo='edit')
            
            equipamento.nome = nome
            equipamento.categoria = categoria
            equipamento.marca = marca
            equipamento.quantidade_total = quantidade_total
            equipamento.descricao = descricao
            equipamento.tamanho = tamanho
            equipamento.peso = peso
            equipamento.validade = validade
            
            db.session.commit()
            flash('Equipamento atualizado com sucesso!', 'success')
            return redirect(url_for('listar_equipamentos'))
            
        except Exception as erro:
            db.session.rollback()
            flash(f'Falha ao atualizar equipamento: {erro}', 'danger')
            return render_template('equipamento_form.html', equipamento=equipamento, form=dados, modo='edit')
    
    return render_template('equipamento_form.html', equipamento=equipamento, form={}, modo='edit')


@app.route('/equipamentos/<int:id_equipamento>/excluir', methods=['POST'])
@epi_required
def excluir_equipamento(id_equipamento):
    equipamento = Equipamento.query.get_or_404(id_equipamento)
    if not _garantir_acesso_equipamento(equipamento):
        return redirect(url_for('listar_equipamentos'))
    try:
        db.session.delete(equipamento)
        db.session.commit()
        flash('Equipamento excluído com sucesso!', 'success')
    except Exception as erro:
        db.session.rollback()
        flash(f'Falha ao excluir equipamento: {erro}', 'danger')
    return redirect(url_for('listar_equipamentos'))


@app.route('/api/equipamentos/<int:id_equipamento>/estoque')
@epi_required
def api_estoque_equipamento(id_equipamento):
    equipamento = Equipamento.query.get_or_404(id_equipamento)
    if not _garantir_acesso_equipamento(equipamento):
        return jsonify({'erro': 'acesso negado'}), 403
    return jsonify({
        'id': equipamento.id_equipamento,
        'nome': equipamento.nome,
        'quantidade_total': equipamento.quantidade_total,
        'quantidade_disponivel': equipamento.quantidade_disponivel
    })

@app.route('/emprestimos')
@login_required
def listar_emprestimos():
    status_filtro = request.args.get('status', '').strip()
    pesquisa = request.args.get('q', '').strip()
    equipamento_filtro = request.args.get('equipamento', '').strip()
    
    consulta = _consulta_emprestimos_com_acesso()
    
    if status_filtro:
        consulta = consulta.filter(Emprestimo.status == status_filtro)
    
    if pesquisa:
        consulta = consulta.filter(Usuario.nome.ilike(f'%{pesquisa}%'))

    if equipamento_filtro:
        consulta = consulta.join(ItemEmprestimo).join(Equipamento).filter(
            Equipamento.nome.ilike(f'%{equipamento_filtro}%')
        ).distinct()
    
    emprestimos = consulta.order_by(Emprestimo.id_emprestimo.desc()).all()
    
    return render_template('emprestimos_list.html', 
                         emprestimos=emprestimos, 
                         status_filtro=status_filtro,
                         pesquisa=pesquisa,
                         equipamento_filtro=equipamento_filtro,
                         status_opcoes=STATUS_EDICAO_EMPRESTIMO)


@app.route('/emprestimos/novo', methods=['GET', 'POST'])
@emprestimo_required
def criar_emprestimo():
    if request.method == 'POST':
        dados = request.form
        try:
            if session.get('usuario_tipo') in ['COLABORADOR', 'USUARIO']:
                id_usuario = session.get('usuario_id')
            else:
                id_usuario = int(dados.get('id_usuario'))
            data_hora_fim_prevista = _datetime(dados.get('data_hora_fim_prevista'))
            status = dados.get('status', 'EMPRESTADO')
            
            if not data_hora_fim_prevista:
                flash('Data e hora de devolução prevista são obrigatórias.', 'danger')
                return redirect(url_for('criar_emprestimo'))

            if data_hora_fim_prevista <= datetime.now():
                flash('A data prevista para devolução deve ser posterior à data e hora atuais.', 'danger')
                return redirect(url_for('criar_emprestimo'))

            if status not in STATUS_CADASTRO_EMPRESTIMO:
                flash('Status inválido para cadastro. Use Emprestado ou Fornecido.', 'danger')
                return redirect(url_for('criar_emprestimo'))
            
            usuario_destino = Usuario.query.get(id_usuario)
            if not usuario_destino:
                flash('Usuário/colaborador não encontrado.', 'danger')
                return redirect(url_for('criar_emprestimo'))
            
            emprestimo = Emprestimo(
                id_usuario=id_usuario,
                data_hora_fim_prevista=data_hora_fim_prevista,
                status=status
            )
            db.session.add(emprestimo)
            db.session.flush()
            
            equipamentos_ids = request.form.getlist('equipamento_id[]')
            quantidades = request.form.getlist('quantidade[]')
            observacoes = request.form.getlist('observacao[]')
            
            itens_validos = 0
            for i, eq_id in enumerate(equipamentos_ids):
                if eq_id and i < len(quantidades) and quantidades[i]:
                    quantidade = int(quantidades[i])
                    equipamento = Equipamento.query.get(int(eq_id))

                    if equipamento and session.get('usuario_tipo') == 'COLABORADOR' and not _garantir_acesso_equipamento(equipamento):
                        db.session.rollback()
                        return redirect(url_for('criar_emprestimo'))

                    if not equipamento or quantidade <= 0:
                        db.session.rollback()
                        flash('Informe equipamentos e quantidades válidas.', 'danger')
                        return redirect(url_for('criar_emprestimo'))
                    
                    if equipamento.quantidade_disponivel < quantidade:
                        db.session.rollback()
                        flash(f'Equipamento {equipamento.nome} não tem quantidade disponível suficiente.', 'danger')
                        return redirect(url_for('criar_emprestimo'))
                    
                    item = ItemEmprestimo(
                        id_emprestimo=emprestimo.id_emprestimo,
                        id_equipamento=int(eq_id),
                        quantidade=quantidade,
                        observacao=observacoes[i] if i < len(observacoes) else ''
                    )
                    db.session.add(item)
                    itens_validos += 1

            if itens_validos == 0:
                db.session.rollback()
                flash('Adicione pelo menos um EPI ao empréstimo.', 'danger')
                return redirect(url_for('criar_emprestimo'))
            
            db.session.commit()
            flash('Empréstimo cadastrado com sucesso!', 'success')
            return redirect(url_for('listar_emprestimos'))
            
        except Exception as erro:
            db.session.rollback()
            flash(f'Falha ao cadastrar empréstimo: {erro}', 'danger')
            return redirect(url_for('criar_emprestimo'))
    
    if session.get('usuario_tipo') in ['COLABORADOR', 'USUARIO']:
        colaboradores = [usuario_atual()]
    else:
        colaboradores = Usuario.query.order_by(Usuario.nome).all()
    if session.get('usuario_tipo') == 'COLABORADOR':
        equipamentos = _consulta_equipamentos_com_acesso().order_by(Equipamento.nome).all()
    else:
        equipamentos = Equipamento.query.order_by(Equipamento.nome).all()
    equipamentos_com_estoque = [e for e in equipamentos if e.quantidade_disponivel > 0]
    
    return render_template('emprestimo_form.html', 
                         colaboradores=colaboradores,
                         equipamentos=equipamentos_com_estoque,
                         modo='create',
                         status_opcoes=STATUS_CADASTRO_EMPRESTIMO,
                         status_com_devolucao=STATUS_COM_DEVOLUCAO)


@app.route('/emprestimos/<int:id_emprestimo>')
@login_required
def ver_emprestimo(id_emprestimo):
    emprestimo = Emprestimo.query.get_or_404(id_emprestimo)
    if not _garantir_acesso_emprestimo(emprestimo):
        return redirect(url_for('listar_emprestimos'))
    emprestimo.verificar_atraso()
    return render_template('emprestimo_view.html', emprestimo=emprestimo)


@app.route('/emprestimos/<int:id_emprestimo>/editar', methods=['GET', 'POST'])
@emprestimo_required
def editar_emprestimo(id_emprestimo):
    if session.get('usuario_tipo') == 'USUARIO':
        flash('Usuário comum pode apenas pedir empréstimo e visualizar seus próprios empréstimos.', 'danger')
        return redirect(url_for('listar_emprestimos'))
    emprestimo = Emprestimo.query.get_or_404(id_emprestimo)
    if not _garantir_acesso_emprestimo(emprestimo):
        return redirect(url_for('listar_emprestimos'))
    
    if request.method == 'POST':
        try:
            status = request.form.get('status', '').strip()
            data_hora_fim_real = _datetime(request.form.get('data_hora_fim_real'))
            observacao_devolucao = request.form.get('observacao_devolucao', '').strip()

            if status not in STATUS_EDICAO_EMPRESTIMO:
                flash('Status inválido.', 'danger')
                return redirect(url_for('editar_emprestimo', id_emprestimo=id_emprestimo))

            emprestimo.status = status

            if status in STATUS_COM_DEVOLUCAO:
                if not data_hora_fim_real:
                    flash('Informe a data da devolução para status Devolvido, Danificado ou Perdido.', 'danger')
                    return redirect(url_for('editar_emprestimo', id_emprestimo=id_emprestimo))
                emprestimo.data_hora_fim_real = data_hora_fim_real
                emprestimo.observacao_devolucao = observacao_devolucao
            else:
                emprestimo.data_hora_fim_real = None
                emprestimo.observacao_devolucao = None

            db.session.commit()
            flash('Status do empréstimo atualizado com sucesso!', 'success')
            return redirect(url_for('listar_emprestimos'))
            
        except Exception as erro:
            db.session.rollback()
            flash(f'Falha ao atualizar empréstimo: {erro}', 'danger')
    
    colaboradores = Usuario.query.order_by(Usuario.nome).all()
    equipamentos = _consulta_equipamentos_com_acesso().order_by(Equipamento.nome).all()
    
    return render_template('emprestimo_form.html', 
                         emprestimo=emprestimo,
                         colaboradores=colaboradores,
                         equipamentos=equipamentos,
                         modo='edit',
                         status_opcoes=STATUS_EDICAO_EMPRESTIMO,
                         status_com_devolucao=STATUS_COM_DEVOLUCAO,
                         datetime_local=_datetime_local)


@app.route('/emprestimos/<int:id_emprestimo>/finalizar', methods=['POST'])
@emprestimo_required
def finalizar_emprestimo(id_emprestimo):
    if session.get('usuario_tipo') == 'USUARIO':
        flash('Usuário comum não pode alterar status de empréstimos.', 'danger')
        return redirect(url_for('listar_emprestimos'))
    emprestimo = Emprestimo.query.get_or_404(id_emprestimo)
    if not _garantir_acesso_emprestimo(emprestimo):
        return redirect(url_for('listar_emprestimos'))
    
    if not emprestimo.pode_finalizar:
        flash('Este empréstimo não pode ser finalizado.', 'warning')
        return redirect(url_for('listar_emprestimos'))
    
    try:
        emprestimo.status = 'DEVOLVIDO'
        emprestimo.data_hora_fim_real = datetime.now()
        db.session.commit()
        flash('Empréstimo marcado como devolvido com sucesso!', 'success')
    except Exception as erro:
        db.session.rollback()
        flash(f'Falha ao finalizar empréstimo: {erro}', 'danger')
    
    return redirect(url_for('listar_emprestimos'))


@app.route('/emprestimos/<int:id_emprestimo>/cancelar', methods=['POST'])
@emprestimo_required
def cancelar_emprestimo(id_emprestimo):
    if session.get('usuario_tipo') == 'USUARIO':
        flash('Usuário comum não pode cancelar empréstimos.', 'danger')
        return redirect(url_for('listar_emprestimos'))
    emprestimo = Emprestimo.query.get_or_404(id_emprestimo)
    if not _garantir_acesso_emprestimo(emprestimo):
        return redirect(url_for('listar_emprestimos'))
    
    if emprestimo.status in STATUS_COM_DEVOLUCAO:
        flash('Empréstimos já baixados não podem ser cancelados.', 'warning')
        return redirect(url_for('listar_emprestimos'))
    
    try:
        emprestimo.status = 'PERDIDO'
        emprestimo.data_hora_fim_real = datetime.now()
        db.session.commit()
        flash('Empréstimo marcado como perdido com sucesso!', 'success')
    except Exception as erro:
        db.session.rollback()
        flash(f'Falha ao cancelar empréstimo: {erro}', 'danger')
    
    return redirect(url_for('listar_emprestimos'))


@app.route('/emprestimos/<int:id_emprestimo>/excluir', methods=['POST'])
@emprestimo_required
def excluir_emprestimo(id_emprestimo):
    if session.get('usuario_tipo') == 'USUARIO':
        flash('Usuário comum não pode excluir empréstimos.', 'danger')
        return redirect(url_for('listar_emprestimos'))
    emprestimo = Emprestimo.query.get_or_404(id_emprestimo)
    if not _garantir_acesso_emprestimo(emprestimo):
        return redirect(url_for('listar_emprestimos'))
    
    try:
        db.session.delete(emprestimo)
        db.session.commit()
        flash('Empréstimo excluído com sucesso!', 'success')
    except Exception as erro:
        db.session.rollback()
        flash(f'Falha ao excluir empréstimo: {erro}', 'danger')
    
    return redirect(url_for('listar_emprestimos'))