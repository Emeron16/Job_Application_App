"""Utility classes for rate limiting, logging, and other common functionality."""

import time
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Optional
from pathlib import Path
import json
from tenacity import retry, stop_after_attempt, wait_exponential


class RateLimiter:
    """Rate limiter to prevent overwhelming job boards with requests."""
    
    def __init__(self, requests_per_minute: int = 30, requests_per_hour: int = 100):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.minute_requests = []
        self.hour_requests = []
        self.last_request_time = None
        self.min_delay = 60 / requests_per_minute  # Minimum delay between requests
    
    def wait_if_needed(self):
        """Wait if necessary to respect rate limits."""
        current_time = datetime.now()
        
        # Clean old requests
        self._clean_old_requests(current_time)
        
        # Check if we've hit minute limit
        if len(self.minute_requests) >= self.requests_per_minute:
            sleep_time = 60 - (current_time - self.minute_requests[0]).total_seconds()
            if sleep_time > 0:
                time.sleep(sleep_time)
                self._clean_old_requests(datetime.now())
        
        # Check if we've hit hour limit
        if len(self.hour_requests) >= self.requests_per_hour:
            sleep_time = 3600 - (current_time - self.hour_requests[0]).total_seconds()
            if sleep_time > 0:
                time.sleep(sleep_time)
                self._clean_old_requests(datetime.now())
        
        # Ensure minimum delay between requests
        if self.last_request_time:
            elapsed = (current_time - self.last_request_time).total_seconds()
            if elapsed < self.min_delay:
                time.sleep(self.min_delay - elapsed)
        
        # Record this request
        now = datetime.now()
        self.minute_requests.append(now)
        self.hour_requests.append(now)
        self.last_request_time = now
    
    def _clean_old_requests(self, current_time: datetime):
        """Remove requests older than the time windows."""
        # Remove requests older than 1 minute
        minute_cutoff = current_time - timedelta(minutes=1)
        self.minute_requests = [req for req in self.minute_requests if req > minute_cutoff]
        
        # Remove requests older than 1 hour
        hour_cutoff = current_time - timedelta(hours=1)
        self.hour_requests = [req for req in self.hour_requests if req > hour_cutoff]


class Logger:
    """Custom logger for the job application system."""
    
    def __init__(self, log_file: str = "logs/application_log.txt", level: str = "INFO"):
        # Create logs directory if it doesn't exist
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        
        # Setup logging
        self.logger = logging.getLogger("JobApplicationBot")
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # File handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Add handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def debug(self, message: str):
        self.logger.debug(message)
    
    def info(self, message: str):
        self.logger.info(message)
    
    def warning(self, message: str):
        self.logger.warning(message)
    
    def error(self, message: str):
        self.logger.error(message)
    
    def critical(self, message: str):
        self.logger.critical(message)
    
    def log_application(self, job_title: str, company: str, success: bool, message: str):
        """Log application attempt."""
        status = "SUCCESS" if success else "FAILED"
        log_message = f"APPLICATION {status}: {job_title} at {company} - {message}"
        
        if success:
            self.info(log_message)
        else:
            self.error(log_message)


class RetryHandler:
    """Handle retries with exponential backoff."""
    
    @staticmethod
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    def retry_request(func, *args, **kwargs):
        """Retry a function with exponential backoff."""
        return func(*args, **kwargs)


class FileManager:
    """Manage file operations for documents and data."""
    
    @staticmethod
    def read_file(file_path: str) -> Optional[str]:
        """Read file contents safely."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return None
        except Exception as e:
            logging.error(f"Error reading file {file_path}: {e}")
            return None
    
    @staticmethod
    def write_file(file_path: str, content: str, create_dirs: bool = True):
        """Write content to file safely."""
        try:
            if create_dirs:
                Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            logging.error(f"Error writing file {file_path}: {e}")
            raise
    
    @staticmethod
    def read_json(file_path: str) -> Optional[Dict]:
        """Read JSON file safely."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return None
        except Exception as e:
            logging.error(f"Error reading JSON file {file_path}: {e}")
            return None
    
    @staticmethod
    def write_json(file_path: str, data: Dict, create_dirs: bool = True):
        """Write data to JSON file safely."""
        try:
            if create_dirs:
                Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logging.error(f"Error writing JSON file {file_path}: {e}")
            raise


class TextProcessor:
    """Process and clean text data."""
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Clean and normalize text."""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Remove non-printable characters
        text = ''.join(char for char in text if char.isprintable() or char.isspace())
        
        return text.strip()
    
    @staticmethod
    def extract_keywords(text: str, min_length: int = 3) -> list:
        """Extract keywords from text."""
        import re
        
        # Simple keyword extraction
        words = re.findall(r'\b[a-zA-Z]{' + str(min_length) + ',}\b', text.lower())
        
        # Remove common stop words
        stop_words = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 
                     'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 
                     'how', 'its', 'may', 'new', 'now', 'old', 'see', 'two', 'who', 'boy', 
                     'did', 'man', 'way', 'use', 'own', 'say', 'she', 'too', 'any', 'end', 
                     'why', 'let', 'try', 'ask', 'men', 'run', 'set', 'put', 'big', 'top'}
        
        return [word for word in words if word not in stop_words]


class URLValidator:
    """Validate and normalize URLs."""
    
    @staticmethod
    def is_valid_url(url: str) -> bool:
        """Check if URL is valid."""
        import re
        
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        
        return url_pattern.match(url) is not None
    
    @staticmethod
    def normalize_url(url: str) -> str:
        """Normalize URL for comparison."""
        # Remove query parameters and fragments for deduplication
        from urllib.parse import urlparse
        
        parsed = urlparse(url)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        return normalized.rstrip('/')


class ConfigValidator:
    """Validate configuration settings."""
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format."""
        import re
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def validate_file_path(file_path: str) -> bool:
        """Check if file path exists and is readable."""
        return os.path.exists(file_path) and os.access(file_path, os.R_OK)
    
    @staticmethod
    def validate_positive_int(value: int, min_value: int = 1) -> bool:
        """Validate positive integer."""
        return isinstance(value, int) and value >= min_value
