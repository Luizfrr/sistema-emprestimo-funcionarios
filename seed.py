from datetime import date

from app import app, db
from app.models import EmailFuncionario, Funcionario, Telefone, Usuario

with app.app_context():
    db.create_all()
    if not Usuario.query.first():
        usuario = Usuario(nome='João da Silva', email='joao@email.com', senha='123456', tipo='FUNCIONARIO')
        db.session.add(usuario)
        db.session.flush()
        funcionario = Funcionario(
            id_usuario=usuario.id_usuario,
            cpf='123.456.789-00',
            data_nascimento=date(1990, 3, 15),
            endereco='Rua das Flores, 123',
        )
        db.session.add(funcionario)
        db.session.add(Telefone(id_usuario=usuario.id_usuario, numero='(11) 99999-9999'))
        db.session.add(EmailFuncionario(id_usuario=usuario.id_usuario, email='joao.extra@email.com'))
        db.session.commit()
        print('Dados de exemplo criados.')
    else:
        print('Banco já possui dados.')
