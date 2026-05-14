from datetime import datetime
from flask import flash, redirect, render_template, request, url_for, session, jsonify
from sqlalchemy.exc import IntegrityError
from functools import wraps

from app import app, db
from app.models import EmailFuncionario, Funcionario, Telefone, Usuario, Equipamento, Emprestimo, ItemEmprestimo


def _date(value):
    return datetime.strptime(value, '%Y-%m-%d').date() if value else None


def _datetime(value):
    return datetime.strptime(value, '%Y-%m-%dT%H:%M') if value else None


def _items(value):
    return [v.strip() for v in (value or '').split(',') if v.strip()]


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            flash('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.before_request
def criar_banco():
    db.create_all()
    
    # Criar usuário admin se não existir
    admin = Usuario.query.filter_by(email='admin@exemplo.com').first()
    if not admin:
        admin = Usuario(
            nome='Administrador',
            email='admin@exemplo.com',
            senha='admin123',
            tipo='ADMIN'
        )
        db.session.add(admin)
        db.session.commit()
        print("Usuário admin criado automaticamente!")


@app.route('/')
def home():
    if 'usuario_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        senha = request.form.get('senha', '').strip()
        
        usuario = Usuario.query.filter_by(email=email, senha=senha).first()
        
        if usuario:
            session['usuario_id'] = usuario.id_usuario
            session['usuario_nome'] = usuario.nome
            session['usuario_tipo'] = usuario.tipo
            flash(f'Bem-vindo, {usuario.nome}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('E-mail ou senha inválidos.', 'danger')
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    # Estatísticas para o dashboard
    total_funcionarios = Funcionario.query.count()
    total_equipamentos = Equipamento.query.count()
    emprestimos_ativos = Emprestimo.query.filter(Emprestimo.status.in_(['ATIVO', 'ATRASADO'])).count()
    emprestimos_atrasados = Emprestimo.query.filter_by(status='ATRASADO').count()
    
    # Últimos empréstimos
    ultimos_emprestimos = Emprestimo.query.order_by(Emprestimo.id_emprestimo.desc()).limit(5).all()
    
    # Equipamentos com baixo estoque
    equipamentos_baixo_estoque = []
    for eq in Equipamento.query.all():
        if eq.quantidade_disponivel <= 5 and eq.quantidade_disponivel > 0:
            equipamentos_baixo_estoque.append(eq)
    
    return render_template('dashboard.html',
                         total_funcionarios=total_funcionarios,
                         total_equipamentos=total_equipamentos,
                         emprestimos_ativos=emprestimos_ativos,
                         emprestimos_atrasados=emprestimos_atrasados,
                         ultimos_emprestimos=ultimos_emprestimos,
                         equipamentos_baixo_estoque=equipamentos_baixo_estoque)

@app.route('/colaboradores')
@app.route('/funcionarios')
@login_required
def listar_funcionarios():
    pesquisa = request.args.get('q', '').strip()
    consulta = Funcionario.query.join(Usuario)

    if pesquisa:
        consulta = consulta.filter(Usuario.nome.ilike(f'%{pesquisa}%'))

    funcionarios = consulta.order_by(Usuario.nome.asc()).all()
    return render_template('manage_emp.html', funcionarios=funcionarios, pesquisa=pesquisa)


@app.route('/colaboradores/novo', methods=['GET', 'POST'])
@app.route('/funcionarios/novo', methods=['GET', 'POST'])
@login_required
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

            usuario = Usuario(nome=nome, email=email_login, senha=senha, tipo='FUNCIONARIO')
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
            flash('Falha ao cadastrar: CPF ou e-mail já cadastrado.', 'danger')
            return render_template('employee.html', funcionario=None, form=dados, modo='create')
        except Exception as erro:
            db.session.rollback()
            flash(f'Falha ao cadastrar colaborador: {erro}', 'danger')
            return render_template('employee.html', funcionario=None, form=dados, modo='create')

    return render_template('employee.html', funcionario=None, form={}, modo='create')


@app.route('/colaboradores/<int:id_usuario>/editar', methods=['GET', 'POST'])
@app.route('/funcionarios/<int:id_usuario>/editar', methods=['GET', 'POST'])
@login_required
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

            funcionario.usuario.nome = nome
            funcionario.usuario.email = email_login
            if senha:
                funcionario.usuario.senha = senha
            funcionario.usuario.tipo = 'FUNCIONARIO'
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
            flash('Falha ao atualizar: CPF ou e-mail já utilizado por outro colaborador.', 'danger')
            return render_template('employee.html', funcionario=funcionario, form=dados, modo='edit')
        except Exception as erro:
            db.session.rollback()
            flash(f'Falha ao atualizar colaborador: {erro}', 'danger')
            return render_template('employee.html', funcionario=funcionario, form=dados, modo='edit')

    return render_template('employee.html', funcionario=funcionario, form={}, modo='edit')


@app.route('/colaboradores/<int:id_usuario>/excluir', methods=['POST'])
@app.route('/funcionarios/<int:id_usuario>/excluir', methods=['POST'])
@login_required
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

@app.route('/equipamentos')
@login_required
def listar_equipamentos():
    pesquisa = request.args.get('q', '').strip()
    consulta = Equipamento.query
    
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
@login_required
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
                validade=validade
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
@login_required
def editar_equipamento(id_equipamento):
    equipamento = Equipamento.query.get_or_404(id_equipamento)
    
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
@login_required
def excluir_equipamento(id_equipamento):
    equipamento = Equipamento.query.get_or_404(id_equipamento)
    try:
        db.session.delete(equipamento)
        db.session.commit()
        flash('Equipamento excluído com sucesso!', 'success')
    except Exception as erro:
        db.session.rollback()
        flash(f'Falha ao excluir equipamento: {erro}', 'danger')
    return redirect(url_for('listar_equipamentos'))


@app.route('/api/equipamentos/<int:id_equipamento>/estoque')
@login_required
def api_estoque_equipamento(id_equipamento):
    equipamento = Equipamento.query.get_or_404(id_equipamento)
    return jsonify({
        'id': equipamento.id_equipamento,
        'nome': equipamento.nome,
        'quantidade_total': equipamento.quantidade_total,
        'quantidade_disponivel': equipamento.quantidade_disponivel
    })

@app.route('/emprestimos')
@login_required
def listar_emprestimos():
    # Atualizar status de atrasados
    for emp in Emprestimo.query.filter_by(status='ATIVO').all():
        emp.verificar_atraso()
    
    status_filtro = request.args.get('status', '')
    pesquisa = request.args.get('q', '').strip()
    
    consulta = Emprestimo.query.join(Usuario)
    
    if status_filtro:
        consulta = consulta.filter(Emprestimo.status == status_filtro)
    
    if pesquisa:
        consulta = consulta.filter(Usuario.nome.ilike(f'%{pesquisa}%'))
    
    emprestimos = consulta.order_by(Emprestimo.id_emprestimo.desc()).all()
    
    return render_template('emprestimos_list.html', 
                         emprestimos=emprestimos, 
                         status_filtro=status_filtro,
                         pesquisa=pesquisa)


@app.route('/emprestimos/novo', methods=['GET', 'POST'])
@login_required
def criar_emprestimo():
    if request.method == 'POST':
        dados = request.form
        try:
            id_usuario = int(dados.get('id_usuario'))
            data_hora_fim_prevista = _datetime(dados.get('data_hora_fim_prevista'))
            
            if not data_hora_fim_prevista:
                flash('Data e hora de devolução prevista são obrigatórias.', 'danger')
                return redirect(url_for('criar_emprestimo'))
            
            # Verificar se o usuário existe
            funcionario = Funcionario.query.get(id_usuario)
            if not funcionario:
                flash('Colaborador não encontrado.', 'danger')
                return redirect(url_for('criar_emprestimo'))
            
            # Criar empréstimo
            emprestimo = Emprestimo(
                id_usuario=id_usuario,
                data_hora_fim_prevista=data_hora_fim_prevista,
                status='ATIVO'
            )
            db.session.add(emprestimo)
            db.session.flush()
            
            # Adicionar itens
            equipamentos_ids = request.form.getlist('equipamento_id[]')
            quantidades = request.form.getlist('quantidade[]')
            observacoes = request.form.getlist('observacao[]')
            
            for i, eq_id in enumerate(equipamentos_ids):
                if eq_id and quantidades[i]:
                    quantidade = int(quantidades[i])
                    equipamento = Equipamento.query.get(int(eq_id))
                    
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
            
            db.session.commit()
            flash('Empréstimo cadastrado com sucesso!', 'success')
            return redirect(url_for('listar_emprestimos'))
            
        except Exception as erro:
            db.session.rollback()
            flash(f'Falha ao cadastrar empréstimo: {erro}', 'danger')
            return redirect(url_for('criar_emprestimo'))
    
    # GET - Carregar formulário
    colaboradores = Funcionario.query.join(Usuario).order_by(Usuario.nome).all()
    equipamentos = Equipamento.query.order_by(Equipamento.nome).all()
    equipamentos_com_estoque = [e for e in equipamentos if e.quantidade_disponivel > 0]
    
    return render_template('emprestimo_form.html', 
                         colaboradores=colaboradores,
                         equipamentos=equipamentos_com_estoque,
                         modo='create')


@app.route('/emprestimos/<int:id_emprestimo>')
@login_required
def ver_emprestimo(id_emprestimo):
    emprestimo = Emprestimo.query.get_or_404(id_emprestimo)
    emprestimo.verificar_atraso()
    return render_template('emprestimo_view.html', emprestimo=emprestimo)


@app.route('/emprestimos/<int:id_emprestimo>/editar', methods=['GET', 'POST'])
@login_required
def editar_emprestimo(id_emprestimo):
    emprestimo = Emprestimo.query.get_or_404(id_emprestimo)
    
    if emprestimo.status not in ['ATIVO', 'ATRASADO']:
        flash('Empréstimos finalizados ou cancelados não podem ser editados.', 'warning')
        return redirect(url_for('listar_emprestimos'))
    
    if request.method == 'POST':
        try:
            data_hora_fim_prevista = _datetime(request.form.get('data_hora_fim_prevista'))
            
            if data_hora_fim_prevista:
                emprestimo.data_hora_fim_prevista = data_hora_fim_prevista
            
            # Atualizar itens (remover todos e recriar)
            ItemEmprestimo.query.filter_by(id_emprestimo=id_emprestimo).delete()
            
            equipamentos_ids = request.form.getlist('equipamento_id[]')
            quantidades = request.form.getlist('quantidade[]')
            observacoes = request.form.getlist('observacao[]')
            
            for i, eq_id in enumerate(equipamentos_ids):
                if eq_id and quantidades[i]:
                    quantidade = int(quantidades[i])
                    item = ItemEmprestimo(
                        id_emprestimo=emprestimo.id_emprestimo,
                        id_equipamento=int(eq_id),
                        quantidade=quantidade,
                        observacao=observacoes[i] if i < len(observacoes) else ''
                    )
                    db.session.add(item)
            
            emprestimo.verificar_atraso()
            db.session.commit()
            flash('Empréstimo atualizado com sucesso!', 'success')
            return redirect(url_for('listar_emprestimos'))
            
        except Exception as erro:
            db.session.rollback()
            flash(f'Falha ao atualizar empréstimo: {erro}', 'danger')
    
    colaboradores = Funcionario.query.join(Usuario).order_by(Usuario.nome).all()
    equipamentos = Equipamento.query.order_by(Equipamento.nome).all()
    
    return render_template('emprestimo_form.html', 
                         emprestimo=emprestimo,
                         colaboradores=colaboradores,
                         equipamentos=equipamentos,
                         modo='edit')


@app.route('/emprestimos/<int:id_emprestimo>/finalizar', methods=['POST'])
@login_required
def finalizar_emprestimo(id_emprestimo):
    emprestimo = Emprestimo.query.get_or_404(id_emprestimo)
    
    if not emprestimo.pode_finalizar:
        flash('Este empréstimo não pode ser finalizado.', 'warning')
        return redirect(url_for('listar_emprestimos'))
    
    try:
        emprestimo.status = 'FINALIZADO'
        emprestimo.data_hora_fim_real = datetime.now()
        db.session.commit()
        flash('Empréstimo finalizado com sucesso!', 'success')
    except Exception as erro:
        db.session.rollback()
        flash(f'Falha ao finalizar empréstimo: {erro}', 'danger')
    
    return redirect(url_for('listar_emprestimos'))


@app.route('/emprestimos/<int:id_emprestimo>/cancelar', methods=['POST'])
@login_required
def cancelar_emprestimo(id_emprestimo):
    emprestimo = Emprestimo.query.get_or_404(id_emprestimo)
    
    if emprestimo.status == 'FINALIZADO':
        flash('Empréstimos finalizados não podem ser cancelados.', 'warning')
        return redirect(url_for('listar_emprestimos'))
    
    try:
        emprestimo.status = 'CANCELADO'
        emprestimo.data_hora_fim_real = datetime.now()
        db.session.commit()
        flash('Empréstimo cancelado com sucesso!', 'success')
    except Exception as erro:
        db.session.rollback()
        flash(f'Falha ao cancelar empréstimo: {erro}', 'danger')
    
    return redirect(url_for('listar_emprestimos'))


@app.route('/emprestimos/<int:id_emprestimo>/excluir', methods=['POST'])
@login_required
def excluir_emprestimo(id_emprestimo):
    emprestimo = Emprestimo.query.get_or_404(id_emprestimo)
    
    try:
        db.session.delete(emprestimo)
        db.session.commit()
        flash('Empréstimo excluído com sucesso!', 'success')
    except Exception as erro:
        db.session.rollback()
        flash(f'Falha ao excluir empréstimo: {erro}', 'danger')
    
    return redirect(url_for('listar_emprestimos'))