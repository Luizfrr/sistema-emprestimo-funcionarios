from app import app, db
from app.models import Usuario


def criar_admin():
    with app.app_context():
        db.create_all()
        admin = Usuario.query.filter_by(email='admin@exemplo.com').first()

        if admin:
            admin.tipo = 'ADMIN'
            admin.ativo = True
            admin.definir_senha('admin123')
            db.session.commit()
            print('Usuário admin já existia e foi atualizado.')
        else:
            admin = Usuario(
                nome='Administrador',
                email='admin@exemplo.com',
                senha='',
                tipo='ADMIN',
                ativo=True,
            )
            admin.definir_senha('admin123')
            db.session.add(admin)
            db.session.commit()

        print('=' * 50)
        print('Usuário administrador disponível:')
        print('Email: admin@exemplo.com')
        print('Senha: admin123')
        print('=' * 50)


if __name__ == '__main__':
    criar_admin()
