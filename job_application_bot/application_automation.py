"""Application automation system for submitting job applications."""

import os
import time
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

from models import JobPosting, ApplicationResult, ApplicationStatus, JobBoard
from utils import Logger, FileManager, RateLimiter
from config import Config


class ApplicationAutomator(ABC):
    """Abstract base class for job application automation."""
    
    def __init__(self, config: Config, logger: Logger, rate_limiter: RateLimiter):
        self.config = config
        self.logger = logger
        self.rate_limiter = rate_limiter
        self.file_manager = FileManager()
        self.driver = None
        self.applications_today = 0
        
        # Load resume and cover letter
        self.resume_content = self._load_document(config.application.resume_path)
        self.cover_letter_content = self._load_document(config.application.cover_letter_path)
    
    def _load_document(self, file_path: str) -> Optional[str]:
        """Load document content from file."""
        if not os.path.exists(file_path):
            self.logger.warning(f"Document not found: {file_path}")
            return None
        
        content = self.file_manager.read_file(file_path)
        if content:
            self.logger.info(f"Loaded document: {file_path}")
        return content
    
    @abstractmethod
    def apply_to_job(self, job: JobPosting) -> ApplicationResult:
        """Apply to a specific job posting."""
        pass
    
    def can_apply_more(self) -> bool:
        """Check if we can submit more applications today."""
        return self.applications_today < self.config.application.daily_application_limit
    
    def _setup_driver(self):
        """Setup Chrome driver for automation."""
        try:
            chrome_options = Options()
            if not self.config.application.auto_apply_enabled:
                chrome_options.add_argument("--headless")
            
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            self.driver = webdriver.Chrome(
                service=webdriver.chrome.service.Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            
            # Remove automation indicators
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.logger.info("Chrome driver initialized for application automation")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to setup Chrome driver: {e}")
            return False
    
    def _wait_and_find_element(self, by: By, value: str, timeout: int = 10):
        """Wait for element and return it."""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except TimeoutException:
            self.logger.warning(f"Element not found: {value}")
            return None
    
    def _safe_click(self, element) -> bool:
        """Safely click an element."""
        try:
            if element and element.is_enabled():
                element.click()
                time.sleep(1)
                return True
        except Exception as e:
            self.logger.warning(f"Failed to click element: {e}")
        return False
    
    def _safe_send_keys(self, element, text: str) -> bool:
        """Safely send keys to an element."""
        try:
            if element and element.is_enabled():
                element.clear()
                element.send_keys(text)
                time.sleep(0.5)
                return True
        except Exception as e:
            self.logger.warning(f"Failed to send keys: {e}")
        return False
    
    def __del__(self):
        """Cleanup driver on destruction."""
        if self.driver:
            self.driver.quit()


class LinkedInApplicationAutomator(ApplicationAutomator):
    """LinkedIn-specific application automation."""
    
    def __init__(self, config: Config, logger: Logger, rate_limiter: RateLimiter):
        super().__init__(config, logger, rate_limiter)
        self.is_logged_in = False
    
    def apply_to_job(self, job: JobPosting) -> ApplicationResult:
        """Apply to a LinkedIn job posting."""
        if not self.can_apply_more():
            return ApplicationResult(
                job_posting=job,
                success=False,
                message="Daily application limit reached"
            )
        
        if not self.driver:
            if not self._setup_driver():
                return ApplicationResult(
                    job_posting=job,
                    success=False,
                    message="Failed to setup web driver"
                )
        
        try:
            self.rate_limiter.wait_if_needed()
            
            # Login if not already logged in
            if not self.is_logged_in:
                login_result = self._login_to_linkedin()
                if not login_result:
                    return ApplicationResult(
                        job_posting=job,
                        success=False,
                        message="Failed to login to LinkedIn"
                    )
            
            # Navigate to job posting
            self.driver.get(job.url)
            time.sleep(3)
            
            # Look for Easy Apply button
            easy_apply_btn = self._wait_and_find_element(
                By.XPATH, "//button[contains(@aria-label, 'Easy Apply')]"
            )
            
            if not easy_apply_btn:
                # Check if already applied
                applied_btn = self.driver.find_elements(
                    By.XPATH, "//button[contains(text(), 'Applied')]"
                )
                if applied_btn:
                    return ApplicationResult(
                        job_posting=job,
                        success=False,
                        message="Already applied to this job"
                    )
                
                return ApplicationResult(
                    job_posting=job,
                    success=False,
                    message="Easy Apply not available"
                )
            
            # Click Easy Apply
            if not self._safe_click(easy_apply_btn):
                return ApplicationResult(
                    job_posting=job,
                    success=False,
                    message="Failed to click Easy Apply button"
                )
            
            # Process the application form
            application_success = self._process_linkedin_application()
            
            if application_success:
                self.applications_today += 1
                return ApplicationResult(
                    job_posting=job,
                    success=True,
                    message="Application submitted successfully"
                )
            else:
                return ApplicationResult(
                    job_posting=job,
                    success=False,
                    message="Failed to complete application form"
                )
                
        except Exception as e:
            self.logger.error(f"Error applying to LinkedIn job: {e}")
            return ApplicationResult(
                job_posting=job,
                success=False,
                message=f"Application error: {str(e)}"
            )
    
    def _login_to_linkedin(self) -> bool:
        """Login to LinkedIn."""
        try:
            self.driver.get("https://www.linkedin.com/login")
            time.sleep(2)
            
            # Enter email
            email_field = self._wait_and_find_element(By.ID, "username")
            if not self._safe_send_keys(email_field, self.config.linkedin_email):
                return False
            
            # Enter password
            password_field = self._wait_and_find_element(By.ID, "password")
            if not self._safe_send_keys(password_field, self.config.linkedin_password):
                return False
            
            # Click login button
            login_btn = self._wait_and_find_element(
                By.XPATH, "//button[@type='submit']"
            )
            if not self._safe_click(login_btn):
                return False
            
            time.sleep(5)
            
            # Check if we're logged in
            if "feed" in self.driver.current_url or "in/" in self.driver.current_url:
                self.is_logged_in = True
                self.logger.info("Successfully logged into LinkedIn")
                return True
            else:
                self.logger.error("LinkedIn login failed")
                return False
                
        except Exception as e:
            self.logger.error(f"LinkedIn login error: {e}")
            return False
    
    def _process_linkedin_application(self) -> bool:
        """Process the LinkedIn Easy Apply application form."""
        try:
            max_steps = 5  # Maximum number of form steps to process
            current_step = 0
            
            while current_step < max_steps:
                time.sleep(2)
                
                # Look for Next button
                next_btn = self.driver.find_elements(
                    By.XPATH, "//button[contains(@aria-label, 'Continue') or contains(@aria-label, 'Next')]"
                )
                
                # Look for Submit button
                submit_btn = self.driver.find_elements(
                    By.XPATH, "//button[contains(@aria-label, 'Submit application')]"
                )
                
                # Look for Review button
                review_btn = self.driver.find_elements(
                    By.XPATH, "//button[contains(@aria-label, 'Review')]"
                )
                
                # Fill any visible form fields
                self._fill_linkedin_form_fields()
                
                # Handle file upload if needed
                self._handle_linkedin_file_upload()
                
                # Click appropriate button
                if submit_btn and submit_btn[0].is_enabled():
                    self._safe_click(submit_btn[0])
                    self.logger.info("Submitted LinkedIn application")
                    return True
                elif review_btn and review_btn[0].is_enabled():
                    self._safe_click(review_btn[0])
                elif next_btn and next_btn[0].is_enabled():
                    self._safe_click(next_btn[0])
                else:
                    # Check if application was completed
                    success_message = self.driver.find_elements(
                        By.XPATH, "//h3[contains(text(), 'Application sent')]"
                    )
                    if success_message:
                        return True
                    
                    self.logger.warning("No action button found in LinkedIn application")
                    break
                
                current_step += 1
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error processing LinkedIn application: {e}")
            return False
    
    def _fill_linkedin_form_fields(self):
        """Fill visible form fields in LinkedIn application."""
        try:
            # Fill text inputs
            text_inputs = self.driver.find_elements(By.TAG_NAME, "input")
            for input_field in text_inputs:
                field_type = input_field.get_attribute("type")
                if field_type in ["text", "email", "tel"]:
                    placeholder = input_field.get_attribute("placeholder") or ""
                    aria_label = input_field.get_attribute("aria-label") or ""
                    
                    # Fill based on field type
                    if "phone" in placeholder.lower() or "phone" in aria_label.lower():
                        self._safe_send_keys(input_field, "555-123-4567")
                    elif "website" in placeholder.lower() or "portfolio" in placeholder.lower():
                        self._safe_send_keys(input_field, "https://example.com")
            
            # Fill textareas (cover letter)
            textareas = self.driver.find_elements(By.TAG_NAME, "textarea")
            for textarea in textareas:
                if self.cover_letter_content:
                    self._safe_send_keys(textarea, self.cover_letter_content[:500])  # Limit length
            
            # Handle dropdowns
            selects = self.driver.find_elements(By.TAG_NAME, "select")
            for select in selects:
                try:
                    select_obj = Select(select)
                    options = select_obj.options
                    if len(options) > 1:
                        select_obj.select_by_index(1)  # Select first non-default option
                except Exception:
                    pass
                    
        except Exception as e:
            self.logger.warning(f"Error filling LinkedIn form fields: {e}")
    
    def _handle_linkedin_file_upload(self):
        """Handle file upload in LinkedIn application."""
        try:
            # Look for file upload inputs
            file_inputs = self.driver.find_elements(
                By.XPATH, "//input[@type='file']"
            )
            
            for file_input in file_inputs:
                if file_input.is_displayed() and self.config.application.resume_path:
                    # Upload resume
                    resume_path = os.path.abspath(self.config.application.resume_path)
                    if os.path.exists(resume_path):
                        file_input.send_keys(resume_path)
                        time.sleep(2)
                        self.logger.info("Uploaded resume to LinkedIn application")
                        
        except Exception as e:
            self.logger.warning(f"Error handling LinkedIn file upload: {e}")


class IndeedApplicationAutomator(ApplicationAutomator):
    """Indeed-specific application automation with Google OAuth login."""
    
    def __init__(self, config: Config, logger: Logger, rate_limiter: RateLimiter):
        super().__init__(config, logger, rate_limiter)
        self.is_logged_in = False
    
    def apply_to_job(self, job: JobPosting) -> ApplicationResult:
        """Apply to an Indeed job posting."""
        if not self.can_apply_more():
            return ApplicationResult(
                job_posting=job,
                success=False,
                message="Daily application limit reached"
            )
        
        if not self.driver:
            if not self._setup_driver():
                return ApplicationResult(
                    job_posting=job,
                    success=False,
                    message="Failed to setup web driver"
                )
        
        try:
            self.rate_limiter.wait_if_needed()
            
            # Login if not already logged in
            if not self.is_logged_in:
                login_result = self._login_to_indeed_with_google()
                if not login_result:
                    return ApplicationResult(
                        job_posting=job,
                        success=False,
                        message="Failed to login to Indeed with Google"
                    )
            
            # Navigate to job posting
            self.driver.get(job.url)
            time.sleep(3)
            
            # Look for Apply Now button
            apply_btn = self._wait_and_find_element(
                By.XPATH, "//button[contains(text(), 'Apply now') or contains(text(), 'Apply Now')]"
            )
            
            if not apply_btn:
                # Check for Easy Apply button
                apply_btn = self._wait_and_find_element(
                    By.XPATH, "//button[contains(@aria-label, 'Apply') or contains(text(), 'Apply')]"
                )
            
            if not apply_btn:
                # Check if already applied
                applied_text = self.driver.find_elements(
                    By.XPATH, "//*[contains(text(), 'Applied') or contains(text(), 'Application sent')]"
                )
                if applied_text:
                    return ApplicationResult(
                        job_posting=job,
                        success=False,
                        message="Already applied to this job"
                    )
                
                return ApplicationResult(
                    job_posting=job,
                    success=False,
                    message="Apply button not found - may be external application"
                )
            
            # Click Apply button
            if not self._safe_click(apply_btn):
                return ApplicationResult(
                    job_posting=job,
                    success=False,
                    message="Failed to click Apply button"
                )
            
            # Process the application form
            application_success = self._process_indeed_application()
            
            if application_success:
                self.applications_today += 1
                return ApplicationResult(
                    job_posting=job,
                    success=True,
                    message="Application submitted successfully"
                )
            else:
                return ApplicationResult(
                    job_posting=job,
                    success=False,
                    message="Failed to complete application form"
                )
                
        except Exception as e:
            self.logger.error(f"Error applying to Indeed job: {e}")
            return ApplicationResult(
                job_posting=job,
                success=False,
                message=f"Application error: {str(e)}"
            )
    
    def _login_to_indeed_with_google(self) -> bool:
        """Login to Indeed using Google OAuth."""
        try:
            self.driver.get("https://secure.indeed.com/account/login")
            time.sleep(3)
            
            # Look for "Sign in with Google" button
            google_login_btn = self._wait_and_find_element(
                By.XPATH, "//button[contains(text(), 'Continue with Google') or contains(text(), 'Sign in with Google') or contains(@aria-label, 'Google')]"
            )
            
            if not google_login_btn:
                # Alternative selector for Google login
                google_login_btn = self._wait_and_find_element(
                    By.XPATH, "//a[contains(@href, 'google') or contains(text(), 'Google')]"
                )
            
            if not google_login_btn:
                self.logger.error("Google login button not found on Indeed")
                return False
            
            # Click Google login button
            if not self._safe_click(google_login_btn):
                return False
            
            time.sleep(3)
            
            # Handle Google OAuth flow
            # The user's Google credentials should already be saved in the browser
            # We'll wait for the OAuth flow to complete and redirect back to Indeed
            
            # Wait for redirect back to Indeed (check for Indeed domain)
            max_wait_time = 60  # 60 seconds max wait for OAuth
            start_time = time.time()
            
            while time.time() - start_time < max_wait_time:
                current_url = self.driver.current_url
                
                # Check if we're back on Indeed and logged in
                if "indeed.com" in current_url and "login" not in current_url:
                    # Verify login by checking for user account elements
                    user_menu = self.driver.find_elements(
                        By.XPATH, "//button[contains(@aria-label, 'Account') or contains(@data-testid, 'account')]"
                    )
                    
                    if user_menu:
                        self.is_logged_in = True
                        self.logger.info("Successfully logged into Indeed with Google")
                        return True
                
                # Check if we're still in Google OAuth flow
                if "accounts.google.com" in current_url or "oauth" in current_url:
                    time.sleep(2)
                    continue
                
                time.sleep(2)
            
            # If we reach here, login likely failed or timed out
            self.logger.error("Indeed Google OAuth login timed out or failed")
            return False
                
        except Exception as e:
            self.logger.error(f"Indeed Google OAuth login error: {e}")
            return False
    
    def _process_indeed_application(self) -> bool:
        """Process the Indeed application form."""
        try:
            max_steps = 5  # Maximum number of form steps to process
            current_step = 0
            
            while current_step < max_steps:
                time.sleep(2)
                
                # Fill any visible form fields
                self._fill_indeed_form_fields()
                
                # Handle file upload if needed
                self._handle_indeed_file_upload()
                
                # Look for Continue/Next/Submit buttons
                continue_btn = self.driver.find_elements(
                    By.XPATH, "//button[contains(text(), 'Continue') or contains(text(), 'Next') or contains(text(), 'Submit')]"
                )
                
                # Look for Submit Application button
                submit_btn = self.driver.find_elements(
                    By.XPATH, "//button[contains(text(), 'Submit application') or contains(text(), 'Submit Application')]"
                )
                
                if submit_btn and submit_btn[0].is_enabled():
                    self._safe_click(submit_btn[0])
                    self.logger.info("Submitted Indeed application")
                    return True
                elif continue_btn and continue_btn[0].is_enabled():
                    self._safe_click(continue_btn[0])
                else:
                    # Check if application was completed
                    success_elements = self.driver.find_elements(
                        By.XPATH, "//*[contains(text(), 'Application sent') or contains(text(), 'Application submitted')]"
                    )
                    if success_elements:
                        return True
                    
                    self.logger.warning("No action button found in Indeed application")
                    break
                
                current_step += 1
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error processing Indeed application: {e}")
            return False
    
    def _fill_indeed_form_fields(self):
        """Fill visible form fields in Indeed application."""
        try:
            # Fill text inputs
            text_inputs = self.driver.find_elements(By.TAG_NAME, "input")
            for input_field in text_inputs:
                field_type = input_field.get_attribute("type")
                if field_type in ["text", "email", "tel"]:
                    placeholder = input_field.get_attribute("placeholder") or ""
                    name = input_field.get_attribute("name") or ""
                    
                    # Fill based on field type
                    if "phone" in placeholder.lower() or "phone" in name.lower():
                        self._safe_send_keys(input_field, "555-123-4567")
                    elif "website" in placeholder.lower() or "portfolio" in placeholder.lower():
                        self._safe_send_keys(input_field, "https://example.com")
                    elif "linkedin" in placeholder.lower() or "linkedin" in name.lower():
                        self._safe_send_keys(input_field, "https://linkedin.com/in/example")
            
            # Fill textareas (cover letter)
            textareas = self.driver.find_elements(By.TAG_NAME, "textarea")
            for textarea in textareas:
                if self.cover_letter_content and not textarea.get_attribute("value"):
                    self._safe_send_keys(textarea, self.cover_letter_content[:1000])  # Limit length
            
            # Handle dropdowns
            selects = self.driver.find_elements(By.TAG_NAME, "select")
            for select in selects:
                try:
                    select_obj = Select(select)
                    options = select_obj.options
                    if len(options) > 1:
                        select_obj.select_by_index(1)  # Select first non-default option
                except Exception:
                    pass
                    
        except Exception as e:
            self.logger.warning(f"Error filling Indeed form fields: {e}")
    
    def _handle_indeed_file_upload(self):
        """Handle file upload in Indeed application."""
        try:
            # Look for file upload inputs
            file_inputs = self.driver.find_elements(
                By.XPATH, "//input[@type='file']"
            )
            
            for file_input in file_inputs:
                if file_input.is_displayed() and self.config.application.resume_path:
                    # Upload resume
                    resume_path = os.path.abspath(self.config.application.resume_path)
                    if os.path.exists(resume_path):
                        file_input.send_keys(resume_path)
                        time.sleep(2)
                        self.logger.info("Uploaded resume to Indeed application")
                        
        except Exception as e:
            self.logger.warning(f"Error handling Indeed file upload: {e}")


class GlassdoorApplicationAutomator(ApplicationAutomator):
    """Glassdoor-specific application automation."""
    
    def apply_to_job(self, job: JobPosting) -> ApplicationResult:
        """Apply to a Glassdoor job posting."""
        # Glassdoor applications are often external
        # This is a placeholder implementation
        
        return ApplicationResult(
            job_posting=job,
            success=False,
            message="Glassdoor application automation not implemented - requires manual application"
        )


class ApplicationManager:
    """Manages the application process across different job boards."""
    
    def __init__(self, config: Config, logger: Logger, rate_limiter: RateLimiter):
        self.config = config
        self.logger = logger
        self.rate_limiter = rate_limiter
        
        # Initialize automators for each job board
        self.automators = {
            JobBoard.LINKEDIN: LinkedInApplicationAutomator(config, logger, rate_limiter),
            JobBoard.INDEED: IndeedApplicationAutomator(config, logger, rate_limiter),
            JobBoard.GLASSDOOR: GlassdoorApplicationAutomator(config, logger, rate_limiter)
        }
        
        self.total_applications_today = 0
    
    def apply_to_jobs(self, jobs: List[JobPosting]) -> List[ApplicationResult]:
        """Apply to a list of job postings."""
        results = []
        
        for job in jobs:
            if not self.can_apply_more():
                self.logger.info("Daily application limit reached")
                break
            
            if not self.config.application.auto_apply_enabled:
                # Create placeholder result for manual application
                result = ApplicationResult(
                    job_posting=job,
                    success=False,
                    message="Auto-apply disabled - manual application required"
                )
                results.append(result)
                continue
            
            # Check if we should skip external applications
            if job.url and not self.config.application.apply_to_external_sites:
                if not self._is_native_application(job):
                    result = ApplicationResult(
                        job_posting=job,
                        success=False,
                        message="External application skipped - not applying to external sites"
                    )
                    results.append(result)
                    continue
            
            # Get appropriate automator
            automator = self.automators.get(job.job_board)
            if not automator:
                result = ApplicationResult(
                    job_posting=job,
                    success=False,
                    message=f"No automator available for {job.job_board.value}"
                )
                results.append(result)
                continue
            
            # Apply to job
            self.logger.info(f"Applying to: {job.title} at {job.company}")
            result = automator.apply_to_job(job)
            results.append(result)
            
            if result.success:
                self.total_applications_today += 1
                self.logger.info(f"Successfully applied to {job.title}")
            else:
                self.logger.warning(f"Failed to apply to {job.title}: {result.message}")
            
            # Add delay between applications
            time.sleep(5)
        
        return results
    
    def can_apply_more(self) -> bool:
        """Check if we can submit more applications today."""
        return self.total_applications_today < self.config.application.daily_application_limit
    
    def _is_native_application(self, job: JobPosting) -> bool:
        """Check if the job application is native to the job board."""
        # Simple heuristic - could be improved
        job_board_domains = {
            JobBoard.LINKEDIN: "linkedin.com",
            JobBoard.INDEED: "indeed.com",
            JobBoard.GLASSDOOR: "glassdoor.com"
        }
        
        domain = job_board_domains.get(job.job_board, "")
        return domain in job.url if job.url else False
    
    def generate_application_report(self, results: List[ApplicationResult]) -> Dict[str, Any]:
        """Generate a summary report of application results."""
        total_applications = len(results)
        successful_applications = sum(1 for result in results if result.success)
        failed_applications = total_applications - successful_applications
        
        # Group by job board
        by_job_board = {}
        for result in results:
            board = result.job_posting.job_board.value
            if board not in by_job_board:
                by_job_board[board] = {"total": 0, "successful": 0, "failed": 0}
            
            by_job_board[board]["total"] += 1
            if result.success:
                by_job_board[board]["successful"] += 1
            else:
                by_job_board[board]["failed"] += 1
        
        # Common failure reasons
        failure_reasons = {}
        for result in results:
            if not result.success:
                reason = result.message
                failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_applications": total_applications,
            "successful_applications": successful_applications,
            "failed_applications": failed_applications,
            "success_rate": (successful_applications / total_applications * 100) if total_applications > 0 else 0,
            "by_job_board": by_job_board,
            "failure_reasons": failure_reasons
        }
        
        return report
