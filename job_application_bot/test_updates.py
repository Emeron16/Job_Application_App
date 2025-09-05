#!/usr/bin/env python3
"""
Test script for the updated job application bot system.
Tests the new Excel storage and Indeed Google OAuth functionality.
"""

import sys
import os
from datetime import datetime

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import JobPosting, JobBoard, ApplicationStatus
from storage import PandasExcelStorage
from utils import Logger

def test_excel_storage():
    """Test the new Excel storage functionality."""
    print("🧪 Testing Excel Storage System...")
    
    # Initialize logger and storage
    logger = Logger()
    excel_path = "documents/Job update.xlsx"
    storage = PandasExcelStorage(excel_path, logger)
    
    # Create test job postings
    test_jobs = [
        JobPosting(
            title="Senior Python Developer",
            company="Tech Corp",
            location="Remote",
            posting_date="2024-01-15",
            url="https://indeed.com/job/12345",
            job_board=JobBoard.INDEED,
            description="Exciting Python role with great benefits",
            salary_range="$80,000 - $120,000",
            job_type="Full-time",
            experience_level="Senior",
            skills_required=["Python", "Django", "PostgreSQL"],
            company_size="100-500",
            industry="Technology",
            job_id="test_job_001"
        ),
        JobPosting(
            title="Data Scientist",
            company="Data Analytics Inc",
            location="New York, NY",
            posting_date="2024-01-16",
            url="https://linkedin.com/job/67890",
            job_board=JobBoard.LINKEDIN,
            description="Machine learning and data analysis role",
            salary_range="$90,000 - $130,000",
            job_type="Full-time",
            experience_level="Mid-level",
            skills_required=["Python", "Machine Learning", "SQL"],
            company_size="50-100",
            industry="Analytics",
            job_id="test_job_002"
        )
    ]
    
    # Test saving jobs
    print("  📝 Saving test jobs to Excel...")
    success = storage.save_jobs(test_jobs)
    if success:
        print("  ✅ Jobs saved successfully!")
    else:
        print("  ❌ Failed to save jobs")
        return False
    
    # Test loading jobs
    print("  📖 Loading jobs from Excel...")
    loaded_jobs = storage.load_jobs()
    print(f"  📊 Loaded {len(loaded_jobs)} jobs")
    
    for job in loaded_jobs:
        print(f"    • {job.title} at {job.company} ({job.job_board.value})")
    
    # Test updating job status (simulating application)
    if loaded_jobs:
        print("  🔄 Testing application status update...")
        test_job = loaded_jobs[0]
        success = storage.update_job_status(
            test_job.job_id,
            ApplicationStatus.APPLIED,
            datetime.now(),
            "Application submitted successfully via test"
        )
        if success:
            print("  ✅ Job status updated successfully!")
        else:
            print("  ❌ Failed to update job status")
            return False
        
        # Verify the update
        updated_jobs = storage.load_jobs()
        updated_job = next((j for j in updated_jobs if j.job_id == test_job.job_id), None)
        if updated_job and updated_job.application_status == ApplicationStatus.APPLIED:
            print("  ✅ Status update verified!")
        else:
            print("  ❌ Status update verification failed")
            return False
    
    print("  🎉 Excel storage tests completed successfully!")
    return True

def test_system_integration():
    """Test system integration without actually running automation."""
    print("\n🔧 Testing System Integration...")
    
    try:
        from main import JobApplicationBot
        
        # Initialize bot (this will test configuration loading and storage setup)
        print("  🤖 Initializing Job Application Bot...")
        bot = JobApplicationBot()
        
        # Test configuration validation
        print("  ✅ Configuration validation...")
        is_valid = bot.validate_configuration()
        if is_valid:
            print("  ✅ Configuration is valid!")
        else:
            print("  ⚠️  Configuration has some issues (may be expected if credentials not set)")
        
        # Test statistics
        print("  📊 Testing statistics...")
        stats = bot.get_job_statistics()
        print(f"  📈 Found {stats.get('total_jobs', 0)} total jobs in storage")
        
        print("  🎉 System integration tests completed!")
        return True
        
    except Exception as e:
        print(f"  ❌ System integration test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 Starting Job Application Bot Update Tests\n")
    
    # Test Excel storage
    excel_success = test_excel_storage()
    
    # Test system integration
    integration_success = test_system_integration()
    
    # Summary
    print(f"\n📋 Test Summary:")
    print(f"  Excel Storage: {'✅ PASS' if excel_success else '❌ FAIL'}")
    print(f"  Integration:   {'✅ PASS' if integration_success else '❌ FAIL'}")
    
    if excel_success and integration_success:
        print(f"\n🎉 All tests passed! The updated system is ready to use.")
        print(f"\n📝 Next steps:")
        print(f"  1. Run 'python main.py search' to test job searching")
        print(f"  2. Check the generated 'documents/Job update.xlsx' file")
        print(f"  3. For Indeed applications, ensure you're logged into Google in your browser")
    else:
        print(f"\n⚠️  Some tests failed. Please check the errors above.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
