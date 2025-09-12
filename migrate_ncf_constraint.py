#!/usr/bin/env python3
"""
Database migration script to safely add unique constraint on Sale.ncf field.
This handles existing duplicate NCFs and ensures fiscal compliance.
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

def migrate_ncf_constraint():
    """
    Safely add unique constraint on Sale.ncf field.
    Handles existing duplicate NCFs by appending suffix.
    """
    database_url = get_database_url()
    engine = create_engine(database_url)
    
    try:
        with engine.connect() as conn:
            # Start transaction
            trans = conn.begin()
            
            try:
                print("🔍 Checking for existing duplicate NCFs...")
                
                # Find duplicate NCFs
                duplicate_check = conn.execute(text("""
                    SELECT ncf, COUNT(*) as count 
                    FROM sales 
                    WHERE ncf IS NOT NULL 
                    GROUP BY ncf 
                    HAVING COUNT(*) > 1
                    ORDER BY ncf
                """))
                
                duplicates = duplicate_check.fetchall()
                
                if duplicates:
                    print(f"⚠️  Found {len(duplicates)} duplicate NCF groups. Fixing...")
                    
                    for row in duplicates:
                        ncf = row[0]
                        count = row[1]
                        print(f"   Fixing NCF {ncf} ({count} duplicates)")
                        
                        # Get all sales with this duplicate NCF
                        sales_query = conn.execute(text("""
                            SELECT id FROM sales 
                            WHERE ncf = :ncf 
                            ORDER BY created_at ASC
                        """), {"ncf": ncf})
                        
                        sales = sales_query.fetchall()
                        
                        # Keep the first one, modify the rest
                        for i, sale in enumerate(sales[1:], 1):
                            new_ncf = f"{ncf}-DUP{i}"
                            conn.execute(text("""
                                UPDATE sales 
                                SET ncf = :new_ncf 
                                WHERE id = :sale_id
                            """), {"new_ncf": new_ncf, "sale_id": sale[0]})
                            
                            print(f"     Updated sale {sale[0]}: {ncf} → {new_ncf}")
                
                else:
                    print("✅ No duplicate NCFs found")
                
                print("🔧 Adding unique constraint on Sale.ncf...")
                
                # Check if constraint already exists
                constraint_check = conn.execute(text("""
                    SELECT COUNT(*) 
                    FROM information_schema.table_constraints 
                    WHERE table_name = 'sales' 
                    AND constraint_type = 'UNIQUE' 
                    AND constraint_name LIKE '%ncf%'
                """))
                
                if constraint_check.fetchone()[0] > 0:
                    print("✅ Unique constraint on NCF already exists")
                else:
                    # Add unique constraint
                    conn.execute(text("""
                        ALTER TABLE sales 
                        ADD CONSTRAINT unique_sale_ncf UNIQUE (ncf)
                    """))
                    print("✅ Unique constraint added successfully")
                
                # Commit all changes
                trans.commit()
                print("🎉 Migration completed successfully!")
                
                # Verify constraint was added
                final_check = conn.execute(text("""
                    SELECT COUNT(*) 
                    FROM information_schema.table_constraints 
                    WHERE table_name = 'sales' 
                    AND constraint_type = 'UNIQUE' 
                    AND constraint_name = 'unique_sale_ncf'
                """))
                
                if final_check.fetchone()[0] > 0:
                    print("✅ Verification: Unique constraint is active")
                else:
                    print("⚠️  Warning: Could not verify constraint was added")
                
            except Exception as e:
                trans.rollback()
                raise e
                
    except SQLAlchemyError as e:
        print(f"❌ Database error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("🚀 Starting NCF unique constraint migration...")
    migrate_ncf_constraint()
    print("✨ Migration complete! NCF assignment is now concurrency-safe.")