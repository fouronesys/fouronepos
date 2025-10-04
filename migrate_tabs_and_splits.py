#!/usr/bin/env python3
"""
Migration script to add tab and split fields to sales table
This enables tabs/open accounts and bill splitting functionality for bar operations
"""

import os
from main import app, db
from sqlalchemy import text

def add_tab_and_split_columns():
    """Add parent_sale_id and split_type columns to sales table"""
    with app.app_context():
        try:
            # Check if columns already exist
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='sales' AND column_name IN ('parent_sale_id', 'split_type');
            """))
            
            existing_columns = [row[0] for row in result.fetchall()]
            
            if 'parent_sale_id' in existing_columns and 'split_type' in existing_columns:
                print("✅ Tab and split columns already exist in sales table")
                return
            
            # Add parent_sale_id column if it doesn't exist
            if 'parent_sale_id' not in existing_columns:
                print("🔄 Adding parent_sale_id column to sales table...")
                db.session.execute(text("""
                    ALTER TABLE sales 
                    ADD COLUMN parent_sale_id INTEGER REFERENCES sales(id);
                """))
                print("✅ Successfully added parent_sale_id column")
            
            # Add split_type column if it doesn't exist
            if 'split_type' not in existing_columns:
                print("🔄 Adding split_type column to sales table...")
                db.session.execute(text("""
                    ALTER TABLE sales 
                    ADD COLUMN split_type VARCHAR(20);
                """))
                print("✅ Successfully added split_type column")
            
            db.session.commit()
            print("✅ Migration completed successfully")
            print("📝 New status values available: 'tab_open', 'split_parent'")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error during migration: {e}")
            raise

if __name__ == "__main__":
    add_tab_and_split_columns()
