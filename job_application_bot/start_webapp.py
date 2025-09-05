#!/usr/bin/env python3
"""
Startup script for Job Application Bot Web Application
"""

import os
import sys
import subprocess
import time
from pathlib import Path

def check_prerequisites():
    """Check if all prerequisites are met."""
    print("🔍 Checking prerequisites...\n")
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ required")
        return False
    else:
        print(f"✅ Python {sys.version.split()[0]}")
    
    # Check if requirements are installed
    try:
        import flask, psycopg2, sqlalchemy
        print("✅ Required packages installed")
    except ImportError as e:
        print(f"❌ Missing package: {e.name}")
        print("💡 Run: pip install -r requirements.txt")
        return False
    
    # Check if PostgreSQL is accessible
    database_url = os.environ.get('DATABASE_URL', 'postgresql://localhost/job_application_bot')
    try:
        import psycopg2
        conn = psycopg2.connect(database_url)
        conn.close()
        print("✅ PostgreSQL connection successful")
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        print("💡 Make sure PostgreSQL is running and DATABASE_URL is correct")
        return False
    
    return True

def setup_environment():
    """Set up environment variables if not already set."""
    print("\n⚙️  Setting up environment...\n")
    
    # Default environment variables
    defaults = {
        'DATABASE_URL': 'postgresql://localhost/job_application_bot',
        'SECRET_KEY': 'dev-secret-key-change-in-production',
        'FLASK_ENV': 'development'
    }
    
    for key, value in defaults.items():
        if not os.environ.get(key):
            os.environ[key] = value
            print(f"✅ Set {key}")
        else:
            print(f"✅ {key} already configured")

def initialize_database():
    """Initialize database if needed."""
    print("\n🗄️  Initializing database...\n")
    
    try:
        from app import app, db
        
        with app.app_context():
            # Create tables
            db.create_all()
            print("✅ Database tables created/verified")
            
            # Check for default preferences
            from app import JobPreferences
            if not JobPreferences.query.first():
                default_prefs = JobPreferences(
                    keywords='["software engineer", "python developer", "web developer"]',
                    locations='["Remote", "Hybrid", "San Francisco", "New York"]',
                    experience_levels='["entry", "mid", "senior"]',
                    job_types='["full-time", "contract"]',
                    exclude_keywords='[]',
                    date_posted='week'
                )
                db.session.add(default_prefs)
                db.session.commit()
                print("✅ Default preferences created")
            else:
                print("✅ Preferences already configured")
                
        return True
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False

def start_application():
    """Start the Flask application."""
    print("\n🚀 Starting Job Application Bot Web Interface...\n")
    
    try:
        from app import app
        
        print("🌐 Web application starting...")
        print("📊 Dashboard: http://localhost:5000/")
        print("🔍 Jobs: http://localhost:5000/jobs")
        print("⚙️  Preferences: http://localhost:5000/preferences")
        print("\n💡 Press Ctrl+C to stop the server")
        print("-" * 50)
        
        # Start the Flask development server
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=True,
            use_reloader=False  # Avoid double startup messages
        )
        
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down gracefully...")
    except Exception as e:
        print(f"\n❌ Failed to start application: {e}")

def main():
    """Main startup function."""
    print("=" * 60)
    print("  JOB APPLICATION BOT - WEB INTERFACE STARTUP")
    print("=" * 60)
    
    # Check prerequisites
    if not check_prerequisites():
        print("\n❌ Prerequisites not met. Please fix the issues above.")
        sys.exit(1)
    
    # Setup environment
    setup_environment()
    
    # Initialize database
    if not initialize_database():
        print("\n❌ Database initialization failed.")
        sys.exit(1)
    
    # Start application
    start_application()

if __name__ == "__main__":
    main()
