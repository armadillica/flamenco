"""Initial users support

Revision ID: 47a0943b9710
Revises: 2af604bf8b39
Create Date: 2015-06-25 16:31:03.859013

"""

# revision identifiers, used by Alembic.
revision = '47a0943b9710'
down_revision = '2af604bf8b39'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('user',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('username', sa.String(length=255), nullable=True),
    sa.Column('password', sa.String(length=255), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=True),
    sa.Column('deleted', sa.Boolean(), nullable=True),
    sa.Column('confirmed_at', sa.DateTime(), nullable=True),
    sa.Column('first_name', sa.String(length=255), nullable=True),
    sa.Column('last_name', sa.String(length=255), nullable=True),
    sa.Column('last_login_at', sa.DateTime(), nullable=True),
    sa.Column('current_login_at', sa.DateTime(), nullable=True),
    sa.Column('last_login_ip', sa.String(length=100), nullable=True),
    sa.Column('current_login_ip', sa.String(length=100), nullable=True),
    sa.Column('login_count', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email'),
    sa.UniqueConstraint('username')
    )



def downgrade():
    op.drop_table('user')
