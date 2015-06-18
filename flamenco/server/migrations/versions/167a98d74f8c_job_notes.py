"""Job notes

Revision ID: 167a98d74f8c
Revises: 474c8055a404
Create Date: 2015-06-18 16:06:21.788212

"""

# revision identifiers, used by Alembic.
revision = '167a98d74f8c'
down_revision = '474c8055a404'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('job', sa.Column('notes', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('job', 'notes')
