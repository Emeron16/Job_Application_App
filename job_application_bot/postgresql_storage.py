"""
PostgreSQL storage adapter for the Job Application Bot
"""

import os
import json
from datetime import datetime
from typing import List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

from models import JobPosting, ApplicationResult, ApplicationStatus, JobBoard
from utils import Logger
from storage import StorageInterface


class PostgreSQLStorage(StorageInterface):
    """PostgreSQL storage implementation for job postings and applications."""
    
    def __init__(self, database_url: str, logger: Logger):
        self.database_url = database_url
        self.logger = logger
        self.pool = None
        self._initialize_connection_pool()
        self._create_tables()
    
    def _initialize_connection_pool(self):
        """Initialize connection pool for PostgreSQL."""
        try:
            self.pool = ThreadedConnectionPool(
                minconn=1,
                maxconn=20,
                dsn=self.database_url
            )
            self.logger.info("PostgreSQL connection pool initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize PostgreSQL connection pool: {e}")
            raise
    
    def _get_connection(self):
        """Get a connection from the pool."""
        if not self.pool:
            raise Exception("Connection pool not initialized")
        return self.pool.getconn()
    
    def _return_connection(self, conn):
        """Return a connection to the pool."""
        if self.pool and conn:
            self.pool.putconn(conn)
    
    def _create_tables(self):
        """Create necessary tables if they don't exist."""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Create job_postings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS job_postings (
                    id SERIAL PRIMARY KEY,
                    job_id VARCHAR(255) UNIQUE NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    company VARCHAR(255) NOT NULL,
                    location VARCHAR(255) NOT NULL,
                    posting_date VARCHAR(50),
                    url TEXT,
                    job_board VARCHAR(50) NOT NULL,
                    description TEXT,
                    salary_range VARCHAR(255),
                    job_type VARCHAR(100),
                    experience_level VARCHAR(100),
                    skills_required TEXT,
                    company_size VARCHAR(100),
                    industry VARCHAR(100),
                    application_status VARCHAR(50) DEFAULT 'not_applied',
                    applied_date TIMESTAMP,
                    application_notes TEXT,
                    scraped_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Create application_logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS application_logs (
                    id SERIAL PRIMARY KEY,
                    job_posting_id INTEGER REFERENCES job_postings(id),
                    job_title VARCHAR(255) NOT NULL,
                    company VARCHAR(255) NOT NULL,
                    job_url TEXT,
                    success BOOLEAN NOT NULL,
                    message TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Create job_preferences table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS job_preferences (
                    id SERIAL PRIMARY KEY,
                    keywords TEXT,
                    locations TEXT,
                    experience_levels TEXT,
                    job_types TEXT,
                    exclude_keywords TEXT,
                    salary_min INTEGER,
                    date_posted VARCHAR(50),
                    daily_application_limit INTEGER DEFAULT 10,
                    auto_apply_enabled BOOLEAN DEFAULT FALSE,
                    apply_to_external_sites BOOLEAN DEFAULT FALSE,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Create indexes for better performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_job_postings_job_id ON job_postings(job_id);
                CREATE INDEX IF NOT EXISTS idx_job_postings_status ON job_postings(application_status);
                CREATE INDEX IF NOT EXISTS idx_job_postings_board ON job_postings(job_board);
                CREATE INDEX IF NOT EXISTS idx_job_postings_scraped_date ON job_postings(scraped_date);
                CREATE INDEX IF NOT EXISTS idx_application_logs_timestamp ON application_logs(timestamp);
            """)
            
            conn.commit()
            self.logger.info("PostgreSQL tables created successfully")
            
        except Exception as e:
            if conn:
                conn.rollback()
            self.logger.error(f"Error creating PostgreSQL tables: {e}")
            raise
        finally:
            if conn:
                self._return_connection(conn)
    
    def save_jobs(self, jobs: List[JobPosting]) -> bool:
        """Save job postings to PostgreSQL."""
        if not jobs:
            return True
            
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            new_jobs_count = 0
            for job in jobs:
                # Check if job already exists
                cursor.execute("SELECT id FROM job_postings WHERE job_id = %s", (job.job_id,))
                if cursor.fetchone():
                    continue  # Skip existing jobs
                
                # Insert new job
                cursor.execute("""
                    INSERT INTO job_postings (
                        job_id, title, company, location, posting_date, url, job_board,
                        description, salary_range, job_type, experience_level, skills_required,
                        company_size, industry, application_status, applied_date, application_notes,
                        scraped_date
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    job.job_id, job.title, job.company, job.location, job.posting_date,
                    job.url, job.job_board.value, job.description, job.salary_range,
                    job.job_type, job.experience_level, json.dumps(job.skills_required),
                    job.company_size, job.industry, job.application_status.value,
                    job.applied_date, job.application_notes, job.scraped_date
                ))
                new_jobs_count += 1
            
            conn.commit()
            self.logger.info(f"Saved {new_jobs_count} new jobs to PostgreSQL")
            return True
            
        except Exception as e:
            if conn:
                conn.rollback()
            self.logger.error(f"Error saving jobs to PostgreSQL: {e}")
            return False
        finally:
            if conn:
                self._return_connection(conn)
    
    def load_jobs(self) -> List[JobPosting]:
        """Load job postings from PostgreSQL."""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT * FROM job_postings 
                ORDER BY scraped_date DESC
            """)
            
            rows = cursor.fetchall()
            jobs = []
            
            for row in rows:
                try:
                    job = JobPosting(
                        title=row['title'],
                        company=row['company'],
                        location=row['location'],
                        posting_date=row['posting_date'] or '',
                        url=row['url'] or '',
                        job_board=JobBoard(row['job_board']),
                        description=row['description'] or '',
                        salary_range=row['salary_range'] or '',
                        job_type=row['job_type'] or '',
                        experience_level=row['experience_level'] or '',
                        skills_required=json.loads(row['skills_required']) if row['skills_required'] else [],
                        company_size=row['company_size'] or '',
                        industry=row['industry'] or '',
                        application_status=ApplicationStatus(row['application_status']),
                        applied_date=row['applied_date'],
                        application_notes=row['application_notes'] or '',
                        scraped_date=row['scraped_date'] or datetime.now(),
                        job_id=row['job_id']
                    )
                    jobs.append(job)
                except Exception as e:
                    self.logger.error(f"Error parsing job record: {e}")
                    continue
            
            self.logger.info(f"Loaded {len(jobs)} jobs from PostgreSQL")
            return jobs
            
        except Exception as e:
            self.logger.error(f"Error loading jobs from PostgreSQL: {e}")
            return []
        finally:
            if conn:
                self._return_connection(conn)
    
    def update_job_status(self, job_id: str, status: ApplicationStatus, 
                         applied_date: Optional[datetime] = None, 
                         notes: str = "") -> bool:
        """Update job application status in PostgreSQL."""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            update_parts = ["application_status = %s", "updated_at = CURRENT_TIMESTAMP"]
            params = [status.value]
            
            if applied_date:
                update_parts.append("applied_date = %s")
                params.append(applied_date)
            
            if notes:
                update_parts.append("application_notes = %s")
                params.append(notes)
            
            params.append(job_id)
            
            cursor.execute(f"""
                UPDATE job_postings 
                SET {', '.join(update_parts)}
                WHERE job_id = %s
            """, params)
            
            if cursor.rowcount > 0:
                conn.commit()
                self.logger.info(f"Updated job {job_id} status to {status.value}")
                return True
            else:
                self.logger.warning(f"Job {job_id} not found for status update")
                return False
                
        except Exception as e:
            if conn:
                conn.rollback()
            self.logger.error(f"Error updating job status in PostgreSQL: {e}")
            return False
        finally:
            if conn:
                self._return_connection(conn)
    
    def get_unapplied_jobs(self) -> List[JobPosting]:
        """Get jobs that haven't been applied to yet."""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT * FROM job_postings 
                WHERE application_status = 'not_applied'
                ORDER BY scraped_date DESC
            """)
            
            rows = cursor.fetchall()
            jobs = []
            
            for row in rows:
                try:
                    job = JobPosting(
                        title=row['title'],
                        company=row['company'],
                        location=row['location'],
                        posting_date=row['posting_date'] or '',
                        url=row['url'] or '',
                        job_board=JobBoard(row['job_board']),
                        description=row['description'] or '',
                        salary_range=row['salary_range'] or '',
                        job_type=row['job_type'] or '',
                        experience_level=row['experience_level'] or '',
                        skills_required=json.loads(row['skills_required']) if row['skills_required'] else [],
                        company_size=row['company_size'] or '',
                        industry=row['industry'] or '',
                        application_status=ApplicationStatus(row['application_status']),
                        applied_date=row['applied_date'],
                        application_notes=row['application_notes'] or '',
                        scraped_date=row['scraped_date'] or datetime.now(),
                        job_id=row['job_id']
                    )
                    jobs.append(job)
                except Exception as e:
                    self.logger.error(f"Error parsing job record: {e}")
                    continue
            
            return jobs
            
        except Exception as e:
            self.logger.error(f"Error getting unapplied jobs from PostgreSQL: {e}")
            return []
        finally:
            if conn:
                self._return_connection(conn)
    
    def log_application(self, result: ApplicationResult) -> bool:
        """Log application attempt to PostgreSQL."""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Get job posting ID
            cursor.execute("SELECT id FROM job_postings WHERE job_id = %s", (result.job_posting.job_id,))
            row = cursor.fetchone()
            job_posting_id = row[0] if row else None
            
            # Insert application log
            cursor.execute("""
                INSERT INTO application_logs (
                    job_posting_id, job_title, company, job_url, success, message, timestamp
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                job_posting_id,
                result.job_posting.title,
                result.job_posting.company,
                result.job_posting.url,
                result.success,
                result.message,
                result.timestamp
            ))
            
            # Update job status
            status = ApplicationStatus.APPLIED if result.success else ApplicationStatus.FAILED
            self.update_job_status(
                result.job_posting.job_id,
                status,
                result.timestamp if result.success else None,
                result.message
            )
            
            conn.commit()
            self.logger.info(f"Logged application for {result.job_posting.title}")
            return True
            
        except Exception as e:
            if conn:
                conn.rollback()
            self.logger.error(f"Error logging application to PostgreSQL: {e}")
            return False
        finally:
            if conn:
                self._return_connection(conn)
    
    def get_job_statistics(self) -> dict:
        """Get job statistics from PostgreSQL."""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Total jobs
            cursor.execute("SELECT COUNT(*) FROM job_postings")
            total_jobs = cursor.fetchone()[0]
            
            # Jobs by status
            cursor.execute("""
                SELECT application_status, COUNT(*) 
                FROM job_postings 
                GROUP BY application_status
            """)
            status_counts = dict(cursor.fetchall())
            
            # Jobs by board
            cursor.execute("""
                SELECT job_board, COUNT(*) 
                FROM job_postings 
                GROUP BY job_board
            """)
            board_counts = dict(cursor.fetchall())
            
            # Recent jobs (last 7 days)
            cursor.execute("""
                SELECT COUNT(*) FROM job_postings 
                WHERE scraped_date >= NOW() - INTERVAL '7 days'
            """)
            recent_jobs = cursor.fetchone()[0]
            
            return {
                'total_jobs': total_jobs,
                'by_status': status_counts,
                'by_job_board': board_counts,
                'recent_jobs': recent_jobs
            }
            
        except Exception as e:
            self.logger.error(f"Error getting job statistics from PostgreSQL: {e}")
            return {'total_jobs': 0}
        finally:
            if conn:
                self._return_connection(conn)
    
    def close(self):
        """Close all connections in the pool."""
        if self.pool:
            self.pool.closeall()
            self.logger.info("PostgreSQL connection pool closed")


class PostgreSQLStorageManager:
    """Enhanced storage manager for PostgreSQL with fallback support."""
    
    def __init__(self, database_url: str, logger: Logger, fallback_storage=None):
        self.logger = logger
        self.primary_storage = None
        self.fallback_storage = fallback_storage
        
        try:
            self.primary_storage = PostgreSQLStorage(database_url, logger)
            self.logger.info("Using PostgreSQL as primary storage")
        except Exception as e:
            self.logger.warning(f"Failed to setup PostgreSQL storage: {e}")
            if fallback_storage:
                self.primary_storage = fallback_storage
                self.logger.info("Using fallback storage")
            else:
                raise
    
    def save_jobs(self, jobs: List[JobPosting]) -> bool:
        """Save jobs using primary storage with fallback."""
        success = self.primary_storage.save_jobs(jobs)
        
        if not success and self.fallback_storage and self.primary_storage != self.fallback_storage:
            self.logger.warning("Primary storage failed, trying fallback")
            success = self.fallback_storage.save_jobs(jobs)
        
        return success
    
    def load_jobs(self) -> List[JobPosting]:
        """Load jobs from primary storage with fallback."""
        jobs = self.primary_storage.load_jobs()
        
        if not jobs and self.fallback_storage and self.primary_storage != self.fallback_storage:
            jobs = self.fallback_storage.load_jobs()
        
        return jobs
    
    def update_job_status(self, job_id: str, status: ApplicationStatus, 
                         applied_date: Optional[datetime] = None, 
                         notes: str = "") -> bool:
        """Update job status in both storages."""
        primary_success = self.primary_storage.update_job_status(
            job_id, status, applied_date, notes
        )
        
        fallback_success = True
        if self.fallback_storage and self.primary_storage != self.fallback_storage:
            fallback_success = self.fallback_storage.update_job_status(
                job_id, status, applied_date, notes
            )
        
        return primary_success or fallback_success
    
    def get_unapplied_jobs(self) -> List[JobPosting]:
        """Get unapplied jobs from primary storage."""
        return self.primary_storage.get_unapplied_jobs()
    
    def log_application(self, result: ApplicationResult) -> bool:
        """Log application in both storages."""
        primary_success = self.primary_storage.log_application(result)
        
        fallback_success = True
        if self.fallback_storage and self.primary_storage != self.fallback_storage:
            fallback_success = self.fallback_storage.log_application(result)
        
        return primary_success or fallback_success
    
    def get_job_statistics(self) -> dict:
        """Get job statistics from primary storage."""
        return self.primary_storage.get_job_statistics()
    
    def close(self):
        """Close storage connections."""
        if hasattr(self.primary_storage, 'close'):
            self.primary_storage.close()
        if self.fallback_storage and hasattr(self.fallback_storage, 'close'):
            self.fallback_storage.close()
