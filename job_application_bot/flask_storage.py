"""Flask database storage adapter for job postings."""

from typing import List, Optional
from datetime import datetime
import sys
import os

# Add the current directory to the Python path so we can import from app.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import JobPosting, ApplicationResult, ApplicationStatus, JobBoard
from utils import Logger


class FlaskDatabaseStorage:
    """Storage adapter that saves jobs directly to the Flask database."""
    
    def __init__(self, logger: Logger):
        self.logger = logger
        self._app = None
        self._db = None
        self._JobPosting = None
        
    def _get_flask_components(self):
        """Lazy loading of Flask components to avoid circular imports."""
        if self._app is None:
            try:
                from app import app, db, JobPosting as FlaskJobPosting
                self._app = app
                self._db = db
                self._JobPosting = FlaskJobPosting
                self.logger.info("Connected to Flask database")
            except ImportError as e:
                self.logger.error(f"Failed to import Flask components: {e}")
                raise
    
    def save_jobs(self, jobs: List[JobPosting]) -> bool:
        """Save job postings to Flask database."""
        try:
            self._get_flask_components()
            
            with self._app.app_context():
                new_jobs_count = 0
                
                for job in jobs:
                    # Check if job already exists
                    existing_job = self._JobPosting.query.filter_by(job_id=job.job_id).first()
                    
                    if not existing_job:
                        # Create new database record
                        db_job = self._JobPosting(
                            job_id=job.job_id,
                            title=job.title,
                            company=job.company,
                            location=job.location,
                            posting_date=job.posting_date,
                            url=job.url,
                            job_board=job.job_board.value if hasattr(job.job_board, 'value') else str(job.job_board),
                            description=job.description,
                            salary_range=job.salary_range,
                            job_type=job.job_type,
                            experience_level=job.experience_level,
                            skills_required=str(job.skills_required) if job.skills_required else None,
                            company_size=job.company_size,
                            industry=job.industry,
                            application_status='not_applied',
                            scraped_date=datetime.utcnow()
                        )
                        
                        self._db.session.add(db_job)
                        new_jobs_count += 1
                
                if new_jobs_count > 0:
                    self._db.session.commit()
                    self.logger.info(f"Saved {new_jobs_count} new jobs to Flask database")
                else:
                    self.logger.info("No new jobs to save (all jobs already exist)")
                
                return True
                
        except Exception as e:
            self.logger.error(f"Error saving jobs to Flask database: {e}")
            try:
                if self._db:
                    self._db.session.rollback()
            except:
                pass
            return False
    
    def load_jobs(self) -> List[JobPosting]:
        """Load job postings from Flask database."""
        try:
            self._get_flask_components()
            
            with self._app.app_context():
                db_jobs = self._JobPosting.query.all()
                
                jobs = []
                for db_job in db_jobs:
                    # Convert back to JobPosting model
                    job = JobPosting(
                        title=db_job.title,
                        company=db_job.company,
                        location=db_job.location,
                        posting_date=db_job.posting_date,
                        url=db_job.url,
                        job_board=JobBoard(db_job.job_board) if db_job.job_board in [b.value for b in JobBoard] else JobBoard.LINKEDIN,
                        job_id=db_job.job_id,
                        description=db_job.description,
                        salary_range=db_job.salary_range,
                        job_type=db_job.job_type,
                        experience_level=db_job.experience_level,
                        company_size=db_job.company_size,
                        industry=db_job.industry
                    )
                    jobs.append(job)
                
                self.logger.info(f"Loaded {len(jobs)} jobs from Flask database")
                return jobs
                
        except Exception as e:
            self.logger.error(f"Error loading jobs from Flask database: {e}")
            return []
    
    def update_job_status(self, job_id: str, status: ApplicationStatus, 
                         applied_date: Optional[datetime] = None, 
                         notes: str = "") -> bool:
        """Update job application status in Flask database."""
        try:
            self._get_flask_components()
            
            with self._app.app_context():
                job = self._JobPosting.query.filter_by(job_id=job_id).first()
                
                if job:
                    job.application_status = status.value if hasattr(status, 'value') else str(status)
                    if applied_date:
                        job.applied_date = applied_date
                    if notes:
                        job.application_notes = notes
                    
                    self._db.session.commit()
                    self.logger.info(f"Updated status for job {job_id} to {status}")
                    return True
                else:
                    self.logger.warning(f"Job {job_id} not found for status update")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Error updating job status: {e}")
            try:
                if self._db:
                    self._db.session.rollback()
            except:
                pass
            return False
    
    def get_unapplied_jobs(self) -> List[JobPosting]:
        """Get jobs that haven't been applied to yet."""
        try:
            self._get_flask_components()
            
            with self._app.app_context():
                db_jobs = self._JobPosting.query.filter_by(application_status='not_applied').all()
                
                jobs = []
                for db_job in db_jobs:
                    job = JobPosting(
                        title=db_job.title,
                        company=db_job.company,
                        location=db_job.location,
                        posting_date=db_job.posting_date,
                        url=db_job.url,
                        job_board=JobBoard(db_job.job_board) if db_job.job_board in [b.value for b in JobBoard] else JobBoard.LINKEDIN,
                        job_id=db_job.job_id,
                        description=db_job.description,
                        salary_range=db_job.salary_range,
                        job_type=db_job.job_type,
                        experience_level=db_job.experience_level,
                        company_size=db_job.company_size,
                        industry=db_job.industry
                    )
                    jobs.append(job)
                
                return jobs
                
        except Exception as e:
            self.logger.error(f"Error getting unapplied jobs: {e}")
            return []
    
    def log_application(self, result: ApplicationResult) -> bool:
        """Log application attempt."""
        try:
            # Update job status based on application result
            status = ApplicationStatus.APPLIED if result.success else ApplicationStatus.FAILED
            notes = f"Application result: {result.message}"
            
            return self.update_job_status(
                result.job_posting.job_id,  # Fixed: use job_posting.job_id
                status, 
                datetime.utcnow() if result.success else None,
                notes
            )
            
        except Exception as e:
            self.logger.error(f"Error logging application: {e}")
            return False 