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
        self.user_profile = None
        
        # Get credentials from environment
        self.linkedin_email = os.getenv('LINKEDIN_EMAIL')
        self.linkedin_password = os.getenv('LINKEDIN_PASSWORD')
        
        # File paths
        self.resume_path = self._find_file('documents', ['resume.pdf', 'Resume.pdf', 'cv.pdf', 'CV.pdf'])
        self.cover_letter_path = self._find_file('documents', ['cover_letter.txt', 'cover_letter.pdf', 'coverletter.txt'])
        
        # Load user profile for form filling
        self._load_user_profile()
        
    def _find_file(self, directory: str, filenames: list) -> Optional[str]:
        """Find the first matching file in directory."""
        for filename in filenames:
            filepath = os.path.join(directory, filename)
            if os.path.exists(filepath):
                return os.path.abspath(filepath)
        return None
    
    def _load_user_profile(self):
        """Load user profile from database for form filling."""
        try:
            # Import here to avoid circular imports
            from app import UserProfile
            from flask import current_app
            
            with current_app.app_context():
                self.user_profile = UserProfile.query.first()
                if self.user_profile:
                    # Update resume path from profile if available
                    if self.user_profile.resume_path and os.path.exists(self.user_profile.resume_path):
                        self.resume_path = self.user_profile.resume_path
                    self.logger.info("User profile loaded successfully")
                else:
                    self.logger.warning("No user profile found in database")
        except Exception as e:
            self.logger.error(f"Failed to load user profile: {e}")
            self.user_profile = None
    
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
            
            # Use a persistent user data directory to maintain Google login session
            import tempfile
            user_data_dir = os.path.join(tempfile.gettempdir(), "job_bot_chrome_profile")
            chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
            chrome_options.add_argument("--profile-directory=JobBotProfile")
            
            # Enable file uploads
            prefs = {
                "profile.default_content_setting_values.notifications": 2,
                "profile.default_content_settings.popups": 0,
            }
            chrome_options.add_experimental_option("prefs", prefs)
            
            # Try improved WebDriver setup first
            try:
                from webdriver_helper import setup_chrome_driver
                
                # Extract user data dir for the helper
                user_data_dir = os.path.join(tempfile.gettempdir(), "job_bot_chrome_profile")
                self.driver = setup_chrome_driver(headless=False, user_data_dir=user_data_dir)
                
                # Apply additional options that the helper doesn't set
                self.driver.execute_script(f"""
                    var prefs = {{"profile.default_content_setting_values.notifications": 2, "profile.default_content_settings.popups": 0}};
                """)
                
            except ImportError:
                # Fallback to original method if webdriver_helper is not available
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            except Exception as e:
                self.logger.warning(f"WebDriver helper failed, using fallback: {e}")
                try:
                    # Try system chromedriver
                    self.driver = webdriver.Chrome(options=chrome_options)
                except Exception as e2:
                    # Final fallback with ChromeDriverManager
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
    
    def ensure_google_login(self) -> bool:
        """Ensure Google account is logged in for both LinkedIn and Indeed."""
        try:
            # Check if already logged into Google
            self.driver.get("https://accounts.google.com")
            self.human_delay(2, 3)
            
            # Look for signs of being logged in
            if "myaccount.google.com" in self.driver.current_url or "accounts.google.com/signin" not in self.driver.current_url:
                self.logger.info("Already logged into Google account")
                return True
            
            self.logger.info("Google login required - please login manually when browser opens")
            
            # Wait for manual login (check every 5 seconds for up to 2 minutes)
            for i in range(24):  # 24 * 5 = 120 seconds
                time.sleep(5)
                if "myaccount.google.com" in self.driver.current_url or "accounts.google.com/signin" not in self.driver.current_url:
                    self.logger.info("Google login detected")
                    return True
                    
            self.logger.warning("Google login timeout - continuing without login")
            return False
            
        except Exception as e:
            self.logger.error(f"Google login check failed: {e}")
            return False
    
    def login_linkedin_google(self) -> bool:
        """Login to LinkedIn using Google OAuth."""
        try:
            if self.linkedin_logged_in:
                return True
                
            self.logger.info("Attempting LinkedIn login with Google OAuth...")
            self.driver.get("https://www.linkedin.com/login")
            self.human_delay(2, 4)
            
            # Check if already logged in
            if self._is_linkedin_logged_in():
                self.linkedin_logged_in = True
                self.logger.info("Already logged into LinkedIn")
                return True
            
            # Look for Google login button
            google_selectors = [
                'button[aria-label*="Google"]',
                'button:contains("Continue with Google")',
                'div[data-test-id="google-auth"] button',
                'a[href*="google"]',
                'button[data-provider="google"]',
                '.google-auth button'
            ]
            
            google_clicked = False
            for selector in google_selectors:
                if self.wait_and_click(selector, timeout=3):
                    self.logger.info("Clicked Google login button")
                    google_clicked = True
                    break
            
            if not google_clicked:
                self.logger.info("Google login button not found on LinkedIn")
                return False
            
            # Handle Google OAuth flow
            self.human_delay(3, 5)
            
            # Check if login was successful
            if self._is_linkedin_logged_in():
                self.linkedin_logged_in = True
                self.logger.info("LinkedIn Google OAuth login successful")
                return True
            else:
                self.logger.info("LinkedIn Google OAuth login did not complete")
                return False
                
        except Exception as e:
            self.logger.error(f"LinkedIn Google OAuth login error: {e}")
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
            
            # Ensure Google login is available first
            self.ensure_google_login()
            
            # Try Google OAuth login first, fallback to regular login
            if not self.login_linkedin_google() and not self.login_linkedin():
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
                # Try external job application for other sites
                self.logger.info(f"Attempting external application for: {job_board}")
                return self.apply_to_external_job(job_url)
                
        except Exception as e:
            self.logger.error(f"Job application error: {e}")
            return False
        finally:
            # Keep browser open for subsequent applications
            pass
    
    def fill_application_form(self, form_data: Dict[str, str] = None) -> bool:
        """Fill out job application form using user profile data."""
        try:
            if not self.user_profile:
                self.logger.warning("No user profile available for form filling")
                return False
            
            # Use provided form_data or default to empty dict
            form_data = form_data or {}
            
            # Common form field selectors and their corresponding profile data
            field_mappings = {
                # Personal Information
                'first_name': ['input[name*="first"]', 'input[id*="first"]', 'input[placeholder*="First"]'],
                'last_name': ['input[name*="last"]', 'input[id*="last"]', 'input[placeholder*="Last"]'],
                'full_name': ['input[name*="name"]', 'input[id*="name"]', 'input[placeholder*="Full name"]'],
                'email': ['input[type="email"]', 'input[name*="email"]', 'input[id*="email"]'],
                'phone': ['input[type="tel"]', 'input[name*="phone"]', 'input[id*="phone"]'],
                'location': ['input[name*="location"]', 'input[name*="city"]', 'input[id*="location"]'],
                'linkedin': ['input[name*="linkedin"]', 'input[id*="linkedin"]'],
                
                # Professional Information
                'current_company': ['input[name*="company"]', 'input[id*="company"]', 'input[placeholder*="Company"]'],
                'current_title': ['input[name*="title"]', 'input[id*="title"]', 'input[placeholder*="Title"]'],
                'years_experience': ['input[name*="experience"]', 'input[id*="experience"]'],
                
                # Education
                'university': ['input[name*="school"]', 'input[name*="university"]', 'input[id*="university"]'],
                'degree': ['input[name*="degree"]', 'input[id*="degree"]', 'input[placeholder*="Degree"]'],
                'graduation_year': ['input[name*="graduation"]', 'input[id*="graduation"]']
            }
            
            # Get profile values
            profile_values = {
                'first_name': self.user_profile.first_name,
                'last_name': self.user_profile.last_name,
                'full_name': self.user_profile.full_name,
                'email': self.user_profile.email,
                'phone': self.user_profile.phone,
                'location': self.user_profile.location,
                'linkedin': self.user_profile.linkedin_profile,
                'current_company': self.user_profile.current_company,
                'current_title': self.user_profile.current_title,
                'years_experience': str(self.user_profile.years_experience) if self.user_profile.years_experience else '',
                'university': self.user_profile.university,
                'degree': self.user_profile.degree,
                'graduation_year': str(self.user_profile.graduation_year) if self.user_profile.graduation_year else ''
            }
            
            filled_fields = 0
            
            # Fill each field type
            for field_type, selectors in field_mappings.items():
                value = form_data.get(field_type) or profile_values.get(field_type)
                if not value:
                    continue
                
                for selector in selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for element in elements:
                            if element.is_displayed() and element.is_enabled():
                                # Clear existing text and fill
                                element.clear()
                                element.send_keys(value)
                                filled_fields += 1
                                self.logger.debug(f"Filled {field_type}: {value}")
                                break
                        if filled_fields > 0:
                            break
                    except Exception as e:
                        self.logger.debug(f"Could not fill {field_type} with selector {selector}: {e}")
                        continue
            
            # Handle dropdowns/select fields
            self._fill_dropdown_fields()
            
            # Handle checkboxes for demographics
            self._fill_checkbox_fields()
            
            # Upload resume if file input found
            self._upload_resume()
            
            self.logger.info(f"Filled {filled_fields} form fields")
            return filled_fields > 0
            
        except Exception as e:
            self.logger.error(f"Form filling error: {e}")
            return False
    
    def _fill_dropdown_fields(self):
        """Fill dropdown/select fields with profile data."""
        try:
            # Gender dropdown
            if self.user_profile.gender:
                gender_selectors = ['select[name*="gender"]', 'select[id*="gender"]']
                for selector in gender_selectors:
                    try:
                        select_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if select_element.is_displayed():
                            from selenium.webdriver.support.ui import Select
                            select = Select(select_element)
                            # Try to select by value or text
                            for option in select.options:
                                if self.user_profile.gender.lower() in option.text.lower():
                                    select.select_by_visible_text(option.text)
                                    break
                    except Exception:
                        continue
            
            # Race/Ethnicity dropdown
            if self.user_profile.race_ethnicity:
                race_selectors = ['select[name*="race"]', 'select[name*="ethnicity"]', 'select[id*="race"]']
                for selector in race_selectors:
                    try:
                        select_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if select_element.is_displayed():
                            from selenium.webdriver.support.ui import Select
                            select = Select(select_element)
                            # Map profile values to common dropdown options
                            race_mapping = {
                                'asian': ['Asian', 'Asian American'],
                                'black': ['Black', 'African American', 'Black or African American'],
                                'hispanic': ['Hispanic', 'Latino', 'Hispanic or Latino'],
                                'white': ['White', 'Caucasian'],
                                'american_indian': ['American Indian', 'Native American'],
                                'pacific_islander': ['Pacific Islander', 'Native Hawaiian']
                            }
                            
                            if self.user_profile.race_ethnicity in race_mapping:
                                for option_text in race_mapping[self.user_profile.race_ethnicity]:
                                    try:
                                        select.select_by_visible_text(option_text)
                                        break
                                    except:
                                        continue
                    except Exception:
                        continue
            
            # Veteran status dropdown
            if self.user_profile.veteran_status:
                veteran_selectors = ['select[name*="veteran"]', 'select[id*="veteran"]']
                for selector in veteran_selectors:
                    try:
                        select_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if select_element.is_displayed():
                            from selenium.webdriver.support.ui import Select
                            select = Select(select_element)
                            veteran_mapping = {
                                'not_veteran': ['No', 'Not a veteran', 'I am not a veteran'],
                                'veteran': ['Yes', 'Veteran', 'I am a veteran'],
                                'disabled_veteran': ['Disabled veteran', 'I am a disabled veteran']
                            }
                            
                            if self.user_profile.veteran_status in veteran_mapping:
                                for option_text in veteran_mapping[self.user_profile.veteran_status]:
                                    try:
                                        select.select_by_visible_text(option_text)
                                        break
                                    except:
                                        continue
                    except Exception:
                        continue
                        
        except Exception as e:
            self.logger.debug(f"Dropdown filling error: {e}")
    
    def _fill_checkbox_fields(self):
        """Fill checkbox fields for demographics and work authorization."""
        try:
            # Sponsorship checkbox
            if self.user_profile.sponsorship_required is not None:
                sponsorship_selectors = [
                    'input[name*="sponsor"]', 'input[id*="sponsor"]',
                    'input[name*="visa"]', 'input[id*="visa"]',
                    'input[name*="authorization"]', 'input[id*="authorization"]'
                ]
                
                for selector in sponsorship_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for element in elements:
                            if element.is_displayed() and element.get_attribute('type') == 'checkbox':
                                # Check if checkbox should be checked based on profile
                                if self.user_profile.sponsorship_required and not element.is_selected():
                                    element.click()
                                elif not self.user_profile.sponsorship_required and element.is_selected():
                                    element.click()
                                break
                    except Exception:
                        continue
            
            # Disability status checkbox
            if self.user_profile.disability_status:
                disability_selectors = ['input[name*="disability"]', 'input[id*="disability"]']
                for selector in disability_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for element in elements:
                            if element.is_displayed() and element.get_attribute('type') == 'checkbox':
                                has_disability = self.user_profile.disability_status == 'has_disability'
                                if has_disability and not element.is_selected():
                                    element.click()
                                elif not has_disability and element.is_selected():
                                    element.click()
                                break
                    except Exception:
                        continue
                        
        except Exception as e:
            self.logger.debug(f"Checkbox filling error: {e}")
    
    def _upload_resume(self):
        """Upload resume file if file input is found."""
        try:
            if not self.resume_path or not os.path.exists(self.resume_path):
                self.logger.warning("Resume file not found for upload")
                return
            
            file_input_selectors = [
                'input[type="file"]',
                'input[name*="resume"]',
                'input[name*="cv"]',
                'input[id*="resume"]',
                'input[id*="cv"]'
            ]
            
            for selector in file_input_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed():
                            element.send_keys(self.resume_path)
                            self.logger.info(f"Resume uploaded: {self.resume_path}")
                            return
                except Exception:
                    continue
                    
        except Exception as e:
            self.logger.debug(f"Resume upload error: {e}")
    
    def apply_to_external_job(self, job_url: str, company_name: str = "") -> bool:
        """Apply to external job sites using profile data."""
        try:
            self.logger.info(f"Applying to external job: {job_url}")
            
            if not self.driver:
                if not self.setup_driver():
                    return False
            
            # Navigate to job URL
            self.driver.get(job_url)
            self.human_delay(3, 5)
            
            # Look for apply buttons with various text
            apply_button_selectors = [
                'button:contains("Apply")',
                'a:contains("Apply")',
                'button[class*="apply"]',
                'a[class*="apply"]',
                'input[type="submit"][value*="Apply"]',
                '.apply-button',
                '#apply-button',
                '[data-testid*="apply"]'
            ]
            
            apply_clicked = False
            for selector in apply_button_selectors:
                if self.wait_and_click(selector, timeout=3):
                    apply_clicked = True
                    self.logger.info("Apply button clicked")
                    break
            
            if not apply_clicked:
                # Try JavaScript click for hidden buttons
                try:
                    apply_buttons = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Apply')] | //a[contains(text(), 'Apply')]")
                    if apply_buttons:
                        self.driver.execute_script("arguments[0].click();", apply_buttons[0])
                        apply_clicked = True
                        self.logger.info("Apply button clicked via JavaScript")
                except Exception:
                    pass
            
            if not apply_clicked:
                self.logger.warning("No apply button found")
                return False
            
            # Wait for application form to load
            self.human_delay(2, 4)
            
            # Fill out the application form
            form_filled = self.fill_application_form()
            
            if form_filled:
                # Look for submit button
                submit_selectors = [
                    'button[type="submit"]',
                    'input[type="submit"]',
                    'button:contains("Submit")',
                    'button:contains("Send")',
                    'button:contains("Apply")',
                    '.submit-button',
                    '#submit-button'
                ]
                
                for selector in submit_selectors:
                    if self.wait_and_click(selector, timeout=5):
                        self.logger.info("Application submitted")
                        self.human_delay(2, 3)
                        return True
                
                self.logger.warning("Submit button not found")
                return False
            else:
                self.logger.warning("Could not fill application form")
                return False
                
        except Exception as e:
            self.logger.error(f"External job application error: {e}")
            return False