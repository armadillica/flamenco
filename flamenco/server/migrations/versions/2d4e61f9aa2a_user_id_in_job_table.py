"""User id in job table

Revision ID: 2d4e61f9aa2a
Revises: 47a0943b9710
Create Date: 2015-06-25 16:37:57.678451

"""

# revision identifiers, used by Alembic.
revision = '2d4e61f9aa2a'
down_revision = '47a0943b9710'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('job', sa.Column('user_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'job', 'user', ['user_id'], ['id'])


def downgrade():
    op.drop_constraint(None, 'job', type_='foreignkey')
    op.drop_column('job', 'user_id')
