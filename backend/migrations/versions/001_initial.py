"""Initial migration

Revision ID: 001_initial
Revises: 
Create Date: 2026-01-19 14:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'depositos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(length=100), nullable=False),
        sa.Column('endereco', sa.Text(), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'veiculos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('placa', sa.String(length=10), nullable=False),
        sa.Column('capacidade', sa.Integer(), nullable=False),
        sa.Column('tipo', sa.Enum('moto', 'carro', 'caminhao', 'van', name='veiculotipo'), nullable=False, server_default='caminhao'),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('placa')
    )
    op.create_index(op.f('ix_veiculos_placa'), 'veiculos', ['placa'], unique=True)

    op.create_table(
        'entregas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pedido_id', sa.String(length=50), nullable=False),
        sa.Column('endereco', sa.Text(), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('demanda', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('janela_inicio', sa.Time(), nullable=True),
        sa.Column('janela_fim', sa.Time(), nullable=True),
        sa.Column('status', sa.Enum('pendente', 'atribuida', 'em_rota', 'entregue', 'falha', 'cancelada', name='entregastatus'), nullable=False, server_default='pendente'),
        sa.Column('observacoes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('rota_id', sa.Integer(), nullable=True),
        sa.Column('parada_ordem', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('pedido_id')
    )
    op.create_index(op.f('ix_entregas_pedido_id'), 'entregas', ['pedido_id'], unique=True)
    op.create_index(op.f('ix_entregas_status'), 'entregas', ['status'])
    op.create_index(op.f('ix_entregas_rota_id'), 'entregas', ['rota_id'])

    op.create_table(
        'rotas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(length=100), nullable=False),
        sa.Column('data', sa.Date(), nullable=False),
        sa.Column('deposito_id', sa.Integer(), nullable=False),
        sa.Column('veiculo_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.Enum('rascunho', 'otimizada', 'em_andamento', 'concluida', 'cancelada', name='rotastatus'), nullable=False, server_default='rascunho'),
        sa.Column('distancia_total_km', sa.Float(), nullable=True),
        sa.Column('tempo_total_min', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('otimizada_em', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['deposito_id'], ['depositos.id'], ),
        sa.ForeignKeyConstraint(['veiculo_id'], ['veiculos.id'], )
    )
    op.create_index(op.f('ix_rotas_data'), 'rotas', ['data'])
    op.create_index(op.f('ix_rotas_status'), 'rotas', ['status'])

    op.create_table(
        'paradas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('rota_id', sa.Integer(), nullable=False),
        sa.Column('entrega_id', sa.Integer(), nullable=True),
        sa.Column('deposito_id', sa.Integer(), nullable=True),
        sa.Column('ordem', sa.Integer(), nullable=False),
        sa.Column('endereco', sa.Text(), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('demanda', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('janela_inicio', sa.Time(), nullable=True),
        sa.Column('janela_fim', sa.Time(), nullable=True),
        sa.Column('status', sa.Enum('pendente', 'em_andamento', 'concluida', 'falha', 'puladas', name='paradastatus'), nullable=False, server_default='pendente'),
        sa.Column('tempo_servico_min', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('chegada_prevista', sa.Time(), nullable=True),
        sa.Column('saida_prevista', sa.Time(), nullable=True),
        sa.Column('observacoes', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['deposito_id'], ['depositos.id'], ),
        sa.ForeignKeyConstraint(['entrega_id'], ['entregas.id'], ),
        sa.ForeignKeyConstraint(['rota_id'], ['rotas.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('rota_id', 'ordem', name='ix_paradas_rota_ordem')
    )
    op.create_index(op.f('ix_paradas_rota_id'), 'paradas', ['rota_id'])
    op.create_index(op.f('ix_paradas_entrega_id'), 'paradas', ['entrega_id'])


def downgrade() -> None:
    op.drop_table('paradas')
    op.drop_table('rotas')
    op.drop_table('entregas')
    op.drop_table('veiculos')
    op.drop_table('depositos')
    
    op.execute('DROP TYPE IF EXISTS paradastatus')
    op.execute('DROP TYPE IF EXISTS rotastatus')
    op.execute('DROP TYPE IF EXISTS entregastatus')
    op.execute('DROP TYPE IF EXISTS veiculotipo')