"""Data storage implementations for job postings and application tracking."""

import json
import os
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from datetime import datetime
import pandas as pd
from pathlib import Path

try:
    import gspread
    from google.auth.exceptions import GoogleAuthError
    from google.oauth2.service_account import Credentials
    GOOGLE_SHEETS_AVAILABLE = True
except ImportError:
    GOOGLE_SHEETS_AVAILABLE = False

from models import JobPosting, ApplicationResult, ApplicationStatus, JobBoard
from utils import Logger, FileManager


class StorageInterface(ABC):
    """Abstract interface for data storage."""
    
    @abstractmethod
    def save_jobs(self, jobs: List[JobPosting]) -> bool:
        """Save job postings to storage."""
        pass
    
    @abstractmethod
    def load_jobs(self) -> List[JobPosting]:
        """Load job postings from storage."""
        pass
    
    @abstractmethod
    def update_job_status(self, job_id: str, status: ApplicationStatus, 
                         applied_date: Optional[datetime] = None, 
                         notes: str = "") -> bool:
        """Update job application status."""
        pass
    
    @abstractmethod
    def get_unapplied_jobs(self) -> List[JobPosting]:
        """Get jobs that haven't been applied to yet."""
        pass
    
    @abstractmethod
    def log_application(self, result: ApplicationResult) -> bool:
        """Log application attempt."""
        pass


class LocalJSONStorage(StorageInterface):
    """Local JSON file storage implementation."""
    
    def __init__(self, file_path: str, logger: Logger):
        self.file_path = file_path
        self.logger = logger
        self.file_manager = FileManager()
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    def save_jobs(self, jobs: List[JobPosting]) -> bool:
        """Save job postings to JSON file."""
        try:
            # Load existing jobs
            existing_jobs = self.load_jobs()
            existing_job_ids = {job.job_id for job in existing_jobs}
            
            # Add new jobs (avoid duplicates)
            new_jobs = [job for job in jobs if job.job_id not in existing_job_ids]
            all_jobs = existing_jobs + new_jobs
            
            # Convert to dictionaries
            jobs_data = [job.to_dict() for job in all_jobs]
            
            # Save to file
            self.file_manager.write_json(self.file_path, {
                'jobs': jobs_data,
                'last_updated': datetime.now().isoformat(),
                'total_jobs': len(all_jobs)
            })
            
            self.logger.info(f"Saved {len(new_jobs)} new jobs to {self.file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving jobs to JSON: {e}")
            return False
    
    def load_jobs(self) -> List[JobPosting]:
        """Load job postings from JSON file."""
        try:
            data = self.file_manager.read_json(self.file_path)
            if not data or 'jobs' not in data:
                return []
            
            jobs = []
            for job_data in data['jobs']:
                try:
                    job = JobPosting.from_dict(job_data)
                    jobs.append(job)
                except Exception as e:
                    self.logger.error(f"Error loading job from data: {e}")
                    continue
            
            self.logger.info(f"Loaded {len(jobs)} jobs from {self.file_path}")
            return jobs
            
        except Exception as e:
            self.logger.error(f"Error loading jobs from JSON: {e}")
            return []
    
    def update_job_status(self, job_id: str, status: ApplicationStatus, 
                         applied_date: Optional[datetime] = None, 
                         notes: str = "") -> bool:
        """Update job application status."""
        try:
            jobs = self.load_jobs()
            updated = False
            
            for job in jobs:
                if job.job_id == job_id:
                    job.application_status = status
                    if applied_date:
                        job.applied_date = applied_date
                    if notes:
                        job.application_notes = notes
                    updated = True
                    break
            
            if updated:
                self.save_jobs(jobs)
                self.logger.info(f"Updated job {job_id} status to {status.value}")
                return True
            else:
                self.logger.warning(f"Job {job_id} not found for status update")
                return False
                
        except Exception as e:
            self.logger.error(f"Error updating job status: {e}")
            return False
    
    def get_unapplied_jobs(self) -> List[JobPosting]:
        """Get jobs that haven't been applied to yet."""
        jobs = self.load_jobs()
        return [job for job in jobs if job.application_status == ApplicationStatus.NOT_APPLIED]
    
    def log_application(self, result: ApplicationResult) -> bool:
        """Log application attempt to separate file."""
        try:
            log_file = self.file_path.replace('.json', '_applications.json')
            
            # Load existing application logs
            logs_data = self.file_manager.read_json(log_file) or {'applications': []}
            
            # Add new log
            logs_data['applications'].append(result.to_dict())
            logs_data['last_updated'] = datetime.now().isoformat()
            
            # Save logs
            self.file_manager.write_json(log_file, logs_data)
            return True
            
        except Exception as e:
            self.logger.error(f"Error logging application: {e}")
            return False


class PandasExcelStorage(StorageInterface):
    """Local Excel file storage using pandas for Google Sheets compatibility."""
    
    def __init__(self, file_path: str, logger: Logger):
        self.file_path = file_path
        self.logger = logger
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Initialize Excel file if it doesn't exist
        self._initialize_excel_file()
    
    def _initialize_excel_file(self):
        """Initialize Excel file with proper headers if it doesn't exist."""
        if not os.path.exists(self.file_path):
            # Create DataFrame with required columns
            df = pd.DataFrame(columns=[
                'title', 'company', 'time_applied', 'location', 'description', 
                'salary', 'experience', 'job_type', 'job_board', 'url', 
                'posting_date', 'application_status', 'job_id', 'scraped_date',
                'skills_required', 'company_size', 'industry', 'application_notes'
            ])
            
            # Save to Excel file
            df.to_excel(self.file_path, index=False, engine='openpyxl')
            self.logger.info(f"Created new Excel file: {self.file_path}")
    
    def save_jobs(self, jobs: List[JobPosting]) -> bool:
        """Save job postings to Excel file."""
        try:
            # Load existing data
            try:
                existing_df = pd.read_excel(self.file_path, engine='openpyxl')
                existing_job_ids = set(existing_df['job_id'].astype(str))
            except (FileNotFoundError, KeyError):
                existing_df = pd.DataFrame()
                existing_job_ids = set()
            
            # Convert new jobs to DataFrame
            new_jobs_data = []
            for job in jobs:
                if job.job_id not in existing_job_ids:
                    job_data = {
                        'title': job.title,
                        'company': job.company,
                        'time_applied': job.applied_date.isoformat() if job.applied_date else '',
                        'location': job.location,
                        'description': job.description,
                        'salary': job.salary_range,
                        'experience': job.experience_level,
                        'job_type': job.job_type,
                        'job_board': job.job_board.value,
                        'url': job.url,
                        'posting_date': job.posting_date,
                        'application_status': job.application_status.value,
                        'job_id': job.job_id,
                        'scraped_date': job.scraped_date.isoformat(),
                        'skills_required': ', '.join(job.skills_required),
                        'company_size': job.company_size,
                        'industry': job.industry,
                        'application_notes': job.application_notes
                    }
                    new_jobs_data.append(job_data)
            
            if new_jobs_data:
                new_df = pd.DataFrame(new_jobs_data)
                
                # Combine with existing data
                if not existing_df.empty:
                    combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                else:
                    combined_df = new_df
                
                # Save to Excel
                combined_df.to_excel(self.file_path, index=False, engine='openpyxl')
                self.logger.info(f"Saved {len(new_jobs_data)} new jobs to {self.file_path}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving jobs to Excel: {e}")
            return False
    
    def load_jobs(self) -> List[JobPosting]:
        """Load job postings from Excel file."""
        try:
            if not os.path.exists(self.file_path):
                return []
                
            df = pd.read_excel(self.file_path, engine='openpyxl')
            
            jobs = []
            for _, row in df.iterrows():
                try:
                    # Handle datetime parsing
                    scraped_date = datetime.now()
                    if pd.notna(row.get('scraped_date')):
                        try:
                            scraped_date = datetime.fromisoformat(str(row['scraped_date']))
                        except:
                            pass
                    
                    applied_date = None
                    if pd.notna(row.get('time_applied')) and str(row['time_applied']).strip():
                        try:
                            applied_date = datetime.fromisoformat(str(row['time_applied']))
                        except:
                            pass
                    
                    # Create JobPosting object
                    job = JobPosting(
                        title=str(row.get('title', '')),
                        company=str(row.get('company', '')),
                        location=str(row.get('location', '')),
                        posting_date=str(row.get('posting_date', '')),
                        url=str(row.get('url', '')),
                        job_board=JobBoard(str(row.get('job_board', 'linkedin'))),
                        description=str(row.get('description', '')),
                        salary_range=str(row.get('salary', '')),
                        job_type=str(row.get('job_type', '')),
                        experience_level=str(row.get('experience', '')),
                        skills_required=str(row.get('skills_required', '')).split(', ') if pd.notna(row.get('skills_required')) else [],
                        company_size=str(row.get('company_size', '')),
                        industry=str(row.get('industry', '')),
                        application_status=ApplicationStatus(str(row.get('application_status', 'not_applied'))),
                        applied_date=applied_date,
                        application_notes=str(row.get('application_notes', '')),
                        scraped_date=scraped_date,
                        job_id=str(row.get('job_id', ''))
                    )
                    jobs.append(job)
                    
                except Exception as e:
                    self.logger.error(f"Error parsing job row: {e}")
                    continue
            
            self.logger.info(f"Loaded {len(jobs)} jobs from {self.file_path}")
            return jobs
            
        except Exception as e:
            self.logger.error(f"Error loading jobs from Excel: {e}")
            return []
    
    def update_job_status(self, job_id: str, status: ApplicationStatus, 
                         applied_date: Optional[datetime] = None, 
                         notes: str = "") -> bool:
        """Update job application status in Excel file."""
        try:
            df = pd.read_excel(self.file_path, engine='openpyxl')
            
            # Find the job to update
            job_mask = df['job_id'].astype(str) == str(job_id)
            if not job_mask.any():
                self.logger.warning(f"Job {job_id} not found in Excel file")
                return False
            
            # Update the status
            df.loc[job_mask, 'application_status'] = status.value
            
            # Update applied date if provided
            if applied_date:
                df.loc[job_mask, 'time_applied'] = df.loc[job_mask, 'time_applied'].astype(str)
                df.loc[job_mask, 'time_applied'] = applied_date.isoformat()
            
            # Update notes if provided
            if notes:
                df.loc[job_mask, 'application_notes'] = df.loc[job_mask, 'application_notes'].astype(str)
                df.loc[job_mask, 'application_notes'] = notes
            
            # Save back to Excel
            df.to_excel(self.file_path, index=False, engine='openpyxl')
            self.logger.info(f"Updated job {job_id} status to {status.value}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating job status in Excel: {e}")
            return False
    
    def get_unapplied_jobs(self) -> List[JobPosting]:
        """Get jobs that haven't been applied to yet."""
        jobs = self.load_jobs()
        return [job for job in jobs if job.application_status == ApplicationStatus.NOT_APPLIED]
    
    def log_application(self, result: ApplicationResult) -> bool:
        """Log application attempt by updating the job status."""
        try:
            status = ApplicationStatus.APPLIED if result.success else ApplicationStatus.FAILED
            return self.update_job_status(
                result.job_posting.job_id,
                status,
                result.timestamp if result.success else None,
                result.message
            )
        except Exception as e:
            self.logger.error(f"Error logging application: {e}")
            return False


class GoogleSheetsStorage(StorageInterface):
    """Google Sheets storage implementation."""
    
    def __init__(self, credentials_path: str, spreadsheet_id: str, logger: Logger):
        self.credentials_path = credentials_path
        self.spreadsheet_id = spreadsheet_id
        self.logger = logger
        self.client = None
        self.spreadsheet = None
        
        if not GOOGLE_SHEETS_AVAILABLE:
            raise ImportError("Google Sheets dependencies not available. Install gspread and google-auth.")
        
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Google Sheets client."""
        try:
            if not os.path.exists(self.credentials_path):
                raise FileNotFoundError(f"Google credentials file not found: {self.credentials_path}")
            
            # Setup credentials
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            
            credentials = Credentials.from_service_account_file(
                self.credentials_path, scopes=scope
            )
            
            self.client = gspread.authorize(credentials)
            self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            
            self.logger.info("Google Sheets client initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Error initializing Google Sheets client: {e}")
            raise
    
    def _get_or_create_worksheet(self, name: str) -> gspread.Worksheet:
        """Get or create a worksheet by name."""
        try:
            return self.spreadsheet.worksheet(name)
        except gspread.WorksheetNotFound:
            # Create new worksheet
            worksheet = self.spreadsheet.add_worksheet(title=name, rows="1000", cols="20")
            
            # Add headers for jobs sheet
            if name == "Jobs":
                headers = [
                    "Job ID", "Title", "Company", "Location", "Posting Date", "URL",
                    "Job Board", "Description", "Salary Range", "Job Type", 
                    "Experience Level", "Skills Required", "Company Size", "Industry",
                    "Application Status", "Applied Date", "Application Notes", "Scraped Date"
                ]
                worksheet.append_row(headers)
            
            # Add headers for applications sheet
            elif name == "Applications":
                headers = [
                    "Timestamp", "Job Title", "Company", "Job URL", "Success", "Message"
                ]
                worksheet.append_row(headers)
            
            self.logger.info(f"Created new worksheet: {name}")
            return worksheet
    
    def save_jobs(self, jobs: List[JobPosting]) -> bool:
        """Save job postings to Google Sheets."""
        try:
            worksheet = self._get_or_create_worksheet("Jobs")
            
            # Get existing job IDs to avoid duplicates
            try:
                existing_data = worksheet.get_all_records()
                existing_job_ids = {str(row.get('Job ID', '')) for row in existing_data}
            except Exception:
                existing_job_ids = set()
            
            # Prepare new rows
            new_rows = []
            for job in jobs:
                if job.job_id not in existing_job_ids:
                    row = [
                        job.job_id,
                        job.title,
                        job.company,
                        job.location,
                        job.posting_date,
                        job.url,
                        job.job_board.value,
                        job.description,
                        job.salary_range,
                        job.job_type,
                        job.experience_level,
                        ', '.join(job.skills_required),
                        job.company_size,
                        job.industry,
                        job.application_status.value,
                        job.applied_date.isoformat() if job.applied_date else '',
                        job.application_notes,
                        job.scraped_date.isoformat()
                    ]
                    new_rows.append(row)
            
            # Batch append new rows
            if new_rows:
                worksheet.append_rows(new_rows)
                self.logger.info(f"Added {len(new_rows)} new jobs to Google Sheets")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving jobs to Google Sheets: {e}")
            return False
    
    def load_jobs(self) -> List[JobPosting]:
        """Load job postings from Google Sheets."""
        try:
            worksheet = self._get_or_create_worksheet("Jobs")
            records = worksheet.get_all_records()
            
            jobs = []
            for record in records:
                try:
                    # Convert record to JobPosting
                    job_data = {
                        'title': record.get('Title', ''),
                        'company': record.get('Company', ''),
                        'location': record.get('Location', ''),
                        'posting_date': record.get('Posting Date', ''),
                        'url': record.get('URL', ''),
                        'job_board': record.get('Job Board', 'linkedin'),
                        'description': record.get('Description', ''),
                        'salary_range': record.get('Salary Range', ''),
                        'job_type': record.get('Job Type', ''),
                        'experience_level': record.get('Experience Level', ''),
                        'skills_required': record.get('Skills Required', '').split(', ') if record.get('Skills Required') else [],
                        'company_size': record.get('Company Size', ''),
                        'industry': record.get('Industry', ''),
                        'application_status': record.get('Application Status', 'not_applied'),
                        'applied_date': record.get('Applied Date', ''),
                        'application_notes': record.get('Application Notes', ''),
                        'scraped_date': record.get('Scraped Date', ''),
                        'job_id': record.get('Job ID', '')
                    }
                    
                    job = JobPosting.from_dict(job_data)
                    jobs.append(job)
                    
                except Exception as e:
                    self.logger.error(f"Error parsing job record: {e}")
                    continue
            
            self.logger.info(f"Loaded {len(jobs)} jobs from Google Sheets")
            return jobs
            
        except Exception as e:
            self.logger.error(f"Error loading jobs from Google Sheets: {e}")
            return []
    
    def update_job_status(self, job_id: str, status: ApplicationStatus, 
                         applied_date: Optional[datetime] = None, 
                         notes: str = "") -> bool:
        """Update job application status in Google Sheets."""
        try:
            worksheet = self._get_or_create_worksheet("Jobs")
            
            # Find the row with the matching job ID
            job_id_col = worksheet.find(job_id)
            if not job_id_col:
                self.logger.warning(f"Job {job_id} not found in Google Sheets")
                return False
            
            row_num = job_id_col.row
            
            # Update status column (column O = 15)
            worksheet.update_cell(row_num, 15, status.value)
            
            # Update applied date if provided (column P = 16)
            if applied_date:
                worksheet.update_cell(row_num, 16, applied_date.isoformat())
            
            # Update notes if provided (column Q = 17)
            if notes:
                worksheet.update_cell(row_num, 17, notes)
            
            self.logger.info(f"Updated job {job_id} status to {status.value} in Google Sheets")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating job status in Google Sheets: {e}")
            return False
    
    def get_unapplied_jobs(self) -> List[JobPosting]:
        """Get jobs that haven't been applied to yet."""
        jobs = self.load_jobs()
        return [job for job in jobs if job.application_status == ApplicationStatus.NOT_APPLIED]
    
    def log_application(self, result: ApplicationResult) -> bool:
        """Log application attempt to Google Sheets."""
        try:
            worksheet = self._get_or_create_worksheet("Applications")
            
            row = [
                result.timestamp.isoformat(),
                result.job_posting.title,
                result.job_posting.company,
                result.job_posting.url,
                "SUCCESS" if result.success else "FAILED",
                result.message
            ]
            
            worksheet.append_row(row)
            self.logger.info(f"Logged application for {result.job_posting.title}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error logging application to Google Sheets: {e}")
            return False


class StorageManager:
    """Manages data storage with fallback options."""
    
    def __init__(self, use_google_sheets: bool = True, 
                 google_sheets_id: Optional[str] = None,
                 credentials_path: str = "credentials/google_credentials.json",
                 local_storage_path: str = "data/job_postings.json",
                 logger: Optional[Logger] = None,
                 excel_file_path: str = "documents/Job update.xlsx"):
        
        self.logger = logger or Logger()
        self.primary_storage = None
        self.fallback_storage = LocalJSONStorage(local_storage_path, self.logger)
        
        # Use PandasExcelStorage as primary storage (replaces Google Sheets)
        try:
            self.primary_storage = PandasExcelStorage(excel_file_path, self.logger)
            self.logger.info("Using Excel file as primary storage")
        except Exception as e:
            self.logger.warning(f"Failed to setup Excel storage: {e}")
            self.logger.info("Falling back to local JSON storage")
        
        # Use local storage as primary if Excel storage is not available
        if not self.primary_storage:
            self.primary_storage = self.fallback_storage
            self.logger.info("Using local JSON storage")
    
    def save_jobs(self, jobs: List[JobPosting]) -> bool:
        """Save jobs using primary storage with fallback."""
        success = self.primary_storage.save_jobs(jobs)
        
        # If primary storage is Excel and it fails, try fallback
        if not success and isinstance(self.primary_storage, PandasExcelStorage):
            self.logger.warning("Primary storage failed, trying fallback")
            success = self.fallback_storage.save_jobs(jobs)
        
        return success
    
    def load_jobs(self) -> List[JobPosting]:
        """Load jobs from primary storage with fallback."""
        jobs = self.primary_storage.load_jobs()
        
        # If primary storage is Excel and returns no jobs, try fallback
        if not jobs and isinstance(self.primary_storage, PandasExcelStorage):
            jobs = self.fallback_storage.load_jobs()
        
        return jobs
    
    def update_job_status(self, job_id: str, status: ApplicationStatus, 
                         applied_date: Optional[datetime] = None, 
                         notes: str = "") -> bool:
        """Update job status in both storages."""
        primary_success = self.primary_storage.update_job_status(
            job_id, status, applied_date, notes
        )
        
        # Also update fallback if different from primary
        fallback_success = True
        if isinstance(self.primary_storage, PandasExcelStorage):
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
        
        # Also log in fallback if different from primary
        fallback_success = True
        if isinstance(self.primary_storage, PandasExcelStorage):
            fallback_success = self.fallback_storage.log_application(result)
        
        return primary_success or fallback_success
    
    def export_to_csv(self, output_path: str) -> bool:
        """Export jobs data to CSV file."""
        try:
            jobs = self.load_jobs()
            if not jobs:
                self.logger.warning("No jobs to export")
                return False
            
            # Convert to pandas DataFrame
            jobs_data = [job.to_dict() for job in jobs]
            df = pd.DataFrame(jobs_data)
            
            # Save to CSV
            df.to_csv(output_path, index=False)
            self.logger.info(f"Exported {len(jobs)} jobs to {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error exporting to CSV: {e}")
            return False
