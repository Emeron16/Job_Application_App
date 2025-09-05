#!/usr/bin/env python3
"""Quick start script for Job Application Bot."""

import os
import sys
import subprocess
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible."""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        return False
    print(f"✅ Python {sys.version.split()[0]} detected")
    return True

def install_dependencies():
    """Install required dependencies."""
    print("📦 Installing dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install dependencies")
        return False

def setup_directories():
    """Create necessary directories."""
    print("📁 Setting up directories...")
    directories = ["documents", "credentials", "data", "logs"]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
    
    print("✅ Directories created")

def setup_config():
    """Setup configuration files."""
    print("⚙️ Setting up configuration...")
    
    # Copy example config if config.json doesn't exist
    if not os.path.exists("config.json") and os.path.exists("config.example.json"):
        import shutil
        shutil.copy("config.example.json", "config.json")
        print("✅ Created config.json from example")
    
    # Copy .env.example if .env doesn't exist
    if not os.path.exists(".env") and os.path.exists(".env.example"):
        import shutil
        shutil.copy(".env.example", ".env")
        print("✅ Created .env from example")
        print("⚠️  Please edit .env file with your credentials")

def check_documents():
    """Check if required documents exist."""
    print("📄 Checking documents...")
    
    resume_path = "documents/resume.pdf"
    cover_letter_path = "documents/cover_letter.txt"
    
    if not os.path.exists(resume_path):
        print(f"⚠️  Resume not found at {resume_path}")
        print("   Please add your resume.pdf to the documents folder")
    else:
        print("✅ Resume found")
    
    if not os.path.exists(cover_letter_path):
        print(f"⚠️  Cover letter template exists at {cover_letter_path}")
        print("   Please customize it with your information")
    else:
        print("✅ Cover letter template found")

def main():
    """Main setup function."""
    print("🤖 Job Application Bot - Quick Start Setup")
    print("=" * 50)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Setup directories
    setup_directories()
    
    # Install dependencies
    if not install_dependencies():
        sys.exit(1)
    
    # Setup configuration
    setup_config()
    
    # Check documents
    check_documents()
    
    print("\n🎉 Setup completed!")
    print("\nNext steps:")
    print("1. Edit .env file with your credentials")
    print("2. Add your resume.pdf to documents/ folder")
    print("3. Customize documents/cover_letter.txt")
    print("4. Run: python main.py validate")
    print("5. Run: python main.py search")
    
    print("\nFor help: python main.py --help")

if __name__ == "__main__":
    main()
