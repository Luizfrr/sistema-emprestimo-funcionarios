from app import app, db
from app.models import Usuario

def criar_admin():
    with app.app_context():
        # Verificar se já existe
        admin = Usuario.query.filter_by(email='admin@exemplo.com').first()
        
        if admin:
            print(f"Usuário admin já existe: {admin.email}")
            return
        
        # Criar usuário admin
        admin = Usuario(
            nome='Administrador',
            email='admin@exemplo.com',
            senha='admin123',
            tipo='ADMIN'
        )
        
        db.session.add(admin)
        db.session.commit()
        
        print("=" * 50)
        print("Usuário administrador criado com sucesso!")
        print(f"Email: admin@exemplo.com")
        print(f"Senha: admin123")
        print("=" * 50)

if __name__ == '__main__':
    criar_admin()