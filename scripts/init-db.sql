-- ===========================================
-- Rizzler - Database Initialization Script
-- Runs automatically when local Postgres starts
-- ===========================================

-- Enable pgvector extension for embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Note: Tables are created by SQLAlchemy/Alembic
-- This script only sets up extensions

