"""Configuration management for the job application automation system."""

import os
from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@dataclass
class JobSearchConfig:
    """Configuration for job search parameters."""
    keywords: List[str] = field(default_factory=lambda: ["software engineer", "python developer"])
    locations: List[str] = field(default_factory=lambda: ["Remote", "San Francisco", "New York"])
    experience_levels: List[str] = field(default_factory=lambda: ["entry", "mid", "senior"])
    job_types: List[str] = field(default_factory=lambda: ["full-time", "contract"])
    exclude_keywords: List[str] = field(default_factory=list)
    salary_min: Optional[int] = None
    date_posted: str = "week"  # today, week, month

@dataclass
class ApplicationConfig:
    """Configuration for application automation."""
    resume_path: str = "documents/resume.pdf"
    cover_letter_path: str = "documents/cover_letter.txt"
    daily_application_limit: int = 10
    auto_apply_enabled: bool = False
    apply_to_external_sites: bool = False

@dataclass
class RateLimitConfig:
    """Configuration for rate limiting and request handling."""
    requests_per_minute: int = 30
    requests_per_hour: int = 100
    retry_attempts: int = 3
    retry_delay_base: float = 1.0
    request_timeout: int = 30
    cooldown_period: int = 300  # 5 minutes

@dataclass
class StorageConfig:
    """Configuration for data storage."""
    use_google_sheets: bool = True
    google_sheets_id: Optional[str] = None
    local_storage_path: str = "data/job_postings.json"
    log_file_path: str = "logs/application_log.txt"

@dataclass
class Config:
    """Main configuration class."""
    job_search: JobSearchConfig = field(default_factory=JobSearchConfig)
    application: ApplicationConfig = field(default_factory=ApplicationConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    
    # Environment variables
    linkedin_email: str = field(default_factory=lambda: os.getenv("LINKEDIN_EMAIL", ""))
    linkedin_password: str = field(default_factory=lambda: os.getenv("LINKEDIN_PASSWORD", ""))
    # Indeed now uses Google OAuth login - no email/password needed
    google_credentials_path: str = field(default_factory=lambda: os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials/google_credentials.json"))
    
    @classmethod
    def load_from_file(cls, config_path: str = "config.json") -> 'Config':
        """Load configuration from JSON file."""
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config_data = json.load(f)
            return cls(**config_data)
        return cls()
    
    def save_to_file(self, config_path: str = "config.json"):
        """Save configuration to JSON file."""
        config_dict = {
            "job_search": self.job_search.__dict__,
            "application": self.application.__dict__,
            "rate_limit": self.rate_limit.__dict__,
            "storage": self.storage.__dict__
        }
        
        Path(config_path).parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(config_dict, f, indent=2)
    
    def validate(self) -> List[str]:
        """Validate configuration and return list of errors."""
        errors = []
        
        if not self.job_search.keywords:
            errors.append("At least one keyword must be specified")
        
        if not self.job_search.locations:
            errors.append("At least one location must be specified")
        
        if self.application.auto_apply_enabled:
            if not os.path.exists(self.application.resume_path):
                errors.append(f"Resume file not found: {self.application.resume_path}")
            
            if not os.path.exists(self.application.cover_letter_path):
                errors.append(f"Cover letter file not found: {self.application.cover_letter_path}")
        
        # Google credentials only needed if explicitly using Google Sheets (legacy mode)
        if self.storage.use_google_sheets and self.storage.google_sheets_id:
            if not os.path.exists(self.google_credentials_path):
                errors.append(f"Google credentials file not found: {self.google_credentials_path}")
        
        return errors

# Global configuration instance
config = Config()
