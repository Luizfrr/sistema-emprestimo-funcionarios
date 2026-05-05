from datetime import datetime

from flask import flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from app import app, db
from app.models import EmailFuncionario, Funcionario, Telefone, Usuario


def _date(value):
    return datetime.strptime(value, '%Y-%m-%d').date() if value else None


def _items(value):
    return [v.strip() for v in (value or '').split(',') if v.strip()]


@app.before_request
def criar_banco():
    db.create_all()


@app.route('/')
def home():
    return redirect(url_for('listar_funcionarios'))


@app.route('/colaboradores')
@app.route('/funcionarios')
def listar_funcionarios():
    pesquisa = request.args.get('q', '').strip()
    consulta = Funcionario.query.join(Usuario)

    if pesquisa:
        consulta = consulta.filter(Usuario.nome.ilike(f'%{pesquisa}%'))

    funcionarios = consulta.order_by(Usuario.nome.asc()).all()
    return render_template('manage_emp.html', funcionarios=funcionarios, pesquisa=pesquisa)


@app.route('/colaboradores/novo', methods=['GET', 'POST'])
@app.route('/funcionarios/novo', methods=['GET', 'POST'])
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
