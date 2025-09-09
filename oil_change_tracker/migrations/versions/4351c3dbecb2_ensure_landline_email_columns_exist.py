"""ensure_landline_email_columns_exist

Revision ID: 4351c3dbecb2
Revises: 814cbfa3ea34
Create Date: 2025-09-09 12:24:03.945898

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4351c3dbecb2'
down_revision: Union[str, None] = '814cbfa3ea34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure landline and email columns exist in customers table
    # This migration will check if columns exist before adding them
    
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    try:
        columns = [col['name'] for col in inspector.get_columns('customers')]
        print(f"Current customers columns: {columns}")
        
        if 'landline' not in columns:
            op.add_column('customers', sa.Column('landline', sa.String(20), nullable=True))
            print("✅ Added landline column to customers table")
        else:
            print("ℹ️ landline column already exists")
            
        if 'email' not in columns:
            op.add_column('customers', sa.Column('email', sa.String(255), nullable=True))
            print("✅ Added email column to customers table")
        else:
            print("ℹ️ email column already exists")
            
    except Exception as e:
        print(f"❌ Error in migration: {e}")
        # If customers table doesn't exist, create it with all columns
        if "no such table" in str(e).lower() or "does not exist" in str(e).lower():
            print("Creating customers table with all columns...")
            op.create_table('customers',
                sa.Column('id', sa.Integer(), primary_key=True),
                sa.Column('first_name', sa.String(100), nullable=False),
                sa.Column('last_name', sa.String(100), nullable=False),
                sa.Column('phone', sa.String(20), nullable=False),
                sa.Column('landline', sa.String(20), nullable=True),
                sa.Column('email', sa.String(255), nullable=True),
            )
            op.create_index('ix_customers_id', 'customers', ['id'])
            op.create_index('ix_customers_first_name', 'customers', ['first_name'])
            op.create_index('ix_customers_last_name', 'customers', ['last_name'])
            op.create_index('ix_customers_phone', 'customers', ['phone'])
            print("✅ Created customers table with all columns")


def downgrade() -> None:
    # Remove the columns if they exist
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    try:
        columns = [col['name'] for col in inspector.get_columns('customers')]
        
        if 'email' in columns:
            op.drop_column('customers', 'email')
            print("✅ Removed email column")
            
        if 'landline' in columns:
            op.drop_column('customers', 'landline')
            print("✅ Removed landline column")
            
    except Exception as e:
        print(f"⚠️ Error in downgrade: {e}")
