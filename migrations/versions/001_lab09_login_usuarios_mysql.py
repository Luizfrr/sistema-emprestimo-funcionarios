"""LAB 09 - login, logout, controle de usuários e campos de devolução

Revision ID: 001_lab09
Revises: 
Create Date: 2026-05-23
"""
from alembic import op
import sqlalchemy as sa

revision = '001_lab09'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table('usuario'):
        op.create_table(
            'usuario',
            sa.Column('id_usuario', sa.Integer(), primary_key=True),
            sa.Column('nome', sa.String(length=100), nullable=False),
            sa.Column('email', sa.String(length=120), nullable=False, unique=True),
            sa.Column('senha', sa.String(length=255), nullable=False),
            sa.Column('tipo', sa.String(length=30), nullable=False, server_default='USUARIO'),
            sa.Column('ativo', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('criado_em', sa.DateTime(), nullable=True),
            sa.Column('ultimo_login', sa.DateTime(), nullable=True),
        )
    else:
        colunas_usuario = [c['name'] for c in inspector.get_columns('usuario')]
        with op.batch_alter_table('usuario') as batch_op:
            if 'ativo' not in colunas_usuario:
                batch_op.add_column(sa.Column('ativo', sa.Boolean(), nullable=False, server_default=sa.true()))
            if 'criado_em' not in colunas_usuario:
                batch_op.add_column(sa.Column('criado_em', sa.DateTime(), nullable=True))
            if 'ultimo_login' not in colunas_usuario:
                batch_op.add_column(sa.Column('ultimo_login', sa.DateTime(), nullable=True))

        op.execute("UPDATE usuario SET tipo = 'COLABORADOR' WHERE tipo = 'FUNCIONARIO'")
        op.execute("UPDATE usuario SET tipo = 'USUARIO' WHERE tipo = 'OPERADOR'")

    if not inspector.has_table('funcionario'):
        op.create_table(
            'funcionario',
            sa.Column('id_usuario', sa.Integer(), sa.ForeignKey('usuario.id_usuario', ondelete='CASCADE'), primary_key=True),
            sa.Column('cpf', sa.String(length=18), nullable=False, unique=True),
            sa.Column('data_nascimento', sa.Date(), nullable=False),
            sa.Column('endereco', sa.String(length=150), nullable=False),
        )
    else:
        try:
            with op.batch_alter_table('funcionario') as batch_op:
                batch_op.alter_column('cpf', existing_type=sa.String(length=14), type_=sa.String(length=18), existing_nullable=False)
        except Exception:
            pass

    if not inspector.has_table('telefone'):
        op.create_table(
            'telefone',
            sa.Column('id_telefone', sa.Integer(), primary_key=True),
            sa.Column('id_usuario', sa.Integer(), sa.ForeignKey('funcionario.id_usuario', ondelete='CASCADE'), nullable=False),
            sa.Column('numero', sa.String(length=20), nullable=False),
        )

    if not inspector.has_table('email_funcionario'):
        op.create_table(
            'email_funcionario',
            sa.Column('id_email', sa.Integer(), primary_key=True),
            sa.Column('id_usuario', sa.Integer(), sa.ForeignKey('funcionario.id_usuario', ondelete='CASCADE'), nullable=False),
            sa.Column('email', sa.String(length=120), nullable=False),
        )

    if not inspector.has_table('equipamento'):
        op.create_table(
            'equipamento',
            sa.Column('id_equipamento', sa.Integer(), primary_key=True),
            sa.Column('nome', sa.String(length=100), nullable=False),
            sa.Column('categoria', sa.String(length=80), nullable=False),
            sa.Column('marca', sa.String(length=80), nullable=False),
            sa.Column('descricao', sa.Text(), nullable=True),
            sa.Column('quantidade_total', sa.Integer(), nullable=False),
            sa.Column('tamanho', sa.String(length=50), nullable=True),
            sa.Column('peso', sa.String(length=50), nullable=True),
            sa.Column('validade', sa.Date(), nullable=True),
            sa.Column('id_usuario_criador', sa.Integer(), sa.ForeignKey('usuario.id_usuario'), nullable=True),
        )

    if inspector.has_table('equipamento'):
        colunas_equipamento = [c['name'] for c in inspector.get_columns('equipamento')]
        if 'id_usuario_criador' not in colunas_equipamento:
            with op.batch_alter_table('equipamento') as batch_op:
                batch_op.add_column(sa.Column('id_usuario_criador', sa.Integer(), nullable=True))

    if not inspector.has_table('emprestimo'):
        op.create_table(
            'emprestimo',
            sa.Column('id_emprestimo', sa.Integer(), primary_key=True),
            sa.Column('data_hora_inicio', sa.DateTime(), nullable=False),
            sa.Column('data_hora_fim_prevista', sa.DateTime(), nullable=False),
            sa.Column('data_hora_fim_real', sa.DateTime(), nullable=True),
            sa.Column('observacao_devolucao', sa.Text(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='EMPRESTADO'),
            sa.Column('id_usuario', sa.Integer(), sa.ForeignKey('usuario.id_usuario', ondelete='CASCADE'), nullable=False),
        )
    else:
        colunas_emprestimo = [c['name'] for c in inspector.get_columns('emprestimo')]
        with op.batch_alter_table('emprestimo') as batch_op:
            if 'observacao_devolucao' not in colunas_emprestimo:
                batch_op.add_column(sa.Column('observacao_devolucao', sa.Text(), nullable=True))

        op.execute("UPDATE emprestimo SET status = 'EMPRESTADO' WHERE status IN ('ATIVO', 'ATRASADO')")
        op.execute("UPDATE emprestimo SET status = 'DEVOLVIDO' WHERE status = 'FINALIZADO'")
        op.execute("UPDATE emprestimo SET status = 'PERDIDO' WHERE status = 'CANCELADO'")

    if not inspector.has_table('item_emprestimo'):
        op.create_table(
            'item_emprestimo',
            sa.Column('id_item', sa.Integer(), primary_key=True),
            sa.Column('quantidade', sa.Integer(), nullable=False),
            sa.Column('observacao', sa.Text(), nullable=True),
            sa.Column('id_emprestimo', sa.Integer(), sa.ForeignKey('emprestimo.id_emprestimo', ondelete='CASCADE'), nullable=False),
            sa.Column('id_equipamento', sa.Integer(), sa.ForeignKey('equipamento.id_equipamento'), nullable=False),
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table('usuario'):
        colunas_usuario = [c['name'] for c in inspector.get_columns('usuario')]
        with op.batch_alter_table('usuario') as batch_op:
            if 'ultimo_login' in colunas_usuario:
                batch_op.drop_column('ultimo_login')
            if 'criado_em' in colunas_usuario:
                batch_op.drop_column('criado_em')
            if 'ativo' in colunas_usuario:
                batch_op.drop_column('ativo')

    if inspector.has_table('equipamento'):
        colunas_equipamento = [c['name'] for c in inspector.get_columns('equipamento')]
        if 'id_usuario_criador' in colunas_equipamento:
            with op.batch_alter_table('equipamento') as batch_op:
                batch_op.drop_column('id_usuario_criador')

    if inspector.has_table('emprestimo'):
        colunas_emprestimo = [c['name'] for c in inspector.get_columns('emprestimo')]
        with op.batch_alter_table('emprestimo') as batch_op:
            if 'observacao_devolucao' in colunas_emprestimo:
                batch_op.drop_column('observacao_devolucao')
