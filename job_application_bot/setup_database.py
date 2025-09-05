#!/usr/bin/env python3
"""
Database setup script for Job Application Bot
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def create_database_if_not_exists(database_url):
    """Create the database if it doesn't exist."""
    try:
        # Parse the database URL
        from urllib.parse import urlparse
        parsed = urlparse(database_url)
        
        # Connect to PostgreSQL server (not specific database)
        server_url = f"postgresql://{parsed.username}:{parsed.password}@{parsed.hostname}:{parsed.port}/postgres"
        
        # Connect and create database
        conn = psycopg2.connect(server_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        db_name = parsed.path[1:]  # Remove leading slash
        
        # Check if database exists
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
        if not cursor.fetchone():
            cursor.execute(f"CREATE DATABASE {db_name}")
            print(f"✅ Created database: {db_name}")
        else:
            print(f"✅ Database already exists: {db_name}")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error creating database: {e}")
        return False

def setup_database():
    """Set up the database and tables."""
    print("🚀 Setting up Job Application Bot Database\n")
    
    # Get database URL
    database_url = os.environ.get('DATABASE_URL', 'postgresql://localhost/job_application_bot')
    print(f"📊 Database URL: {database_url}")
    
    # Create database if it doesn't exist
    if not create_database_if_not_exists(database_url):
        return False
    
    # Test connection
    try:
        engine = create_engine(database_url)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"✅ Connected to PostgreSQL: {version[:50]}...")
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        return False
    
    # Initialize Flask app and create tables
    try:
        from app import app, db
        
        with app.app_context():
            # Create all tables
            db.create_all()
            print("✅ Created all database tables")
            
            # Check if we have any existing data
            from app import JobPosting, JobPreferences
            
            job_count = JobPosting.query.count()
            print(f"📊 Found {job_count} existing job postings")
            
            # Create default preferences if none exist
            if not JobPreferences.query.first():
                default_prefs = JobPreferences(
                    keywords='["software engineer", "python developer", "web developer"]',
                    locations='["Remote", "Hybrid", "San Francisco", "New York", "Seattle"]',
                    experience_levels='["entry", "mid", "senior"]',
                    job_types='["full-time", "contract"]',
                    exclude_keywords='["unpaid", "intern"]',
                    date_posted='week',
                    daily_application_limit=10,
                    auto_apply_enabled=False,
                    apply_to_external_sites=False
                )
                db.session.add(default_prefs)
                db.session.commit()
                print("✅ Created default job preferences")
            else:
                print("✅ Job preferences already configured")
        
        return True
        
    except Exception as e:
        print(f"❌ Error setting up database tables: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main setup function."""
    print("=" * 60)
    print("  JOB APPLICATION BOT - DATABASE SETUP")
    print("=" * 60)
    
    if setup_database():
        print("\n🎉 Database setup completed successfully!")
        print("\nNext steps:")
        print("1. Start the web application: python app.py")
        print("2. Visit http://localhost:5000 in your browser")
        print("3. Configure your job preferences")
        print("4. Start searching for jobs!")
    else:
        print("\n❌ Database setup failed!")
        print("\nTroubleshooting:")
        print("1. Make sure PostgreSQL is running")
        print("2. Check your DATABASE_URL environment variable")
        print("3. Ensure you have the required permissions")
        sys.exit(1)

if __name__ == "__main__":
    main()
