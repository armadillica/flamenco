"""initial setup

Revision ID: 3fc5f3e23c05
Revises: None
Create Date: 2015-01-06 15:33:40.891617

"""

# revision identifiers, used by Alembic.
revision = '3fc5f3e23c05'
down_revision = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('setting',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=True),
    sa.Column('value', sa.String(length=128), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('project',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=True),
    sa.Column('path_server', sa.Text(), nullable=True),
    sa.Column('path_linux', sa.Text(), nullable=True),
    sa.Column('path_win', sa.Text(), nullable=True),
    sa.Column('path_osx', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('manager',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ip_address', sa.String(length=15), nullable=True),
    sa.Column('port', sa.Integer(), nullable=True),
    sa.Column('name', sa.String(length=50), nullable=True),
    sa.Column('total_workers', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('ip_address', 'port', name='connection_uix')
    )
    op.create_table('job',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=True),
    sa.Column('frame_start', sa.Integer(), nullable=True),
    sa.Column('frame_end', sa.Integer(), nullable=True),
    sa.Column('chunk_size', sa.Integer(), nullable=True),
    sa.Column('current_frame', sa.Integer(), nullable=True),
    sa.Column('name', sa.String(length=120), nullable=True),
    sa.Column('filepath', sa.String(length=256), nullable=True),
    sa.Column('render_settings', sa.String(length=120), nullable=True),
    sa.Column('format', sa.String(length=10), nullable=True),
    sa.Column('status', sa.String(length=64), nullable=True),
    sa.Column('priority', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['project_id'], ['project.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('task',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('job_id', sa.Integer(), nullable=True),
    sa.Column('manager_id', sa.Integer(), nullable=True),
    sa.Column('chunk_start', sa.Integer(), nullable=True),
    sa.Column('chunk_end', sa.Integer(), nullable=True),
    sa.Column('current_frame', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(length=64), nullable=True),
    sa.Column('priority', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['job_id'], ['job.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('task')
    op.drop_table('job')
    op.drop_table('manager')
    op.drop_table('project')
    op.drop_table('setting')
