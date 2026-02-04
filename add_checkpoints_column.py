"""
Script to add checkpoints column to jobs table
"""
import asyncio
import sys
sys.path.insert(0, 'Backend-API-DS')
from sqlalchemy import text
from app.db.session import async_engine

async def add_checkpoints_column():
    async with async_engine.begin() as conn:
        # Check if column exists
        result = await conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'jobs' AND column_name = 'checkpoints'
        """))
        exists = result.first() is not None
        
        if exists:
            print("✅ Checkpoints column already exists")
            return
        
        print("Adding checkpoints column...")
        
        # Add column
        await conn.execute(text("""
            ALTER TABLE jobs 
            ADD COLUMN checkpoints JSONB
        """))
        
        # Set default for existing rows
        await conn.execute(text("""
            UPDATE jobs 
            SET checkpoints = '{"ocrCheckpoint": "pending", "dischargeMedicationsCheckpoint": "pending", "dischargeSummaryCheckpoint": "pending"}'::jsonb
            WHERE checkpoints IS NULL
        """))
        
        print("✅ Checkpoints column added successfully")

if __name__ == "__main__":
    asyncio.run(add_checkpoints_column())
