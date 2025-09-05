"""Job search implementations for different job boards."""

import time
import re
import hashlib
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from urllib.parse import urlencode, quote_plus
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from fake_useragent import UserAgent

from models import JobPosting, JobBoard, SearchResult
from utils import RateLimiter, Logger

class JobSearcher(ABC):
    """Abstract base class for job board searchers."""
    
    def __init__(self, rate_limiter: RateLimiter, logger: Logger):
        self.rate_limiter = rate_limiter
        self.logger = logger
        self.session = requests.Session()
        self.ua = UserAgent()
        self.session.headers.update({'User-Agent': self.ua.random})
    
    @abstractmethod
    def search_jobs(self, keywords: str, location: str, **filters) -> SearchResult:
        """Search for jobs on the specific job board."""
        pass
    
    def _generate_job_id(self, title: str, company: str, url: str) -> str:
        """Generate a unique job ID for deduplication."""
        content = f"{title}|{company}|{url}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

class LinkedInSearcher(JobSearcher):
    """LinkedIn job searcher using web scraping."""
    
    def __init__(self, rate_limiter: RateLimiter, logger: Logger):
        super().__init__(rate_limiter, logger)
        self.base_url = "https://www.linkedin.com/jobs/search"
        self.driver = None
        self._setup_driver()
    
    def _setup_driver(self):
        """Setup Chrome driver for LinkedIn scraping."""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument(f"--user-agent={self.ua.random}")
            
            self.driver = webdriver.Chrome(
                service=webdriver.chrome.service.Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            self.logger.info("LinkedIn Chrome driver initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to setup Chrome driver for LinkedIn: {e}")
    
    def search_jobs(self, keywords: str, location: str, **filters) -> SearchResult:
        """Search for jobs on LinkedIn."""
        search_result = SearchResult(
            job_board=JobBoard.LINKEDIN,
            query=keywords,
            location=location,
            jobs_found=[]
        )
        
        if not self.driver:
            search_result.errors.append("Chrome driver not available")
            return search_result
        
        try:
            self.rate_limiter.wait_if_needed()
            
            # Build search URL
            params = {
                'keywords': keywords,
                'location': location,
                'f_TPR': 'r86400',  # Past 24 hours
                'f_JT': 'F',  # Full time
                'start': '0'
            }
            
            search_url = f"{self.base_url}?{urlencode(params)}"
            self.logger.info(f"Searching LinkedIn: {search_url}")
            
            self.driver.get(search_url)
            time.sleep(3)  # Wait for page load
            
            # Wait for job cards to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".job-search-card"))
            )
            
            # Extract job postings
            job_cards = self.driver.find_elements(By.CSS_SELECTOR, ".job-search-card")
            
            for card in job_cards[:20]:  # Limit to first 20 results
                try:
                    job = self._extract_linkedin_job(card)
                    if job:
                        search_result.jobs_found.append(job)
                except Exception as e:
                    self.logger.error(f"Error extracting LinkedIn job: {e}")
                    continue
            
            search_result.total_results = len(search_result.jobs_found)
            self.logger.info(f"Found {search_result.total_results} jobs on LinkedIn")
            
        except TimeoutException:
            search_result.errors.append("LinkedIn page load timeout")
            self.logger.error("LinkedIn page load timeout")
        except Exception as e:
            search_result.errors.append(f"LinkedIn search error: {str(e)}")
            self.logger.error(f"LinkedIn search error: {e}")
        
        return search_result
    
    def _extract_linkedin_job(self, card) -> Optional[JobPosting]:
        """Extract job details from LinkedIn job card."""
        try:
            # Title and URL
            title_element = card.find_element(By.CSS_SELECTOR, ".base-search-card__title a")
            title = title_element.text.strip()
            url = title_element.get_attribute("href")
            
            # Company
            company_element = card.find_element(By.CSS_SELECTOR, ".base-search-card__subtitle a")
            company = company_element.text.strip()
            
            # Location
            location_element = card.find_element(By.CSS_SELECTOR, ".job-search-card__location")
            location = location_element.text.strip()
            
            # Date posted
            date_element = card.find_element(By.CSS_SELECTOR, ".job-search-card__listdate")
            posting_date = date_element.get_attribute("datetime") or date_element.text.strip()
            
            job_id = self._generate_job_id(title, company, url)
            
            return JobPosting(
                title=title,
                company=company,
                location=location,
                posting_date=posting_date,
                url=url,
                job_board=JobBoard.LINKEDIN,
                job_id=job_id
            )
            
        except NoSuchElementException as e:
            self.logger.error(f"Missing element in LinkedIn job card: {e}")
            return None
    
    def __del__(self):
        """Cleanup driver on destruction."""
        if self.driver:
            self.driver.quit()

class IndeedSearcher(JobSearcher):
    """Indeed job searcher using web scraping."""
    
    def __init__(self, rate_limiter: RateLimiter, logger: Logger):
        super().__init__(rate_limiter, logger)
        self.base_url = "https://www.indeed.com/jobs"
    
    def search_jobs(self, keywords: str, location: str, **filters) -> SearchResult:
        """Search for jobs on Indeed."""
        search_result = SearchResult(
            job_board=JobBoard.INDEED,
            query=keywords,
            location=location,
            jobs_found=[]
        )
        
        try:
            self.rate_limiter.wait_if_needed()
            
            # Build search parameters
            params = {
                'q': keywords,
                'l': location,
                'fromage': '1',  # Last 1 day
                'sort': 'date',
                'start': '0'
            }
            
            search_url = f"{self.base_url}?{urlencode(params)}"
            self.logger.info(f"Searching Indeed: {search_url}")
            
            # Make request
            response = self.session.get(search_url, timeout=30)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find job cards
            job_cards = soup.find_all('div', class_='job_seen_beacon')
            
            for card in job_cards[:20]:  # Limit to first 20 results
                try:
                    job = self._extract_indeed_job(card)
                    if job:
                        search_result.jobs_found.append(job)
                except Exception as e:
                    self.logger.error(f"Error extracting Indeed job: {e}")
                    continue
            
            search_result.total_results = len(search_result.jobs_found)
            self.logger.info(f"Found {search_result.total_results} jobs on Indeed")
            
        except requests.RequestException as e:
            search_result.errors.append(f"Indeed request error: {str(e)}")
            self.logger.error(f"Indeed request error: {e}")
        except Exception as e:
            search_result.errors.append(f"Indeed search error: {str(e)}")
            self.logger.error(f"Indeed search error: {e}")
        
        return search_result
    
    def _extract_indeed_job(self, card) -> Optional[JobPosting]:
        """Extract job details from Indeed job card."""
        try:
            # Title and URL
            title_link = card.find('h2', class_='jobTitle').find('a')
            title = title_link.get('title') or title_link.text.strip()
            
            # Build full URL
            href = title_link.get('href')
            url = f"https://www.indeed.com{href}" if href.startswith('/') else href
            
            # Company
            company_element = card.find('span', class_='companyName')
            if company_element:
                company_link = company_element.find('a')
                company = company_link.text.strip() if company_link else company_element.text.strip()
            else:
                company = "Unknown"
            
            # Location
            location_element = card.find('div', class_='companyLocation')
            location = location_element.text.strip() if location_element else "Unknown"
            
            # Date posted
            date_element = card.find('span', class_='date')
            posting_date = date_element.text.strip() if date_element else "Unknown"
            
            # Salary (if available)
            salary_element = card.find('span', class_='salary-snippet')
            salary_range = salary_element.text.strip() if salary_element else ""
            
            job_id = self._generate_job_id(title, company, url)
            
            return JobPosting(
                title=title,
                company=company,
                location=location,
                posting_date=posting_date,
                url=url,
                job_board=JobBoard.INDEED,
                salary_range=salary_range,
                job_id=job_id
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing Indeed job card: {e}")
            return None

class GlassdoorSearcher(JobSearcher):
    """Glassdoor job searcher using web scraping."""
    
    def __init__(self, rate_limiter: RateLimiter, logger: Logger):
        super().__init__(rate_limiter, logger)
        self.base_url = "https://www.glassdoor.com/Job/jobs.htm"
    
    def search_jobs(self, keywords: str, location: str, **filters) -> SearchResult:
        """Search for jobs on Glassdoor."""
        search_result = SearchResult(
            job_board=JobBoard.GLASSDOOR,
            query=keywords,
            location=location,
            jobs_found=[]
        )
        
        try:
            self.rate_limiter.wait_if_needed()
            
            # Build search parameters
            params = {
                'sc.keyword': keywords,
                'locT': 'C',
                'locId': location,
                'jobType': 'fulltime',
                'fromAge': '1',  # Last 1 day
                'minSalary': '0',
                'includeNoSalaryJobs': 'true',
                'radius': '25'
            }
            
            search_url = f"{self.base_url}?{urlencode(params)}"
            self.logger.info(f"Searching Glassdoor: {search_url}")
            
            # Add specific headers for Glassdoor
            headers = {
                'User-Agent': self.ua.random,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            }
            
            response = self.session.get(search_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Note: Glassdoor has anti-bot measures, so this is a placeholder implementation
            # In practice, you might need to use Selenium or handle CAPTCHA
            self.logger.warning("Glassdoor scraping is limited due to anti-bot measures")
            
            # Add placeholder job for demonstration
            placeholder_job = JobPosting(
                title=f"Placeholder: {keywords}",
                company="Glassdoor Placeholder",
                location=location,
                posting_date="Today",
                url="https://www.glassdoor.com",
                job_board=JobBoard.GLASSDOOR,
                job_id=self._generate_job_id("placeholder", "glassdoor", "placeholder")
            )
            search_result.jobs_found.append(placeholder_job)
            search_result.total_results = 1
            
        except requests.RequestException as e:
            search_result.errors.append(f"Glassdoor request error: {str(e)}")
            self.logger.error(f"Glassdoor request error: {e}")
        except Exception as e:
            search_result.errors.append(f"Glassdoor search error: {str(e)}")
            self.logger.error(f"Glassdoor search error: {e}")
        
        return search_result

class JobSearchManager:
    """Manages job searches across multiple job boards."""
    
    def __init__(self, rate_limiter: RateLimiter, logger: Logger):
        self.rate_limiter = rate_limiter
        self.logger = logger
        self.searchers = {
            JobBoard.LINKEDIN: LinkedInSearcher(rate_limiter, logger),
            JobBoard.INDEED: IndeedSearcher(rate_limiter, logger),
            JobBoard.GLASSDOOR: GlassdoorSearcher(rate_limiter, logger)
        }
    
    def search_all_boards(self, keywords: List[str], locations: List[str], 
                         job_boards: Optional[List[JobBoard]] = None) -> List[SearchResult]:
        """Search for jobs across multiple boards and keywords/locations."""
        if job_boards is None:
            job_boards = list(self.searchers.keys())
        
        all_results = []
        
        for keyword in keywords:
            for location in locations:
                for board in job_boards:
                    if board in self.searchers:
                        try:
                            self.logger.info(f"Searching {board.value} for '{keyword}' in '{location}'")
                            result = self.searchers[board].search_jobs(keyword, location)
                            all_results.append(result)
                            
                            # Add delay between searches
                            time.sleep(2)
                            
                        except Exception as e:
                            self.logger.error(f"Error searching {board.value}: {e}")
                            error_result = SearchResult(
                                job_board=board,
                                query=keyword,
                                location=location,
                                jobs_found=[],
                                errors=[f"Search failed: {str(e)}"]
                            )
                            all_results.append(error_result)
        
        return all_results
    
    def deduplicate_jobs(self, jobs: List[JobPosting]) -> List[JobPosting]:
        """Remove duplicate job postings."""
        seen = set()
        unique_jobs = []
        
        for job in jobs:
            # Create a hash based on title, company, and normalized URL
            job_hash = hash((job.title.lower(), job.company.lower(), job.url.split('?')[0]))
            
            if job_hash not in seen:
                seen.add(job_hash)
                unique_jobs.append(job)
            else:
                self.logger.debug(f"Duplicate job found: {job.title} at {job.company}")
        
        self.logger.info(f"Removed {len(jobs) - len(unique_jobs)} duplicate jobs")
        return unique_jobs
