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
    
    def search_jobs(self, keywords: str, location: str, job_limit: int = 20, **filters) -> SearchResult:
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
            
            for card in job_cards[:job_limit]:  # Limit to specified number of results
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
        
        # No demo jobs - let real scraping work or fail gracefully
        if not search_result.jobs_found:
            self.logger.warning(f"No jobs found for LinkedIn search: {keywords} in {location}")
        
        return search_result
    
    def _extract_linkedin_job(self, card) -> Optional[JobPosting]:
        """Extract job details from LinkedIn job card."""
        try:
            # Try multiple selectors for title and URL
            title_selectors = [
                ".base-search-card__title a",
                ".job-search-card__title a", 
                "[data-entity-urn] h3 a",
                ".base-card__full-link",
                "h3 a"
            ]
            
            title_element = None
            for selector in title_selectors:
                try:
                    title_element = card.find_element(By.CSS_SELECTOR, selector)
                    break
                except NoSuchElementException:
                    continue
                    
            if not title_element:
                self.logger.warning("Could not find title element in LinkedIn job card")
                return None
                
            title = title_element.text.strip()
            url = title_element.get_attribute("href") or "https://linkedin.com/jobs"
            
            # Try multiple selectors for company
            company_selectors = [
                ".base-search-card__subtitle a",
                ".job-search-card__subtitle-link",
                ".base-search-card__subtitle",
                "[data-entity-urn] h4 a",
                "h4 a"
            ]
            
            company = "Unknown Company"
            for selector in company_selectors:
                try:
                    company_element = card.find_element(By.CSS_SELECTOR, selector)
                    company = company_element.text.strip()
                    break
                except NoSuchElementException:
                    continue
            
            # Try multiple selectors for location
            location_selectors = [
                ".job-search-card__location",
                ".base-search-card__metadata span",
                "[data-entity-urn] span",
                ".job-result-card__location"
            ]
            
            location = "Remote"
            for selector in location_selectors:
                try:
                    location_element = card.find_element(By.CSS_SELECTOR, selector)
                    location = location_element.text.strip()
                    break
                except NoSuchElementException:
                    continue
            
            # Try to get posting date
            posting_date = "Today"
            date_selectors = [
                ".job-search-card__listdate",
                ".job-result-card__listdate",
                "time"
            ]
            
            for selector in date_selectors:
                try:
                    date_element = card.find_element(By.CSS_SELECTOR, selector)
                    posting_date = date_element.get_attribute("datetime") or date_element.text.strip()
                    break
                except NoSuchElementException:
                    continue
            
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
            
        except Exception as e:
            self.logger.error(f"Error extracting LinkedIn job: {e}")
            return None
    
    def _create_demo_linkedin_jobs(self, keywords: str, location: str) -> List[JobPosting]:
        """Create demo jobs for testing when LinkedIn scraping fails."""
        demo_jobs = []
        companies = ["TechCorp", "InnovateLabs", "DataSystems", "CloudWorks", "DevCompany"]
        titles = [
            f"Senior {keywords}",
            f"{keywords} Developer",
            f"Lead {keywords}",
            f"{keywords} Engineer",
            f"Principal {keywords}"
        ]
        
        for i in range(min(5, len(companies))):
            job = JobPosting(
                title=titles[i % len(titles)],
                company=companies[i],
                location=location,
                posting_date="2 days ago",
                url=f"https://linkedin.com/jobs/demo-{i+1}",
                job_board=JobBoard.LINKEDIN,
                job_id=self._generate_job_id(titles[i % len(titles)], companies[i], f"demo-{i+1}"),
                description=f"Exciting opportunity for a {keywords} at {companies[i]} in {location}. Join our innovative team!",
                salary_range="$80,000 - $120,000",
                experience_level="Mid-Senior level"
            )
            demo_jobs.append(job)
        
        return demo_jobs
    
    def __del__(self):
        """Cleanup driver on destruction."""
        if self.driver:
            self.driver.quit()

class IndeedSearcher(JobSearcher):
    """Indeed job searcher using web scraping."""
    
    def __init__(self, rate_limiter: RateLimiter, logger: Logger):
        super().__init__(rate_limiter, logger)
        self.base_url = "https://www.indeed.com/jobs"
    
    def search_jobs(self, keywords: str, location: str, job_limit: int = 20, **filters) -> SearchResult:
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
            
            # Enhanced headers to avoid 403 errors with session management
            headers = {
                'User-Agent': self.ua.random,  # Use random user agent
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache',
                'Sec-Ch-Ua': '"Chromium";v="118", "Google Chrome";v="118", "Not=A?Brand";v="99"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"macOS"',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1',
            }
            
            # Make request with enhanced headers
            response = self.session.get(search_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find job cards - try multiple selectors
            job_cards = soup.find_all('div', class_='job_seen_beacon')
            if not job_cards:
                job_cards = soup.find_all('div', class_='slider_container')
            if not job_cards:
                job_cards = soup.find_all('div', attrs={'data-jk': True})
            
            for card in job_cards[:job_limit]:  # Limit to specified number of results
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
        
        # If scraping completely failed, create a minimal real job entry pointing to Indeed search
        if not search_result.jobs_found and any("403" in str(error) for error in search_result.errors):
            # Create one job that points to the actual Indeed search results
            indeed_search_url = f"https://www.indeed.com/jobs?q={keywords.replace(' ', '+')}&l={location.replace(' ', '+')}"
            fallback_job = JobPosting(
                title=f"{keywords} - View on Indeed",
                company="Multiple Companies",
                location=location,
                posting_date="Today", 
                url=indeed_search_url,
                job_board=JobBoard.INDEED,
                job_id=self._generate_job_id(f"{keywords}-indeed-search", "indeed", indeed_search_url),
                description=f"Click 'View on Platform' to see {keywords} jobs on Indeed for {location}",
                salary_range="Varies",
                job_type="Multiple"
            )
            search_result.jobs_found.append(fallback_job)
            search_result.total_results = 1
            self.logger.info(f"Created Indeed search redirect for: {keywords} in {location}")
        elif not search_result.jobs_found:
            self.logger.warning(f"No jobs found for Indeed search: {keywords} in {location}")
        
        return search_result
    
    def _extract_indeed_job(self, card) -> Optional[JobPosting]:
        """Extract job details from Indeed job card."""
        try:
            # Try multiple selectors for title and URL
            title_link = None
            title_selectors = [
                'h2.jobTitle a',
                'h2[data-testid="job-title"] a',
                'a[data-jk]',
                '.jobTitle a',
                'h2 a'
            ]
            
            for selector in title_selectors:
                title_link = card.select_one(selector)
                if title_link:
                    break
                    
            if not title_link:
                self.logger.warning("Could not find title link in Indeed job card")
                return None
                
            title = title_link.get('title') or title_link.text.strip()
            
            # Build full URL
            href = title_link.get('href')
            url = f"https://www.indeed.com{href}" if href and href.startswith('/') else (href or "https://www.indeed.com")
            
            # Try multiple selectors for company
            company = "Unknown Company"
            company_selectors = [
                'span.companyName a',
                'span.companyName',
                '[data-testid="company-name"]',
                '.companyName'
            ]
            
            for selector in company_selectors:
                company_element = card.select_one(selector)
                if company_element:
                    company = company_element.text.strip()
                    break
            
            # Try multiple selectors for location
            location = "Remote"
            location_selectors = [
                'div.companyLocation',
                '[data-testid="job-location"]',
                '.companyLocation',
                '.locationsContainer'
            ]
            
            for selector in location_selectors:
                location_element = card.select_one(selector)
                if location_element:
                    location = location_element.text.strip()
                    break
            
            # Try multiple selectors for date
            posting_date = "Today"
            date_selectors = [
                'span.date',
                '[data-testid="myJobsStateDate"]',
                '.date'
            ]
            
            for selector in date_selectors:
                date_element = card.select_one(selector)
                if date_element:
                    posting_date = date_element.text.strip()
                    break
            
            # Try to get salary
            salary_range = ""
            salary_selectors = [
                'span.salary-snippet',
                '.salary-snippet-container',
                '[data-testid="job-salary"]'
            ]
            
            for selector in salary_selectors:
                salary_element = card.select_one(selector)
                if salary_element:
                    salary_range = salary_element.text.strip()
                    break
            
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
    
    def _create_demo_indeed_jobs(self, keywords: str, location: str) -> List[JobPosting]:
        """Create demo jobs for testing when Indeed scraping fails."""
        demo_jobs = []
        companies = ["StartupTech", "BigCorp Inc", "FinanceFlow", "HealthTech", "EduSoft"]
        titles = [
            f"{keywords} Specialist",
            f"Remote {keywords}",
            f"{keywords} Consultant",
            f"Full Stack {keywords}",
            f"Junior {keywords}"
        ]
        
        for i in range(min(4, len(companies))):
            job = JobPosting(
                title=titles[i % len(titles)],
                company=companies[i],
                location=location,
                posting_date="1 day ago",
                url=f"https://indeed.com/jobs/demo-{i+1}",
                job_board=JobBoard.INDEED,
                job_id=self._generate_job_id(titles[i % len(titles)], companies[i], f"indeed-demo-{i+1}"),
                description=f"Great opportunity for a {keywords} to join {companies[i]}. Competitive benefits!",
                salary_range="$70,000 - $110,000",
                job_type="Full-time"
            )
            demo_jobs.append(job)
        
        return demo_jobs

class GlassdoorSearcher(JobSearcher):
    """Glassdoor job searcher using web scraping."""
    
    def __init__(self, rate_limiter: RateLimiter, logger: Logger):
        super().__init__(rate_limiter, logger)
        self.base_url = "https://www.glassdoor.com/Job/jobs.htm"
    
    def search_jobs(self, keywords: str, location: str, job_limit: int = 20, **filters) -> SearchResult:
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
    
    def search_all_boards_with_limit(self, keywords: List[str], locations: List[str], 
                                   job_boards: Optional[List[JobBoard]] = None, 
                                   job_limit: int = 20, progress_callback=None) -> List[SearchResult]:
        """Search for jobs across multiple boards with a limit on results per search."""
        if job_boards is None:
            job_boards = list(self.searchers.keys())
        
        all_results = []
        
        for keyword in keywords:
            for location in locations:
                for board in job_boards:
                    if board in self.searchers:
                        try:
                            self.logger.info(f"Searching {board.value} for '{keyword}' in '{location}' (limit: {job_limit})")
                            result = self.searchers[board].search_jobs(keyword, location, job_limit=job_limit)
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
