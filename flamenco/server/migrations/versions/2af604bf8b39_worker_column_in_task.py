"""Worker column in task

Revision ID: 2af604bf8b39
Revises: 167a98d74f8c
Create Date: 2015-06-18 22:54:24.190549

"""

# revision identifiers, used by Alembic.
revision = '2af604bf8b39'
down_revision = '167a98d74f8c'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('task', sa.Column('worker', sa.String(length=128), nullable=True))


def downgrade():
    op.drop_column('task', 'worker')
