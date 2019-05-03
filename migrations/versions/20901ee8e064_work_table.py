"""work table

Revision ID: 20901ee8e064
Revises: 85d3fc2ddfbc
Create Date: 2019-04-28 00:31:31.539299

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20901ee8e064'
down_revision = '85d3fc2ddfbc'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('work', sa.Column('date', sa.DateTime(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('work', 'date')
    # ### end Alembic commands ###
