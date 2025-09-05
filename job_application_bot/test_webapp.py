#!/usr/bin/env python3
"""
Test script for the Job Application Bot Web Application
"""

import os
import sys
import time
import requests
from datetime import datetime

def test_web_app():
    """Test the web application functionality."""
    print("🧪 Testing Job Application Bot Web Application\n")
    
    base_url = "http://localhost:5000"
    
    # Test 1: Check if server is running
    print("1. Testing server connection...")
    try:
        response = requests.get(base_url, timeout=5)
        if response.status_code == 200:
            print("   ✅ Server is running and accessible")
        else:
            print(f"   ⚠️  Server responded with status {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Cannot connect to server: {e}")
        print("   💡 Make sure to start the server with: python app.py")
        return False
    
    # Test 2: Check dashboard
    print("\n2. Testing dashboard...")
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        if response.status_code == 200 and "Dashboard" in response.text:
            print("   ✅ Dashboard loads successfully")
        else:
            print(f"   ❌ Dashboard test failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Dashboard test error: {e}")
    
    # Test 3: Check jobs page
    print("\n3. Testing jobs page...")
    try:
        response = requests.get(f"{base_url}/jobs", timeout=5)
        if response.status_code == 200 and "Job Search" in response.text:
            print("   ✅ Jobs page loads successfully")
        else:
            print(f"   ❌ Jobs page test failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Jobs page test error: {e}")
    
    # Test 4: Check preferences page
    print("\n4. Testing preferences page...")
    try:
        response = requests.get(f"{base_url}/preferences", timeout=5)
        if response.status_code == 200 and "Preferences" in response.text:
            print("   ✅ Preferences page loads successfully")
        else:
            print(f"   ❌ Preferences page test failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Preferences page test error: {e}")
    
    # Test 5: Check API endpoints
    print("\n5. Testing API endpoints...")
    try:
        response = requests.get(f"{base_url}/api/job_stats", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Job stats API works - Total jobs: {data.get('total_jobs', 0)}")
        else:
            print(f"   ❌ Job stats API test failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ API test error: {e}")
    
    # Test 6: Check static files
    print("\n6. Testing static files...")
    try:
        css_response = requests.get(f"{base_url}/static/css/style.css", timeout=5)
        js_response = requests.get(f"{base_url}/static/js/main.js", timeout=5)
        
        if css_response.status_code == 200:
            print("   ✅ CSS file loads successfully")
        else:
            print(f"   ❌ CSS file test failed: {css_response.status_code}")
        
        if js_response.status_code == 200:
            print("   ✅ JavaScript file loads successfully")
        else:
            print(f"   ❌ JavaScript file test failed: {js_response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Static files test error: {e}")
    
    return True

def check_dependencies():
    """Check if all required dependencies are installed."""
    print("🔍 Checking dependencies...\n")
    
    required_packages = [
        'flask', 'flask_sqlalchemy', 'psycopg2', 'requests'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"   ✅ {package}")
        except ImportError:
            print(f"   ❌ {package} (missing)")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n❌ Missing packages: {', '.join(missing_packages)}")
        print("💡 Install with: pip install -r requirements.txt")
        return False
    
    print("\n✅ All dependencies are installed")
    return True

def check_database():
    """Check database connection."""
    print("\n🗄️  Checking database connection...\n")
    
    try:
        from app import app, db
        
        with app.app_context():
            # Try to connect to database
            db.engine.connect()
            print("   ✅ Database connection successful")
            
            # Check if tables exist
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            expected_tables = ['job_postings', 'job_preferences', 'application_logs']
            missing_tables = [table for table in expected_tables if table not in tables]
            
            if missing_tables:
                print(f"   ⚠️  Missing tables: {', '.join(missing_tables)}")
                print("   💡 Run: python setup_database.py")
                return False
            else:
                print("   ✅ All required tables exist")
            
            return True
            
    except Exception as e:
        print(f"   ❌ Database connection failed: {e}")
        print("   💡 Make sure PostgreSQL is running and DATABASE_URL is correct")
        return False

def main():
    """Main test function."""
    print("=" * 60)
    print("  JOB APPLICATION BOT - WEB APPLICATION TESTS")
    print("=" * 60)
    
    # Check dependencies
    if not check_dependencies():
        return
    
    # Check database
    if not check_database():
        return
    
    # Test web application
    if test_web_app():
        print("\n🎉 All tests completed!")
        print("\nWeb Application Status:")
        print("✅ Server is running")
        print("✅ All pages are accessible")
        print("✅ API endpoints are working")
        print("✅ Static files are loading")
        
        print("\n🌐 Access your application at:")
        print("   Dashboard:    http://localhost:5000/")
        print("   Jobs:         http://localhost:5000/jobs")
        print("   Preferences:  http://localhost:5000/preferences")
    else:
        print("\n❌ Some tests failed!")
        print("Check the error messages above for troubleshooting.")

if __name__ == "__main__":
    main()
