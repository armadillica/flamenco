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
    with op.batch_alter_table('job') as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('job-user_id', 'user', ['user_id'], ['id'])


def downgrade():
    with op.batch_alter_table('job') as batch_op:
        batch_op.drop_constraint('job-user_id', type_='foreignkey')
        batch_op.drop_column('user_id')
