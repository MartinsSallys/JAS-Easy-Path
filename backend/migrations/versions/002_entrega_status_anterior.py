"""Add status_anterior to entregas

Revision ID: 002_entrega_status_anterior
Revises: 001_initial
Create Date: 2026-11-28 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = '002_entrega_status_anterior'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'entregas',
        sa.Column(
            'status_anterior',
            sa.Enum(
                'PENDENTE', 'ATRIBUIDA', 'EM_ROTA', 'ENTREGUE', 'FALHA',
                'CANCELADA', name='entregastatus',
            ),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column('entregas', 'status_anterior')
