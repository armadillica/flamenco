"""Project table cleanup

Revision ID: 86dad093873
Revises: 2d4e61f9aa2a
Create Date: 2015-10-18 21:04:19.180507

"""

# revision identifiers, used by Alembic.
revision = '86dad093873'
down_revision = '2d4e61f9aa2a'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('project', sa.Column('creation_date', sa.DateTime(), nullable=True))
    op.add_column('project', sa.Column('status', sa.String(length=80), nullable=True))
    with op.batch_alter_table('project', schema=None) as batch_op:
        batch_op.drop_column('path_linux')
        batch_op.drop_column('render_path_linux')
        batch_op.drop_column('render_path_osx')
        batch_op.drop_column('path_win')
        batch_op.drop_column('render_path_server')
        batch_op.drop_column('render_path_win')
        batch_op.drop_column('path_osx')
        batch_op.drop_column('path_server')


def downgrade():
    op.add_column('project', sa.Column('path_server', sa.TEXT(), nullable=True))
    op.add_column('project', sa.Column('path_osx', sa.TEXT(), nullable=True))
    op.add_column('project', sa.Column('render_path_win', sa.TEXT(), nullable=True))
    op.add_column('project', sa.Column('render_path_server', sa.TEXT(), nullable=True))
    op.add_column('project', sa.Column('path_win', sa.TEXT(), nullable=True))
    op.add_column('project', sa.Column('render_path_osx', sa.TEXT(), nullable=True))
    op.add_column('project', sa.Column('render_path_linux', sa.TEXT(), nullable=True))
    op.add_column('project', sa.Column('path_linux', sa.TEXT(), nullable=True))
    with op.batch_alter_table('project', schema=None) as batch_op:
        batch_op.drop_column('status')
        batch_op.drop_column('creation_date')
