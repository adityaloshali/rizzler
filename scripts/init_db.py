#!/usr/bin/env python3
"""
Database initialization script.
Creates all tables and enables required extensions on Supabase/PostgreSQL.

Usage:
    python scripts/init_db.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.models import Base


async def init_database():
    """Initialize the database with all tables and extensions."""
    
    if not settings.database_url:
        print("❌ DATABASE_URL not set in environment")
        print("   Set it in your .env file or environment variables")
        sys.exit(1)
    
    print(f"🔗 Connecting to database...")
    print(f"   URL: {settings.async_database_url[:50]}...")
    
    engine = create_async_engine(
        settings.async_database_url,
        echo=True,  # Show SQL statements
    )
    
    async with engine.begin() as conn:
        # Enable pgvector extension
        print("\n📦 Enabling pgvector extension...")
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            print("   ✅ pgvector enabled")
        except Exception as e:
            print(f"   ⚠️  pgvector: {e}")
        
        # Enable uuid-ossp extension
        print("\n📦 Enabling uuid-ossp extension...")
        try:
            await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
            print("   ✅ uuid-ossp enabled")
        except Exception as e:
            print(f"   ⚠️  uuid-ossp: {e}")
        
        # Create all tables
        print("\n🏗️  Creating tables...")
        await conn.run_sync(Base.metadata.create_all)
        print("   ✅ All tables created")
    
    await engine.dispose()
    
    print("\n✨ Database initialization complete!")
    print("\nCreated tables:")
    for table in Base.metadata.tables:
        print(f"   - {table}")


if __name__ == "__main__":
    print("=" * 50)
    print("🚀 Rizzler Database Initialization")
    print("=" * 50)
    asyncio.run(init_database())

