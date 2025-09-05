#!/usr/bin/env python3
"""Demo script showing Job Application Bot functionality."""

import json
import time
from datetime import datetime
from models import JobPosting, JobBoard, ApplicationStatus
from storage import LocalJSONStorage
from utils import Logger

def create_sample_jobs():
    """Create sample job postings for demonstration."""
    sample_jobs = [
        JobPosting(
            title="Senior Python Developer",
            company="TechCorp Inc.",
            location="San Francisco, CA",
            posting_date="2024-01-15",
            url="https://example.com/job1",
            job_board=JobBoard.LINKEDIN,
            description="We are looking for a senior Python developer...",
            salary_range="$120,000 - $150,000",
            job_type="full-time",
            experience_level="senior",
            skills_required=["Python", "Django", "PostgreSQL", "AWS"],
            company_size="100-500",
            industry="Technology",
            job_id="demo_job_001"
        ),
        JobPosting(
            title="Full Stack Engineer",
            company="StartupXYZ",
            location="Remote",
            posting_date="2024-01-14",
            url="https://example.com/job2",
            job_board=JobBoard.INDEED,
            description="Join our fast-growing startup as a full stack engineer...",
            salary_range="$90,000 - $120,000",
            job_type="full-time",
            experience_level="mid",
            skills_required=["JavaScript", "React", "Node.js", "MongoDB"],
            company_size="10-50",
            industry="Technology",
            job_id="demo_job_002"
        ),
        JobPosting(
            title="Data Scientist",
            company="DataAnalytics Co.",
            location="New York, NY",
            posting_date="2024-01-13",
            url="https://example.com/job3",
            job_board=JobBoard.GLASSDOOR,
            description="We're seeking a data scientist to join our analytics team...",
            salary_range="$100,000 - $130,000",
            job_type="full-time",
            experience_level="mid",
            skills_required=["Python", "R", "Machine Learning", "SQL"],
            company_size="500+",
            industry="Finance",
            job_id="demo_job_003"
        )
    ]
    
    return sample_jobs

def demo_storage_functionality():
    """Demonstrate storage functionality."""
    print("🗄️ Storage System Demo")
    print("=" * 30)
    
    # Initialize logger and storage
    logger = Logger("logs/demo_log.txt")
    storage = LocalJSONStorage("data/demo_jobs.json", logger)
    
    # Create sample jobs
    sample_jobs = create_sample_jobs()
    
    print(f"📝 Saving {len(sample_jobs)} sample jobs...")
    success = storage.save_jobs(sample_jobs)
    
    if success:
        print("✅ Jobs saved successfully")
    else:
        print("❌ Failed to save jobs")
        return
    
    # Load jobs back
    print("📖 Loading jobs from storage...")
    loaded_jobs = storage.load_jobs()
    print(f"✅ Loaded {len(loaded_jobs)} jobs")
    
    # Display loaded jobs
    for job in loaded_jobs:
        print(f"  • {job.title} at {job.company} - {job.location}")
    
    # Demonstrate status updates
    print("\n📊 Updating job statuses...")
    
    # Mark first job as applied
    if loaded_jobs:
        first_job = loaded_jobs[0]
        storage.update_job_status(
            job_id=first_job.job_id,
            status=ApplicationStatus.APPLIED,
            applied_date=datetime.now(),
            notes="Applied via LinkedIn Easy Apply"
        )
        print(f"✅ Marked '{first_job.title}' as APPLIED")
        
        # Mark second job as failed
        if len(loaded_jobs) > 1:
            second_job = loaded_jobs[1]
            storage.update_job_status(
                job_id=second_job.job_id,
                status=ApplicationStatus.FAILED,
                notes="Application form too complex"
            )
            print(f"✅ Marked '{second_job.title}' as FAILED")
    
    # Get unapplied jobs
    unapplied = storage.get_unapplied_jobs()
    print(f"\n📋 Found {len(unapplied)} unapplied jobs:")
    for job in unapplied:
        print(f"  • {job.title} at {job.company}")

def demo_configuration():
    """Demonstrate configuration system."""
    print("\n⚙️ Configuration System Demo")
    print("=" * 35)
    
    from config import Config, JobSearchConfig, ApplicationConfig
    
    # Create custom configuration
    config = Config()
    
    # Customize job search settings
    config.job_search = JobSearchConfig(
        keywords=["python developer", "data scientist"],
        locations=["Remote", "San Francisco"],
        experience_levels=["mid", "senior"],
        salary_min=100000
    )
    
    # Customize application settings
    config.application = ApplicationConfig(
        daily_application_limit=5,
        auto_apply_enabled=False
    )
    
    print("📋 Current configuration:")
    print(f"  Keywords: {config.job_search.keywords}")
    print(f"  Locations: {config.job_search.locations}")
    print(f"  Daily limit: {config.application.daily_application_limit}")
    print(f"  Auto-apply: {config.application.auto_apply_enabled}")
    
    # Save configuration
    config.save_to_file("demo_config.json")
    print("✅ Configuration saved to demo_config.json")
    
    # Validate configuration
    errors = config.validate()
    if errors:
        print("⚠️ Configuration issues:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("✅ Configuration is valid")

def demo_rate_limiting():
    """Demonstrate rate limiting functionality."""
    print("\n⏱️ Rate Limiting Demo")
    print("=" * 25)
    
    from utils import RateLimiter
    
    # Create a rate limiter (very permissive for demo)
    rate_limiter = RateLimiter(requests_per_minute=5, requests_per_hour=20)
    
    print("🔄 Simulating requests with rate limiting...")
    
    for i in range(3):
        print(f"Request {i+1}: ", end="")
        start_time = time.time()
        
        rate_limiter.wait_if_needed()
        
        elapsed = time.time() - start_time
        print(f"Completed (waited {elapsed:.2f}s)")
        
        # Simulate some work
        time.sleep(0.1)
    
    print("✅ Rate limiting demo completed")

def demo_job_filtering():
    """Demonstrate job filtering and search functionality."""
    print("\n🔍 Job Filtering Demo")
    print("=" * 27)
    
    # Get sample jobs
    sample_jobs = create_sample_jobs()
    
    print(f"📊 Original jobs: {len(sample_jobs)}")
    
    # Filter by location
    remote_jobs = [job for job in sample_jobs if "Remote" in job.location]
    print(f"🏠 Remote jobs: {len(remote_jobs)}")
    
    # Filter by salary (extract minimum salary)
    high_salary_jobs = []
    for job in sample_jobs:
        if job.salary_range and "$" in job.salary_range:
            # Simple extraction - in practice you'd use regex
            if "120,000" in job.salary_range or "130,000" in job.salary_range:
                high_salary_jobs.append(job)
    
    print(f"💰 High salary jobs ($120k+): {len(high_salary_jobs)}")
    
    # Filter by skills
    python_jobs = [job for job in sample_jobs if "Python" in job.skills_required]
    print(f"🐍 Python jobs: {len(python_jobs)}")
    
    # Show skill distribution
    all_skills = {}
    for job in sample_jobs:
        for skill in job.skills_required:
            all_skills[skill] = all_skills.get(skill, 0) + 1
    
    print("📈 Skill distribution:")
    for skill, count in sorted(all_skills.items(), key=lambda x: x[1], reverse=True):
        print(f"  {skill}: {count} jobs")

def main():
    """Run all demo functions."""
    print("🤖 Job Application Bot - Demonstration")
    print("=" * 45)
    print("This demo shows key functionality without making external requests.\n")
    
    try:
        # Run demo functions
        demo_storage_functionality()
        demo_configuration()
        demo_rate_limiting()
        demo_job_filtering()
        
        print("\n🎉 Demo completed successfully!")
        print("\nDemo files created:")
        print("  - data/demo_jobs.json (sample job data)")
        print("  - logs/demo_log.txt (demo logs)")
        print("  - demo_config.json (sample configuration)")
        
        print("\nTo run the actual application:")
        print("  1. Set up your credentials in .env")
        print("  2. Add your documents to documents/")
        print("  3. Run: python main.py search")
        
    except Exception as e:
        print(f"❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
