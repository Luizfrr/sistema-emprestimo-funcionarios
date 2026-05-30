import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

basedir = os.path.abspath(os.path.dirname(__file__))

def _database_uri():
    """
    Usa MySQL quando DATABASE_URL estiver configurado.
    Exemplo para o LAB 09:
    mysql+pymysql://root:senha@localhost:3306/controle_epi

    Mantém SQLite como fallback para facilitar testes locais quando o MySQL
    ainda não foi criado pelo aluno/professor.
    """
    return os.environ.get(
        'DATABASE_URL',
        'sqlite:///' + os.path.join(basedir, '..', 'emprestimos.db')
    )

app.config['SQLALCHEMY_DATABASE_URI'] = _database_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-trocar-em-producao')

db = SQLAlchemy(app)
migrate = Migrate(app, db)

from app import routes
