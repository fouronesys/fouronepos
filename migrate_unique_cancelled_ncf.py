#!/usr/bin/env python3
"""
Migration to add UNIQUE constraint on CancelledNCF.ncf

This is CRITICAL for DGII compliance - prevents duplicate cancelled NCF records
which would violate Dominican Republic fiscal audit requirements.
"""

from sqlalchemy import create_engine, text
import os
import sys

def main():
    # Get database URL from environment
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)
    
    engine = create_engine(database_url)
    
    try:
        with engine.connect() as conn:
            # Begin transaction
            trans = conn.begin()
            
            try:
                # Check if unique constraint already exists
                result = conn.execute(text("""
                    SELECT COUNT(*) as constraint_exists 
                    FROM information_schema.table_constraints 
                    WHERE table_name = 'cancelled_ncfs' 
                    AND constraint_type = 'UNIQUE'
                    AND constraint_name = 'uq_cancelled_ncfs_ncf'
                """))
                
                constraint_exists = result.fetchone()[0] > 0
                
                if constraint_exists:
                    print("✓ UNIQUE constraint on cancelled_ncfs.ncf already exists")
                else:
                    # Check for duplicate NCFs before adding constraint
                    result = conn.execute(text("""
                        SELECT ncf, COUNT(*) as count 
                        FROM cancelled_ncfs 
                        GROUP BY ncf 
                        HAVING COUNT(*) > 1
                    """))
                    
                    duplicates = result.fetchall()
                    
                    if duplicates:
                        print("ERROR: Found duplicate NCFs in cancelled_ncfs table:")
                        for row in duplicates:
                            print(f"  NCF: {row[0]} appears {row[1]} times")
                        print("Please clean up duplicates before running this migration.")
                        sys.exit(1)
                    
                    # Add UNIQUE constraint
                    conn.execute(text("""
                        ALTER TABLE cancelled_ncfs 
                        ADD CONSTRAINT uq_cancelled_ncfs_ncf UNIQUE (ncf)
                    """))
                    
                    print("✓ Added UNIQUE constraint on cancelled_ncfs.ncf")
                
                # Commit transaction
                trans.commit()
                print("✓ Migration completed successfully")
                
            except Exception as e:
                trans.rollback()
                raise e
                
    except Exception as e:
        print(f"ERROR: Migration failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()