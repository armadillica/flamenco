"""Log table

Revision ID: 111a89ae6a55
Revises: 2d33ab39d177
Create Date: 2015-03-31 10:28:56.876364

"""

# revision identifiers, used by Alembic.
revision = '111a89ae6a55'
down_revision = '2d33ab39d177'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    op.create_table('log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('item_id', sa.Integer(), nullable=False),
    sa.Column('category', sa.String(length=64), nullable=False),
    sa.Column('log', sa.Text(), nullable=True),
    sa.Column('creation_date', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('log')
