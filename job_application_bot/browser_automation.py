"""
Browser Automation for Job Applications
Handles Selenium WebDriver setup, login automation, and form filling
"""

import os
import time
import random
from typing import Optional, Dict, Any
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import logging

class BrowserAutomator:
    """Main browser automation class for job applications."""
    
    def __init__(self):
        self.driver = None
        self.logger = logging.getLogger(__name__)
        self.linkedin_logged_in = False
        self.indeed_logged_in = False
        
        # Get credentials from environment
        self.linkedin_email = os.getenv('LINKEDIN_EMAIL')
        self.linkedin_password = os.getenv('LINKEDIN_PASSWORD')
        
        # File paths
        self.resume_path = self._find_file('documents', ['resume.pdf', 'Resume.pdf', 'cv.pdf', 'CV.pdf'])
        self.cover_letter_path = self._find_file('documents', ['cover_letter.txt', 'cover_letter.pdf', 'coverletter.txt'])
        
    def _find_file(self, directory: str, filenames: list) -> Optional[str]:
        """Find the first matching file in directory."""
        for filename in filenames:
            filepath = os.path.join(directory, filename)
            if os.path.exists(filepath):
                return os.path.abspath(filepath)
        return None
    
    def setup_driver(self) -> bool:
        """Initialize Chrome WebDriver with optimal settings."""
        try:
            chrome_options = Options()
            
            # Add arguments for better automation
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # Enable file uploads
            prefs = {
                "profile.default_content_setting_values.notifications": 2,
                "profile.default_content_settings.popups": 0,
            }
            chrome_options.add_experimental_option("prefs", prefs)
            
            # Use ChromeDriverManager to automatically handle driver
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Execute script to hide automation indicators
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.driver.implicitly_wait(10)
            self.driver.maximize_window()
            
            self.logger.info("Chrome WebDriver initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to setup Chrome driver: {e}")
            return False
    
    def close_driver(self):
        """Close the browser driver."""
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.linkedin_logged_in = False
            self.indeed_logged_in = False
    
    def wait_and_click(self, selector: str, by: By = By.CSS_SELECTOR, timeout: int = 10) -> bool:
        """Wait for element and click it."""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((by, selector))
            )
            self.driver.execute_script("arguments[0].click();", element)
            return True
        except TimeoutException:
            self.logger.warning(f"Could not click element: {selector}")
            return False
    
    def wait_and_send_keys(self, selector: str, text: str, by: By = By.CSS_SELECTOR, timeout: int = 10) -> bool:
        """Wait for element and send keys."""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, selector))
            )
            element.clear()
            element.send_keys(text)
            return True
        except TimeoutException:
            self.logger.warning(f"Could not send keys to element: {selector}")
            return False
    
    def human_delay(self, min_seconds: float = 1.0, max_seconds: float = 3.0):
        """Add human-like delay."""
        time.sleep(random.uniform(min_seconds, max_seconds))
    
    def login_linkedin(self) -> bool:
        """Login to LinkedIn using credentials from .env file."""
        if self.linkedin_logged_in:
            return True
            
        if not self.linkedin_email or not self.linkedin_password:
            self.logger.error("LinkedIn credentials not found in .env file")
            return False
            
        try:
            self.logger.info("Logging into LinkedIn...")
            self.driver.get("https://www.linkedin.com/login")
            self.human_delay(2, 4)
            
            # Enter email
            if not self.wait_and_send_keys('input#username', self.linkedin_email):
                return False
            self.human_delay(0.5, 1.5)
            
            # Enter password
            if not self.wait_and_send_keys('input#password', self.linkedin_password):
                return False
            self.human_delay(0.5, 1.5)
            
            # Click login button
            if not self.wait_and_click('button[type="submit"]'):
                return False
            
            # Wait for login to complete
            self.human_delay(3, 5)
            
            # Check if login was successful
            if "feed" in self.driver.current_url or "in.linkedin.com" in self.driver.current_url:
                self.linkedin_logged_in = True
                self.logger.info("LinkedIn login successful")
                return True
            else:
                self.logger.error("LinkedIn login failed - not redirected to feed")
                return False
                
        except Exception as e:
            self.logger.error(f"LinkedIn login error: {e}")
            return False
    
    def login_indeed_google(self) -> bool:
        """Login to Indeed using Google OAuth."""
        if self.indeed_logged_in:
            return True
            
        try:
            self.logger.info("Logging into Indeed with Google...")
            self.driver.get("https://secure.indeed.com/account/login")
            self.human_delay(2, 4)
            
            # Click "Continue with Google" button
            google_selectors = [
                'button[data-testid="google-auth-button"]',
                'button[aria-label*="Google"]',
                'button:contains("Continue with Google")',
                '.google-auth-button',
                '[data-provider="google"]'
            ]
            
            clicked = False
            for selector in google_selectors:
                if self.wait_and_click(selector, timeout=5):
                    clicked = True
                    break
            
            if not clicked:
                self.logger.error("Could not find Google login button on Indeed")
                return False
            
            self.human_delay(2, 4)
            
            # Handle Google OAuth popup (if needed)
            # Note: This assumes user is already logged into Google in browser
            # or will handle the Google login manually
            
            # Wait for redirect back to Indeed
            WebDriverWait(self.driver, 30).until(
                lambda driver: "indeed.com" in driver.current_url and "login" not in driver.current_url
            )
            
            self.indeed_logged_in = True
            self.logger.info("Indeed Google login successful")
            return True
            
        except Exception as e:
            self.logger.error(f"Indeed Google login error: {e}")
            return False
    
    def apply_linkedin_easy_apply(self, job_url: str) -> bool:
        """Apply to LinkedIn job using Easy Apply."""
        try:
            self.logger.info(f"Applying to LinkedIn job: {job_url}")
            
            # Ensure logged in
            if not self.login_linkedin():
                return False
            
            # Navigate to job
            self.driver.get(job_url)
            self.human_delay(2, 4)
            
            # Look for Easy Apply button
            easy_apply_selectors = [
                'button[aria-label*="Easy Apply"]',
                'button:contains("Easy Apply")',
                '.jobs-apply-button--top-card button',
                '.jobs-s-apply button'
            ]
            
            applied = False
            for selector in easy_apply_selectors:
                if self.wait_and_click(selector, timeout=5):
                    applied = True
                    break
            
            if not applied:
                self.logger.warning("Easy Apply button not found - job may require external application")
                return False
            
            # Handle Easy Apply flow
            return self._handle_linkedin_easy_apply_flow()
            
        except Exception as e:
            self.logger.error(f"LinkedIn Easy Apply error: {e}")
            return False
    
    def _handle_linkedin_easy_apply_flow(self) -> bool:
        """Handle the LinkedIn Easy Apply multi-step flow."""
        try:
            max_steps = 5
            current_step = 0
            
            while current_step < max_steps:
                self.human_delay(1, 2)
                current_step += 1
                
                # Check if we're done (success page or confirmation)
                if self._check_application_success():
                    self.logger.info("LinkedIn application submitted successfully")
                    return True
                
                # Fill current form
                self._fill_linkedin_form()
                
                # Look for Next/Continue button
                next_selectors = [
                    'button[aria-label="Continue to next step"]',
                    'button[aria-label="Review your application"]',
                    'button[aria-label="Submit application"]',
                    'button:contains("Next")',
                    'button:contains("Continue")',
                    'button:contains("Review")',
                    'button:contains("Submit")',
                    '.artdeco-button--primary'
                ]
                
                clicked_next = False
                for selector in next_selectors:
                    if self.wait_and_click(selector, timeout=3):
                        clicked_next = True
                        break
                
                if not clicked_next:
                    self.logger.warning("Could not find Next/Submit button")
                    break
                
                self.human_delay(1, 2)
            
            # Final check for success
            return self._check_application_success()
            
        except Exception as e:
            self.logger.error(f"LinkedIn Easy Apply flow error: {e}")
            return False
    
    def _fill_linkedin_form(self):
        """Fill LinkedIn application form fields."""
        try:
            # Handle file uploads
            self._handle_file_uploads()
            
            # Fill text fields with common patterns
            text_fields = self.driver.find_elements(By.CSS_SELECTOR, 'input[type="text"], textarea')
            
            for field in text_fields:
                try:
                    field_name = field.get_attribute('name') or field.get_attribute('id') or ''
                    field_name = field_name.lower()
                    
                    # Skip if already filled
                    if field.get_attribute('value'):
                        continue
                    
                    # Fill based on field type
                    if any(keyword in field_name for keyword in ['phone', 'mobile']):
                        field.send_keys('(555) 123-4567')  # Placeholder phone
                    elif any(keyword in field_name for keyword in ['salary', 'compensation']):
                        field.send_keys('Negotiable')
                    elif any(keyword in field_name for keyword in ['experience', 'years']):
                        field.send_keys('3')
                    elif any(keyword in field_name for keyword in ['website', 'portfolio']):
                        field.send_keys('https://github.com/username')  # Placeholder
                    
                except Exception:
                    continue
            
            # Handle dropdowns/select fields
            self._handle_dropdowns()
            
        except Exception as e:
            self.logger.warning(f"Form filling error: {e}")
    
    def _handle_file_uploads(self):
        """Handle resume and cover letter uploads."""
        try:
            file_inputs = self.driver.find_elements(By.CSS_SELECTOR, 'input[type="file"]')
            
            for file_input in file_inputs:
                input_name = (file_input.get_attribute('name') or '').lower()
                
                if 'resume' in input_name or 'cv' in input_name:
                    if self.resume_path and os.path.exists(self.resume_path):
                        file_input.send_keys(self.resume_path)
                        self.logger.info(f"Uploaded resume: {self.resume_path}")
                elif 'cover' in input_name:
                    if self.cover_letter_path and os.path.exists(self.cover_letter_path):
                        file_input.send_keys(self.cover_letter_path)
                        self.logger.info(f"Uploaded cover letter: {self.cover_letter_path}")
                        
        except Exception as e:
            self.logger.warning(f"File upload error: {e}")
    
    def _handle_dropdowns(self):
        """Handle dropdown selections."""
        try:
            dropdowns = self.driver.find_elements(By.CSS_SELECTOR, 'select')
            
            for dropdown in dropdowns:
                try:
                    options = dropdown.find_elements(By.TAG_NAME, 'option')
                    if len(options) > 1:  # Skip if only placeholder option
                        # Select second option (first real option after placeholder)
                        options[1].click()
                except Exception:
                    continue
                    
        except Exception as e:
            self.logger.warning(f"Dropdown handling error: {e}")
    
    def _check_application_success(self) -> bool:
        """Check if application was submitted successfully."""
        try:
            success_indicators = [
                'Your application was sent',
                'Application submitted',
                'Thank you for applying',
                'Application complete',
                'Successfully applied'
            ]
            
            page_text = self.driver.page_source.lower()
            return any(indicator.lower() in page_text for indicator in success_indicators)
            
        except Exception:
            return False
    
    def apply_indeed_job(self, job_url: str) -> bool:
        """Apply to Indeed job."""
        try:
            self.logger.info(f"Applying to Indeed job: {job_url}")
            
            # Ensure logged in
            if not self.login_indeed_google():
                return False
            
            # Navigate to job
            self.driver.get(job_url)
            self.human_delay(2, 4)
            
            # Look for Apply button
            apply_selectors = [
                'button[data-testid="apply-button"]',
                'button:contains("Apply now")',
                '.ia-ApplyButtonContainer button',
                '.jobsearch-IndeedApplyButton-button'
            ]
            
            applied = False
            for selector in apply_selectors:
                if self.wait_and_click(selector, timeout=5):
                    applied = True
                    break
            
            if not applied:
                self.logger.warning("Apply button not found on Indeed")
                return False
            
            self.human_delay(2, 3)
            
            # Handle Indeed application form
            return self._handle_indeed_application_form()
            
        except Exception as e:
            self.logger.error(f"Indeed application error: {e}")
            return False
    
    def _handle_indeed_application_form(self) -> bool:
        """Handle Indeed application form."""
        try:
            # Similar to LinkedIn but with Indeed-specific selectors
            self._handle_file_uploads()
            
            # Fill required fields
            self._fill_indeed_form()
            
            # Submit application
            submit_selectors = [
                'button[data-testid="submit-application"]',
                'button:contains("Submit application")',
                'button:contains("Send application")',
                '.ia-SubmitApplication-button'
            ]
            
            for selector in submit_selectors:
                if self.wait_and_click(selector, timeout=5):
                    self.human_delay(2, 3)
                    if self._check_application_success():
                        self.logger.info("Indeed application submitted successfully")
                        return True
                    break
            
            return False
            
        except Exception as e:
            self.logger.error(f"Indeed form handling error: {e}")
            return False
    
    def _fill_indeed_form(self):
        """Fill Indeed-specific form fields."""
        try:
            # Handle common Indeed form fields
            text_inputs = self.driver.find_elements(By.CSS_SELECTOR, 'input[type="text"], input[type="email"], textarea')
            
            for input_field in text_inputs:
                try:
                    field_name = (input_field.get_attribute('name') or input_field.get_attribute('placeholder') or '').lower()
                    
                    if input_field.get_attribute('value'):
                        continue  # Skip pre-filled fields
                    
                    if any(keyword in field_name for keyword in ['phone', 'mobile']):
                        input_field.send_keys('(555) 123-4567')
                    elif any(keyword in field_name for keyword in ['city', 'location']):
                        input_field.send_keys('San Francisco, CA')
                    elif any(keyword in field_name for keyword in ['salary', 'pay']):
                        input_field.send_keys('Competitive')
                        
                except Exception:
                    continue
                    
        except Exception as e:
            self.logger.warning(f"Indeed form filling error: {e}")
    
    def apply_to_job(self, job_url: str, job_board: str) -> bool:
        """Main method to apply to a job based on the job board."""
        try:
            if not self.driver:
                if not self.setup_driver():
                    return False
            
            job_board = job_board.lower()
            
            if 'linkedin' in job_board:
                return self.apply_linkedin_easy_apply(job_url)
            elif 'indeed' in job_board:
                return self.apply_indeed_job(job_url)
            else:
                self.logger.warning(f"Unsupported job board: {job_board}")
                return False
                
        except Exception as e:
            self.logger.error(f"Job application error: {e}")
            return False
        finally:
            # Keep browser open for subsequent applications
            pass 