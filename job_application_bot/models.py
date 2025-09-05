"""Data models for job postings and applications."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
import json

class JobBoard(Enum):
    """Supported job boards."""
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    GLASSDOOR = "glassdoor"

class ApplicationStatus(Enum):
    """Application status tracking."""
    NOT_APPLIED = "not_applied"
    APPLIED = "applied"
    FAILED = "failed"
    SKIPPED = "skipped"
    DUPLICATE = "duplicate"

@dataclass
class JobPosting:
    """Represents a job posting from any job board."""
    title: str
    company: str
    location: str
    posting_date: str
    url: str
    job_board: JobBoard
    
    # Optional detailed information
    description: str = ""
    salary_range: str = ""
    job_type: str = ""
    experience_level: str = ""
    skills_required: List[str] = field(default_factory=list)
    company_size: str = ""
    industry: str = ""
    
    # Application tracking
    application_status: ApplicationStatus = ApplicationStatus.NOT_APPLIED
    applied_date: Optional[datetime] = None
    application_notes: str = ""
    
    # Metadata
    scraped_date: datetime = field(default_factory=datetime.now)
    job_id: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "posting_date": self.posting_date,
            "url": self.url,
            "job_board": self.job_board.value,
            "description": self.description,
            "salary_range": self.salary_range,
            "job_type": self.job_type,
            "experience_level": self.experience_level,
            "skills_required": self.skills_required,
            "company_size": self.company_size,
            "industry": self.industry,
            "application_status": self.application_status.value,
            "applied_date": self.applied_date.isoformat() if self.applied_date else None,
            "application_notes": self.application_notes,
            "scraped_date": self.scraped_date.isoformat(),
            "job_id": self.job_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JobPosting':
        """Create JobPosting from dictionary."""
        # Handle datetime fields
        scraped_date = datetime.fromisoformat(data.get("scraped_date", datetime.now().isoformat()))
        applied_date = None
        if data.get("applied_date"):
            applied_date = datetime.fromisoformat(data["applied_date"])
        
        return cls(
            title=data["title"],
            company=data["company"],
            location=data["location"],
            posting_date=data["posting_date"],
            url=data["url"],
            job_board=JobBoard(data["job_board"]),
            description=data.get("description", ""),
            salary_range=data.get("salary_range", ""),
            job_type=data.get("job_type", ""),
            experience_level=data.get("experience_level", ""),
            skills_required=data.get("skills_required", []),
            company_size=data.get("company_size", ""),
            industry=data.get("industry", ""),
            application_status=ApplicationStatus(data.get("application_status", "not_applied")),
            applied_date=applied_date,
            application_notes=data.get("application_notes", ""),
            scraped_date=scraped_date,
            job_id=data.get("job_id", "")
        )
    
    def __hash__(self):
        """Make JobPosting hashable for deduplication."""
        return hash((self.title, self.company, self.location, self.url))
    
    def __eq__(self, other):
        """Check equality for deduplication."""
        if not isinstance(other, JobPosting):
            return False
        return (self.title == other.title and 
                self.company == other.company and 
                self.location == other.location and 
                self.url == other.url)

@dataclass
class ApplicationResult:
    """Result of an application attempt."""
    job_posting: JobPosting
    success: bool
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "job_title": self.job_posting.title,
            "company": self.job_posting.company,
            "job_url": self.job_posting.url,
            "success": self.success,
            "message": self.message,
            "timestamp": self.timestamp.isoformat()
        }

@dataclass
class SearchResult:
    """Result of a job search operation."""
    job_board: JobBoard
    query: str
    location: str
    jobs_found: List[JobPosting]
    search_time: datetime = field(default_factory=datetime.now)
    total_results: int = 0
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "job_board": self.job_board.value,
            "query": self.query,
            "location": self.location,
            "jobs_found_count": len(self.jobs_found),
            "total_results": self.total_results,
            "search_time": self.search_time.isoformat(),
            "errors": self.errors
        }
