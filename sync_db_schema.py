"""
Script to synchronize database schema by recreating Phase 2 tables.
This script drops the templates table and recreates all tables to ensure alignment with models.
"""
import asyncio
import sys
from sqlalchemy import text
from app.db.session import async_engine
from app.db.base import Base
# Import all models to ensure they are registered with Base.metadata
import app.db.models 

async def sync_db():
    async with async_engine.begin() as conn:
        print("🔍 Checking database schema...")
        
        # Drop problematic tables (these are Phase 2 tables that might be outdated)
        # We drop them in reverse order of dependencies
        tables_to_drop = ["templates", "discharge_summaries", "patients", "upload_sessions"]
        
        for table in tables_to_drop:
            try:
                print(f"🗑️  Dropping table {table} if it exists...")
                await conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
            except Exception as e:
                print(f"⚠️  Could not drop table {table}: {e}")
        
        print("🏗️  Recreating all tables from models...")
        await conn.run_sync(Base.metadata.create_all)
        
        print("✅ Database schema synchronized successfully!")

if __name__ == "__main__":
    # Ensure project path is in sys.path
    import os
    if os.path.exists("Backend-API-DS"):
        sys.path.insert(0, "Backend-API-DS")
        
    asyncio.run(sync_db())
