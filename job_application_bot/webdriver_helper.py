"""
WebDriver helper with improved compatibility for macOS ARM64 and other systems.
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import platform
import os
import logging

def setup_chrome_driver(headless=False, user_data_dir=None):
    """
    Setup Chrome WebDriver with improved compatibility for macOS ARM64.
    
    Args:
        headless (bool): Whether to run in headless mode
        user_data_dir (str): Path to Chrome user data directory for persistent sessions
        
    Returns:
        webdriver.Chrome: Configured Chrome WebDriver instance
    """
    options = Options()
    
    # Basic options
    if not headless:
        options.add_argument("--start-maximized")
    else:
        options.add_argument("--headless")
        options.add_argument("--window-size=1920,1080")
    
    # Anti-detection options
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Stability and compatibility options
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-web-security")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--disable-features=VizDisplayCompositor")
    
    # User data directory for persistent sessions
    if user_data_dir:
        options.add_argument(f"--user-data-dir={user_data_dir}")
    
    # macOS ARM64 specific options
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-renderer-backgrounding")
    
    driver = None
    
    # Method 1: Try ChromeDriverManager
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        print("✅ Chrome WebDriver initialized successfully with ChromeDriverManager")
    except Exception as e:
        print(f"⚠️ ChromeDriverManager failed: {e}")
        
        # Method 2: Try system chromedriver
        try:
            driver = webdriver.Chrome(options=options)
            print("✅ Chrome WebDriver initialized successfully with system chromedriver")
        except Exception as e2:
            print(f"⚠️ System chromedriver also failed: {e2}")
            
            # Method 3: Try with explicit Chrome binary paths (macOS ARM64)
            if platform.system() == "Darwin":
                chrome_paths = [
                    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                    "/Applications/Chromium.app/Contents/MacOS/Chromium",
                    "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary"
                ]
                
                for chrome_path in chrome_paths:
                    if os.path.exists(chrome_path):
                        options.binary_location = chrome_path
                        print(f"🔧 Trying Chrome binary at: {chrome_path}")
                        break
                
                try:
                    driver = webdriver.Chrome(options=options)
                    print("✅ Chrome WebDriver initialized with explicit binary path")
                except Exception as e3:
                    print(f"❌ Explicit binary path also failed: {e3}")
            
            # Method 4: Last resort - try alternative browsers
            if not driver:
                print("🔧 Trying alternative browser setups...")
                try:
                    # Try Firefox as fallback
                    from selenium.webdriver.firefox.options import Options as FirefoxOptions
                    from selenium.webdriver.firefox.service import Service as FirefoxService
                    
                    firefox_options = FirefoxOptions()
                    if headless:
                        firefox_options.add_argument("--headless")
                    
                    driver = webdriver.Firefox(options=firefox_options)
                    print("✅ Firefox WebDriver initialized as fallback")
                except Exception as e4:
                    print(f"❌ Firefox fallback also failed: {e4}")
                    print("\n💡 Troubleshooting suggestions:")
                    print("1. Install Chrome: https://www.google.com/chrome/")
                    print("2. Install chromedriver: brew install chromedriver")
                    print("3. Or install Firefox: brew install firefox")
                    print("4. Check if Chrome is properly installed in /Applications/")
                    raise Exception("All WebDriver initialization methods failed")
    
    if driver:
        # Apply anti-detection script
        try:
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        except:
            pass  # Not critical if this fails
    
    return driver

def setup_chrome_driver_for_screenshots():
    """Setup Chrome WebDriver specifically optimized for screenshot capture."""
    return setup_chrome_driver(headless=False)

def setup_chrome_driver_for_automation(user_data_dir="job_bot_chrome_profile"):
    """Setup Chrome WebDriver for job application automation with persistent session."""
    return setup_chrome_driver(headless=False, user_data_dir=user_data_dir)

def setup_chrome_driver_headless():
    """Setup Chrome WebDriver in headless mode for server environments."""
    return setup_chrome_driver(headless=True)

# Test function
def test_webdriver_setup():
    """Test the WebDriver setup."""
    try:
        print("🧪 Testing WebDriver setup...")
        driver = setup_chrome_driver_for_screenshots()
        driver.get("https://www.google.com")
        print(f"✅ Successfully loaded Google. Page title: {driver.title}")
        driver.quit()
        print("✅ WebDriver test completed successfully")
        return True
    except Exception as e:
        print(f"❌ WebDriver test failed: {e}")
        return False

if __name__ == "__main__":
    test_webdriver_setup()
