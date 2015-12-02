"""initial setup

Revision ID: 2c4b6eae4733
Revises: None
Create Date: 2015-01-06 15:44:35.647924

"""

# revision identifiers, used by Alembic.
revision = '2c4b6eae4733'
down_revision = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('worker',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ip_address', sa.String(length=15), nullable=True),
    sa.Column('port', sa.Integer(), nullable=True),
    sa.Column('hostname', sa.String(length=50), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=True),
    sa.Column('connection', sa.String(length=20), nullable=True),
    sa.Column('system', sa.String(length=50), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('ip_address', 'port', name='connection_uix')
    )
    op.create_table('task_type',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=40), nullable=False),
    sa.Column('url', sa.String(length=128), nullable=False),
    sa.Column('pre_command', sa.String(length=256), nullable=True),
    sa.Column('post_command', sa.String(length=256), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('task',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('server_id', sa.Integer(), nullable=False),
    sa.Column('worker_id', sa.Integer(), nullable=True),
    sa.Column('priority', sa.Integer(), nullable=True),
    sa.Column('frame_start', sa.Integer(), nullable=True),
    sa.Column('frame_end', sa.Integer(), nullable=True),
    sa.Column('frame_current', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(length=10), nullable=True),
    sa.Column('format', sa.String(length=10), nullable=True),
    sa.Column('file_path_linux', sa.String(length=256), nullable=True),
    sa.Column('file_path_win', sa.String(length=256), nullable=True),
    sa.Column('file_path_osx', sa.String(length=256), nullable=True),
    sa.Column('output', sa.String(length=256), nullable=True),
    sa.Column('settings', sa.String(length=50), nullable=True),
    sa.Column('pid', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('task')
    op.drop_table('task_type')
    op.drop_table('worker')
