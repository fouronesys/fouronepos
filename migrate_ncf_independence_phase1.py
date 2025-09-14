#!/usr/bin/env python3
"""
Database migration script Phase 1: Make NCF sequences independent from cash registers.
This migration:
1. Ensures ncf_sequences.cash_register_id is nullable
2. Adds audit tables for NCF management
3. Maintains backward compatibility
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

def get_database_url():
    """Get database URL from environment variables."""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not found")
        sys.exit(1)
    return database_url

def migrate_ncf_independence_phase1():
    """
    Phase 1: Make NCF sequences independent - add audit tables and ensure nullable FK.
    """
    database_url = get_database_url()
    engine = create_engine(database_url)
    
    try:
        with engine.connect() as conn:
            # Start transaction
            trans = conn.begin()
            
            try:
                print("🔄 Phase 1: Making NCF sequences independent from cash registers...")
                
                # Step 1: Ensure ncf_sequences.cash_register_id is nullable (if not already)
                print("🔍 Checking NCF sequences table constraints...")
                
                constraint_check = conn.execute(text("""
                    SELECT column_name, is_nullable 
                    FROM information_schema.columns 
                    WHERE table_name = 'ncf_sequences' 
                    AND column_name = 'cash_register_id'
                """))
                
                result = constraint_check.fetchone()
                if result and result[1] == 'NO':
                    print("🔧 Making cash_register_id nullable in ncf_sequences...")
                    conn.execute(text("""
                        ALTER TABLE ncf_sequences 
                        ALTER COLUMN cash_register_id DROP NOT NULL
                    """))
                    print("✅ Made cash_register_id nullable")
                else:
                    print("✅ cash_register_id is already nullable")
                
                # Step 2: Create NCFSequenceAudit table
                print("🔧 Creating NCFSequenceAudit table...")
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS ncf_sequence_audit (
                        id SERIAL PRIMARY KEY,
                        sequence_id INTEGER NOT NULL REFERENCES ncf_sequences(id),
                        user_id INTEGER NOT NULL REFERENCES users(id),
                        action VARCHAR(50) NOT NULL,
                        before_json JSONB,
                        after_json JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                print("✅ NCFSequenceAudit table created")
                
                # Step 3: Create NCFLedger table for immutable NCF issuance audit
                print("🔧 Creating NCFLedger table...")
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS ncf_ledger (
                        id SERIAL PRIMARY KEY,
                        sequence_id INTEGER NOT NULL REFERENCES ncf_sequences(id),
                        sale_id INTEGER REFERENCES sales(id),
                        serie VARCHAR(3) NOT NULL,
                        number INTEGER NOT NULL,
                        ncf VARCHAR(20) NOT NULL,
                        issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        user_id INTEGER NOT NULL REFERENCES users(id),
                        cash_register_id INTEGER REFERENCES cash_registers(id),
                        CONSTRAINT unique_serie_number UNIQUE (serie, number)
                    )
                """))
                print("✅ NCFLedger table created")
                
                # Step 4: Create RegisterReassignmentLog table
                print("🔧 Creating RegisterReassignmentLog table...")
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS register_reassignment_log (
                        id SERIAL PRIMARY KEY,
                        from_register_id INTEGER NOT NULL,
                        to_register_id INTEGER NOT NULL REFERENCES cash_registers(id),
                        sales_count INTEGER DEFAULT 0,
                        sessions_count INTEGER DEFAULT 0,
                        user_id INTEGER NOT NULL REFERENCES users(id),
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                print("✅ RegisterReassignmentLog table created")
                
                # Step 5: Add indexes for performance
                print("🔧 Adding performance indexes...")
                
                # Index for NCF sequence audit queries
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_ncf_sequence_audit_sequence_id 
                    ON ncf_sequence_audit(sequence_id, created_at DESC)
                """))
                
                # Index for NCF ledger queries
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_ncf_ledger_sequence_id 
                    ON ncf_ledger(sequence_id, issued_at DESC)
                """))
                
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_ncf_ledger_sale_id 
                    ON ncf_ledger(sale_id) WHERE sale_id IS NOT NULL
                """))
                
                # Index for reassignment log
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_register_reassignment_from 
                    ON register_reassignment_log(from_register_id, created_at DESC)
                """))
                
                print("✅ Performance indexes created")
                
                # Step 6: Add constraints for data integrity
                print("🔧 Adding data integrity constraints...")
                
                # Check if constraint already exists
                constraint_exists = conn.execute(text("""
                    SELECT constraint_name 
                    FROM information_schema.check_constraints 
                    WHERE constraint_name = 'chk_current_number_bounds'
                """))
                
                if not constraint_exists.fetchone():
                    # Ensure current_number is within bounds
                    conn.execute(text("""
                        ALTER TABLE ncf_sequences 
                        ADD CONSTRAINT chk_current_number_bounds 
                        CHECK (current_number >= start_number AND current_number <= end_number + 1)
                    """))
                    print("✅ Added current_number bounds constraint")
                else:
                    print("✅ Current_number bounds constraint already exists")
                
                print("✅ Data integrity constraints added")
                
                trans.commit()
                print("✅ Phase 1 migration completed successfully!")
                print("📋 Summary:")
                print("   - NCF sequences can now exist independently of cash registers")
                print("   - Added audit tables for NCF sequence management")
                print("   - Added immutable NCF issuance ledger")
                print("   - Added register reassignment logging")
                print("   - System remains backward compatible")
                
                return True
                
            except Exception as e:
                trans.rollback()
                print(f"❌ Migration failed: {e}")
                print("🔄 All changes have been rolled back")
                return False
                
    except SQLAlchemyError as e:
        print(f"❌ Database connection error: {e}")
        return False

def verify_migration():
    """Verify that the migration was successful."""
    print("\n🔍 Verifying Phase 1 migration...")
    
    database_url = get_database_url()
    engine = create_engine(database_url)
    
    try:
        with engine.connect() as conn:
            # Check if all new tables exist
            tables_check = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('ncf_sequence_audit', 'ncf_ledger', 'register_reassignment_log')
                ORDER BY table_name
            """))
            
            tables = [row[0] for row in tables_check.fetchall()]
            expected_tables = ['ncf_ledger', 'ncf_sequence_audit', 'register_reassignment_log']
            
            if set(tables) == set(expected_tables):
                print("✅ All audit tables created successfully")
            else:
                print(f"❌ Missing tables: {set(expected_tables) - set(tables)}")
                return False
            
            # Check nullable constraint
            nullable_check = conn.execute(text("""
                SELECT is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'ncf_sequences' 
                AND column_name = 'cash_register_id'
            """))
            
            nullable = nullable_check.fetchone()
            if nullable and nullable[0] == 'YES':
                print("✅ NCF sequences cash_register_id is nullable")
            else:
                print("❌ NCF sequences cash_register_id is not nullable")
                return False
            
            print("✅ Phase 1 migration verification passed!")
            return True
            
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting NCF Independence Migration Phase 1")
    print("=" * 60)
    
    success = migrate_ncf_independence_phase1()
    if success:
        verify_migration()
        print("\n🎉 Phase 1 migration completed successfully!")
        print("📝 Next steps:")
        print("   1. Update models.py to add new audit models")
        print("   2. Update API logic to use independent NCF sequences")
        print("   3. Run Phase 2 migration to fully remove FK constraint")
    else:
        print("\n❌ Phase 1 migration failed. Please check the errors above.")
        sys.exit(1)