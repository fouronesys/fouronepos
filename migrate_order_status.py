#!/usr/bin/env python3
"""
Migration script to add order_status field to sales table
This allows tracking kitchen workflow stages in restaurant operations
"""

import os
from main import app, db
from models import OrderStatus
from sqlalchemy import text

def add_order_status_column():
    """Add order_status column to sales table with default value"""
    with app.app_context():
        try:
            # Check if column already exists
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='sales' AND column_name='order_status';
            """))
            
            if result.fetchone():
                print("✅ order_status column already exists in sales table")
                return
            
            print("🔄 Adding order_status column to sales table...")
            
            # Add the column with default value
            db.session.execute(text("""
                ALTER TABLE sales 
                ADD COLUMN order_status VARCHAR(20) DEFAULT 'not_sent';
            """))
            
            # Update existing records to have proper default
            db.session.execute(text("""
                UPDATE sales 
                SET order_status = 'not_sent' 
                WHERE order_status IS NULL;
            """))
            
            db.session.commit()
            print("✅ Successfully added order_status column to sales table")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error adding order_status column: {e}")
            raise

if __name__ == "__main__":
    add_order_status_column()