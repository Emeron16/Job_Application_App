"""
Flask Web Application for Job Application Bot
"""

import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_socketio import SocketIO, emit
from datetime import datetime
import threading
import json

# Removed main.py dependency - using web-app-only components
from models import JobBoard, ApplicationStatus

# Initialize Flask app
app = Flask(__name__, template_folder='app/templates', static_folder='app/static')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Database configuration
database_url = os.environ.get('DATABASE_URL', 'postgresql://postgres@localhost:5430/job_application_bot')
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)
socketio = SocketIO(app, 
                   cors_allowed_origins=["http://127.0.0.1:5002", "http://localhost:5002"],
                   async_mode='threading',
                   logger=True,
                   engineio_logger=True)

# Add custom Jinja2 filters
@app.template_filter('from_json')
def from_json_filter(value):
    """Parse JSON string to Python object."""
    if not value:
        return []
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []

# Database Models
class JobPosting(db.Model):
    __tablename__ = 'job_postings'
    
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.String(255), unique=True, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    company = db.Column(db.String(255), nullable=False)
    location = db.Column(db.String(255), nullable=False)
    posting_date = db.Column(db.String(50))
    url = db.Column(db.Text)
    job_board = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    salary_range = db.Column(db.String(255))
    job_type = db.Column(db.String(100))
    experience_level = db.Column(db.String(100))
    skills_required = db.Column(db.Text)  # JSON string
    company_size = db.Column(db.String(100))
    industry = db.Column(db.String(100))
    has_easy_apply = db.Column(db.Boolean, default=False)  # Whether job has Easy Apply option
    application_status = db.Column(db.String(50), default='not_applied')
    applied_date = db.Column(db.DateTime)
    status_changed_date = db.Column(db.DateTime, default=datetime.utcnow)  # When status was last changed
    application_notes = db.Column(db.Text)
    recruiter_notes = db.Column(db.Text)  # Notes about recruiter communications
    scraped_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'job_id': self.job_id,
            'title': self.title,
            'company': self.company,
            'location': self.location,
            'posting_date': self.posting_date,
            'url': self.url,
            'job_board': self.job_board,
            'description': self.description,
            'salary_range': self.salary_range,
            'job_type': self.job_type,
            'experience_level': self.experience_level,
            'skills_required': json.loads(self.skills_required) if self.skills_required else [],
            'company_size': self.company_size,
            'industry': self.industry,
            'has_easy_apply': self.has_easy_apply,
            'application_status': self.application_status,
            'applied_date': self.applied_date.isoformat() if self.applied_date else None,
            'status_changed_date': self.status_changed_date.isoformat() if self.status_changed_date else None,
            'application_notes': self.application_notes,
            'recruiter_notes': self.recruiter_notes,
            'scraped_date': self.scraped_date.isoformat() if self.scraped_date else None
        }

class JobPreferences(db.Model):
    __tablename__ = 'job_preferences'
    
    id = db.Column(db.Integer, primary_key=True)
    keywords = db.Column(db.Text)  # JSON string
    locations = db.Column(db.Text)  # JSON string
    experience_levels = db.Column(db.Text)  # JSON string
    job_types = db.Column(db.Text)  # JSON string
    exclude_keywords = db.Column(db.Text)  # JSON string
    salary_min = db.Column(db.Integer)
    date_posted = db.Column(db.String(50))
    job_search_limit = db.Column(db.Integer, default=20)
    auto_apply_enabled = db.Column(db.Boolean, default=False)
    apply_to_external_sites = db.Column(db.Boolean, default=False)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    updated_date = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class UserProfile(db.Model):
    __tablename__ = 'user_profile'
    
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    full_name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    location = db.Column(db.String(255), nullable=False)
    linkedin_profile = db.Column(db.String(500))
    pronouns = db.Column(db.String(50))
    sponsorship_required = db.Column(db.Boolean, default=False)
    gender = db.Column(db.String(50))
    race_ethnicity = db.Column(db.String(100))
    veteran_status = db.Column(db.String(50))
    disability_status = db.Column(db.String(50))
    
    # Additional fields for job applications
    current_company = db.Column(db.String(200))
    current_title = db.Column(db.String(200))
    years_experience = db.Column(db.Integer)
    education_level = db.Column(db.String(100))
    university = db.Column(db.String(200))
    degree = db.Column(db.String(200))
    graduation_year = db.Column(db.Integer)
    
    # Resume and cover letter paths
    resume_path = db.Column(db.String(500))
    cover_letter_template = db.Column(db.Text)
    
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    updated_date = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'email': self.email,
            'phone': self.phone,
            'location': self.location,
            'linkedin_profile': self.linkedin_profile,
            'pronouns': self.pronouns,
            'sponsorship_required': self.sponsorship_required,
            'gender': self.gender,
            'race_ethnicity': self.race_ethnicity,
            'veteran_status': self.veteran_status,
            'disability_status': self.disability_status,
            'current_company': self.current_company,
            'current_title': self.current_title,
            'years_experience': self.years_experience,
            'education_level': self.education_level,
            'university': self.university,
            'degree': self.degree,
            'graduation_year': self.graduation_year,
            'resume_path': self.resume_path,
            'cover_letter_template': self.cover_letter_template
        }

# Web-app-only job search system
def get_job_search_manager():
    """Get job search manager for web app."""
    try:
        from job_searchers import JobSearchManager
        from utils import Logger, RateLimiter
        
        logger = Logger()
        rate_limiter = RateLimiter(requests_per_minute=30, requests_per_hour=100)
        
        return JobSearchManager(rate_limiter, logger)
    except Exception as e:
        print(f"❌ Failed to initialize JobSearchManager: {e}")
        import traceback
        traceback.print_exc()
        return None

# SocketIO event handlers
@socketio.on('connect')
def handle_connect():
    print(f'🔌 Client connected: {request.sid}')
    emit('connection_status', {'status': 'connected', 'message': 'Successfully connected to Job Application Bot'})

@socketio.on('disconnect')
def handle_disconnect():
    print(f'🔌 Client disconnected: {request.sid}')

@socketio.on('ping')
def handle_ping():
    emit('pong', {'timestamp': datetime.utcnow().isoformat()})

# Routes
@app.route('/')
def dashboard():
    """Main dashboard page"""
    # Get job statistics
    total_jobs = JobPosting.query.count()
    applied_jobs = JobPosting.query.filter_by(application_status='applied').count()
    failed_jobs = JobPosting.query.filter_by(application_status='failed').count()
    pending_jobs = JobPosting.query.filter_by(application_status='not_applied').count()
    
    # Recent jobs (last 7 days)
    from datetime import timedelta
    recent_cutoff = datetime.utcnow() - timedelta(days=7)
    recent_jobs = JobPosting.query.filter(JobPosting.scraped_date >= recent_cutoff).count()
    
    # Jobs by board
    linkedin_jobs = JobPosting.query.filter_by(job_board='linkedin').count()
    indeed_jobs = JobPosting.query.filter_by(job_board='indeed').count()
    glassdoor_jobs = JobPosting.query.filter_by(job_board='glassdoor').count()
    
    stats = {
        'total_jobs': total_jobs,
        'applied_jobs': applied_jobs,
        'failed_jobs': failed_jobs,
        'pending_jobs': pending_jobs,
        'recent_jobs': recent_jobs,
        'linkedin_jobs': linkedin_jobs,
        'indeed_jobs': indeed_jobs,
        'glassdoor_jobs': glassdoor_jobs
    }
    
    # Get recent job postings for display
    recent_postings = JobPosting.query.order_by(JobPosting.scraped_date.desc()).limit(10).all()
    
    return render_template('dashboard.html', stats=stats, recent_jobs=recent_postings)

@app.route('/jobs')
def jobs():
    """Job search and management page"""
    # Get filter parameters
    status_filter = request.args.get('status', 'all')
    board_filter = request.args.get('board', 'all')
    apply_type_filter = request.args.get('apply_type', 'all')
    search_query = request.args.get('search', '')
    
    # Build query
    query = JobPosting.query
    
    if status_filter != 'all':
        query = query.filter_by(application_status=status_filter)
    
    if board_filter != 'all':
        query = query.filter_by(job_board=board_filter)
    
    # Filter by application type
    if apply_type_filter == 'quick_apply':
        # Jobs with Easy Apply (LinkedIn) or Indeed direct apply
        query = query.filter(
            db.or_(
                db.and_(JobPosting.job_board == 'linkedin', JobPosting.has_easy_apply == True),
                db.and_(JobPosting.job_board == 'indeed', JobPosting.has_easy_apply == True)
            )
        )
    elif apply_type_filter == 'manual_apply':
        # Jobs without Easy Apply or from other job boards
        query = query.filter(
            db.or_(
                db.and_(JobPosting.job_board == 'linkedin', JobPosting.has_easy_apply == False),
                db.and_(JobPosting.job_board == 'indeed', JobPosting.has_easy_apply == False),
                ~JobPosting.job_board.in_(['linkedin', 'indeed'])
            )
        )
    
    if search_query:
        query = query.filter(
            db.or_(
                JobPosting.title.ilike(f'%{search_query}%'),
                JobPosting.company.ilike(f'%{search_query}%'),
                JobPosting.description.ilike(f'%{search_query}%')
            )
        )
    
    # Get jobs with pagination
    page = request.args.get('page', 1, type=int)
    jobs = query.order_by(JobPosting.scraped_date.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('jobs.html', jobs=jobs, 
                         status_filter=status_filter, 
                         board_filter=board_filter, 
                         apply_type_filter=apply_type_filter,
                         search_query=search_query)

@app.route('/preferences')
def preferences():
    """Job preferences configuration page"""
    # Get current preferences or create default
    prefs = JobPreferences.query.first()
    if not prefs:
        prefs = JobPreferences(
            keywords='["software engineer", "python developer"]',
            locations='["Remote", "Hybrid", "San Francisco", "New York"]',
            experience_levels='["entry", "mid", "senior"]',
            job_types='["full-time", "contract"]',
            exclude_keywords='[]',
            date_posted='week'
        )
        db.session.add(prefs)
        db.session.commit()
    
    return render_template('preferences.html', preferences=prefs)

@app.route('/preferences', methods=['POST'])
def update_preferences():
    """Update job preferences"""
    prefs = JobPreferences.query.first()
    if not prefs:
        prefs = JobPreferences()
        db.session.add(prefs)
    
    # Update preferences from form
    # Handle keywords and locations which come as JSON strings from the frontend
    keywords_data = request.form.get('keywords', '[]')
    locations_data = request.form.get('locations', '[]')
    
    # If already JSON strings, use them directly; otherwise convert lists
    try:
        # Try to parse as JSON first (from new bubble UI)
        json.loads(keywords_data)
        prefs.keywords = keywords_data
    except (json.JSONDecodeError, TypeError):
        # Fallback for old format or direct list
        prefs.keywords = json.dumps(request.form.getlist('keywords'))
    
    try:
        # Try to parse as JSON first (from new bubble UI)  
        json.loads(locations_data)
        prefs.locations = locations_data
    except (json.JSONDecodeError, TypeError):
        # Fallback for old format or direct list
        prefs.locations = json.dumps(request.form.getlist('locations'))
    
    prefs.experience_levels = json.dumps(request.form.getlist('experience_levels'))
    prefs.job_types = json.dumps(request.form.getlist('job_types'))
    prefs.exclude_keywords = json.dumps(request.form.getlist('exclude_keywords'))
    
    # Handle salary_min - convert to int if not empty, otherwise None
    salary_min_value = request.form.get('salary_min', '').strip()
    prefs.salary_min = int(salary_min_value) if salary_min_value else None
    
    prefs.date_posted = request.form.get('date_posted', 'week')
    prefs.job_search_limit = int(request.form.get('job_search_limit', 20))
    prefs.auto_apply_enabled = 'auto_apply_enabled' in request.form
    prefs.apply_to_external_sites = 'apply_to_external_sites' in request.form
    prefs.updated_date = datetime.utcnow()
    
    db.session.commit()
    flash('Preferences updated successfully!', 'success')
    return redirect(url_for('preferences'))

@app.route('/profile')
def profile():
    """User profile configuration page"""
    # Get current profile or create default
    user_profile = UserProfile.query.first()
    if not user_profile:
        user_profile = UserProfile(
            first_name='',
            last_name='',
            full_name='',
            email='',
            phone='',
            location='',
            linkedin_profile='',
            pronouns='',
            sponsorship_required=False,
            gender='',
            race_ethnicity='',
            veteran_status='',
            disability_status='',
            current_company='',
            current_title='',
            years_experience=0,
            education_level='',
            university='',
            degree='',
            graduation_year=None,
            resume_path='',
            cover_letter_template=''
        )
        db.session.add(user_profile)
        db.session.commit()
    
    return render_template('profile.html', profile=user_profile)

@app.route('/profile', methods=['POST'])
def update_profile():
    """Update user profile"""
    user_profile = UserProfile.query.first()
    if not user_profile:
        user_profile = UserProfile()
        db.session.add(user_profile)
    
    # Update profile from form
    user_profile.first_name = request.form.get('first_name', '').strip()
    user_profile.last_name = request.form.get('last_name', '').strip()
    user_profile.full_name = request.form.get('full_name', '').strip()
    user_profile.email = request.form.get('email', '').strip()
    user_profile.phone = request.form.get('phone', '').strip()
    user_profile.location = request.form.get('location', '').strip()
    user_profile.linkedin_profile = request.form.get('linkedin_profile', '').strip()
    user_profile.pronouns = request.form.get('pronouns', '').strip()
    user_profile.sponsorship_required = 'sponsorship_required' in request.form
    user_profile.gender = request.form.get('gender', '').strip()
    user_profile.race_ethnicity = request.form.get('race_ethnicity', '').strip()
    user_profile.veteran_status = request.form.get('veteran_status', '').strip()
    user_profile.disability_status = request.form.get('disability_status', '').strip()
    
    # Additional fields
    user_profile.current_company = request.form.get('current_company', '').strip()
    user_profile.current_title = request.form.get('current_title', '').strip()
    
    # Handle years_experience - convert to int if not empty, otherwise None
    years_exp_value = request.form.get('years_experience', '').strip()
    user_profile.years_experience = int(years_exp_value) if years_exp_value else 0
    
    user_profile.education_level = request.form.get('education_level', '').strip()
    user_profile.university = request.form.get('university', '').strip()
    user_profile.degree = request.form.get('degree', '').strip()
    
    # Handle graduation_year - convert to int if not empty, otherwise None
    grad_year_value = request.form.get('graduation_year', '').strip()
    user_profile.graduation_year = int(grad_year_value) if grad_year_value else None
    
    user_profile.resume_path = request.form.get('resume_path', '').strip()
    user_profile.cover_letter_template = request.form.get('cover_letter_template', '').strip()
    user_profile.updated_date = datetime.utcnow()
    
    db.session.commit()
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('profile'))

@app.route('/api/search_jobs', methods=['POST'])
def api_search_jobs():
    """API endpoint to search for new jobs"""
    try:
        data = request.get_json()
        job_boards = data.get('job_boards', ['linkedin', 'indeed', 'glassdoor'])
        collect_screenshots = data.get('collect_screenshots', False)  # New parameter for ML training
        
        # Get user preferences for job search limit
        prefs = JobPreferences.query.first()
        job_limit = prefs.job_search_limit if prefs else 20
        
        # Convert string names to JobBoard enums
        board_enums = []
        for board in job_boards:
            if board == 'linkedin':
                board_enums.append(JobBoard.LINKEDIN)
            elif board == 'indeed':
                board_enums.append(JobBoard.INDEED)
            elif board == 'glassdoor':
                board_enums.append(JobBoard.GLASSDOOR)
        
        # Run job search in background thread with live updates
        def search_jobs_background():
            with app.app_context():  # Add Flask application context
                try:
                    socketio.emit('search_status', {'status': 'started', 'message': 'Job search started...'})
                    
                    def progress_callback(data):
                        socketio.emit('search_status', data)
                    
                    search_manager = get_job_search_manager()
                    print(f"🔍 Search manager instance: {search_manager}")
                    if search_manager is None:
                        raise Exception("Search manager initialization failed")
                    
                    # Get search preferences
                    prefs = JobPreferences.query.first()
                    keywords = json.loads(prefs.keywords) if prefs and prefs.keywords else ['Software Engineer']
                    locations = json.loads(prefs.locations) if prefs and prefs.locations else ['Remote']
                    
                    print(f"🔍 Searching with keywords: {keywords}, locations: {locations}, boards: {board_enums}, limit: {job_limit}")
                    
                    # Search jobs and save to database
                    from flask_storage import FlaskDatabaseStorage
                    storage = FlaskDatabaseStorage(search_manager.logger)
                    
                    # Use the correct method from JobSearchManager
                    try:
                        print("🔍 Starting job search...")
                        results = search_manager.search_all_boards_with_limit(
                            keywords=keywords,
                            locations=locations, 
                            job_boards=board_enums,
                            job_limit=job_limit,
                            progress_callback=progress_callback  # Add the progress callback
                        )
                        print(f"🔍 Search completed, got {len(results)} result objects")
                        
                        all_jobs = []
                        screenshot_urls = []  # Collect URLs for screenshot collection
                        
                        for result in results:
                            print(f"🔍 Processing result from {result.job_board.value}: {len(result.jobs_found) if result.jobs_found else 0} jobs")
                            if result.jobs_found:
                                all_jobs.extend(result.jobs_found)
                                
                                # Collect URLs for screenshot collection if requested
                                if collect_screenshots:
                                    for job in result.jobs_found:
                                        if hasattr(job, 'url') and job.url:
                                            screenshot_urls.append({
                                                'url': job.url,
                                                'title': getattr(job, 'title', 'Unknown'),
                                                'company': getattr(job, 'company', 'Unknown'),
                                                'platform': getattr(job, 'platform', 'Unknown')
                                            })
                                
                                # Emit progress update for each board result
                                socketio.emit('search_status', {
                                    'status': 'progress',
                                    'message': f'Found {len(result.jobs_found)} jobs from {result.job_board.value}',
                                    'jobs_count': len(all_jobs)
                                })
                            else:
                                # Emit update even for failed searches
                                socketio.emit('search_status', {
                                    'status': 'progress',
                                    'message': f'No jobs found from {result.job_board.value}',
                                    'jobs_count': len(all_jobs)
                                })
                                if result.errors:
                                    print(f"⚠️ {result.job_board.value} errors: {result.errors}")
                    except Exception as e:
                        print(f"Error in job search: {e}")
                        all_jobs = []
                        screenshot_urls = []
                    
                    # Save jobs to database
                    if all_jobs:
                        storage.save_jobs(all_jobs)
                        print(f"🔍 Saved {len(all_jobs)} jobs to database")
                    
                    jobs = all_jobs
                    
                    # Start screenshot collection as separate background task if requested
                    if collect_screenshots and screenshot_urls:
                        socketio.emit('search_status', {
                            'status': 'screenshots_starting', 
                            'message': f'Starting screenshot collection for {len(screenshot_urls)} jobs...',
                            'jobs_count': len(jobs)
                        })
                        
                        # Start screenshot collection in separate thread
                        screenshot_thread = threading.Thread(
                            target=collect_screenshots_background, 
                            args=(screenshot_urls,)
                        )
                        screenshot_thread.daemon = True
                        screenshot_thread.start()
                    
                    socketio.emit('search_status', {
                        'status': 'completed', 
                        'message': f'Search completed! Found {len(jobs)} jobs.' + 
                                  (f' Screenshot collection started for {len(screenshot_urls)} jobs.' if collect_screenshots and screenshot_urls else ''),
                        'jobs_count': len(jobs),
                        'screenshot_collection': collect_screenshots and len(screenshot_urls) > 0
                    })
                    
                except Exception as e:
                    socketio.emit('search_status', {
                        'status': 'error', 
                        'message': f'Search failed: {str(e)}'
                    })
        
        thread = threading.Thread(target=search_jobs_background)
        thread.start()
        
        return jsonify({'status': 'success', 'message': 'Job search started'})
    
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

def _handle_cloudflare_verification(driver):
    """Handle Cloudflare verification if present"""
    try:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        # Check for Cloudflare verification elements
        cloudflare_selectors = [
            '.cf-browser-verification',
            '.cf-checking-browser',
            '[data-ray-id]',
            'h1:contains("Checking")',
            '.cf-wrapper'
        ]
        
        for selector in cloudflare_selectors:
            try:
                if 'contains' in selector:
                    xpath = "//h1[contains(text(), 'Checking')] | //h1[contains(text(), 'verification')]"
                    elements = driver.find_elements(By.XPATH, xpath)
                else:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                
                if elements:
                    print("🛡️ Cloudflare verification detected, waiting...")
                    # Wait for verification to complete (up to 30 seconds)
                    WebDriverWait(driver, 30).until_not(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    print("✅ Cloudflare verification completed")
                    return True
            except:
                continue
                
        return False
    except Exception as e:
        print(f"⚠️ Error handling Cloudflare verification: {e}")
        return False

def _capture_application_form(driver, job_info, job_number, screenshots_dir):
    """Navigate to and capture application form screenshot"""
    try:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        # Platform-specific apply button selectors
        apply_selectors = {
            'linkedin': [
                'button[aria-label*="Easy Apply"]',
                '.jobs-apply-button',
                'button:contains("Easy Apply")',
                '.artdeco-button--primary'
            ],
            'indeed': [
                'button[data-jk]',
                '.jobsearch-IndeedApplyButton',
                'button:contains("Apply now")',
                '.ia-IndeedApplyButton'
            ],
            'glassdoor': [
                'button:contains("Easy Apply")',
                '.apply-btn',
                'button[data-test="apply-btn"]'
            ]
        }
        
        platform = job_info.get('platform', 'unknown').lower()
        selectors = apply_selectors.get(platform, apply_selectors['indeed'])  # Default to indeed
        
        clicked_apply = False
        for selector in selectors:
            try:
                if 'contains' in selector:
                    # Use XPath for text-based selection
                    text = selector.split(':contains("')[1].split('")')[0]
                    xpath = f"//button[contains(text(), '{text}')] | //a[contains(text(), '{text}')]"
                    elements = driver.find_elements(By.XPATH, xpath)
                    if elements and elements[0].is_displayed():
                        driver.execute_script("arguments[0].click();", elements[0])
                        clicked_apply = True
                        print(f"✅ Clicked apply button using XPath: {text}")
                        break
                else:
                    element = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    if element.is_displayed():
                        driver.execute_script("arguments[0].click();", element)
                        clicked_apply = True
                        print(f"✅ Clicked apply button using CSS: {selector}")
                        break
            except Exception as e:
                print(f"⚠️ Failed to click selector {selector}: {e}")
                continue
        
        if clicked_apply:
            # Wait for form to load
            time.sleep(5)
            
            # Wait for form elements to appear
            form_selectors = [
                'form',
                'input[type="text"]',
                'input[type="email"]',
                'textarea',
                '.application-form',
                '.job-application'
            ]
            
            form_found = False
            for form_selector in form_selectors:
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, form_selector))
                    )
                    form_found = True
                    break
                except:
                    continue
            
            if form_found or "apply" in driver.current_url.lower():
                # Take screenshot of application form
                form_filename = f"{job_info['platform']}_{job_number:03d}_form_{job_info['title'][:30].replace(' ', '_').replace('/', '_')}.png"
                form_filepath = screenshots_dir / form_filename
                
                driver.save_screenshot(str(form_filepath))
                print(f"✅ Captured application form screenshot: {form_filename}")
                
                # Go back to job page for next iteration
                driver.back()
                time.sleep(2)
                return True
            else:
                print("⚠️ No application form found after clicking apply")
        else:
            print("⚠️ Could not find or click apply button")
        
        return False
        
    except Exception as e:
        print(f"❌ Error capturing application form: {e}")
        return False

def collect_screenshots_background(screenshot_urls):
    """Background function to collect screenshots for ML training"""
    # Initialize stop flag
    collect_screenshots_background.should_stop = False
    
    with app.app_context():
        try:
            from pathlib import Path
            import time
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.common.by import By
            
            # Create screenshots directory with timestamp
            timestamp = int(time.time())
            screenshots_dir = Path(f"ml_training_data/screenshots_{timestamp}")
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            
            print(f"📸 Starting screenshot collection for {len(screenshot_urls)} jobs")
            socketio.emit('screenshot_status', {
                'status': 'started',
                'message': f'Starting screenshot collection for {len(screenshot_urls)} jobs...',
                'total_jobs': len(screenshot_urls),
                'completed': 0,
                'jobs_count': 0,  # Add jobs_count for consistency
                'can_background': True,  # Allow backgrounding
                'can_stop': True  # Allow stopping
            })
            
            # Initialize the optimized screenshot collector
            try:
                from webdriver_helper import setup_chrome_driver_for_screenshots
                print("🔧 Initializing WebDriver for screenshot collection...")
                driver = setup_chrome_driver_for_screenshots()
                print("✅ WebDriver initialized successfully")
                
                # Test that driver is working by navigating to a simple page first
                print("🧪 Testing WebDriver with Google...")
                driver.get("https://www.google.com")
                time.sleep(2)
                print(f"✅ WebDriver test successful, current URL: {driver.current_url}")
                
                successful_screenshots = 0
                failed_screenshots = 0
                
                for i, job_info in enumerate(screenshot_urls):
                    try:
                        # Check if collection was stopped
                        if hasattr(collect_screenshots_background, 'should_stop') and collect_screenshots_background.should_stop:
                            print("📸 Screenshot collection stopped by user")
                            break
                            
                        print(f"📸 Capturing screenshot {i+1}/{len(screenshot_urls)}: {job_info['title']}")
                        
                        # Navigate to job page
                        driver.get(job_info['url'])
                        time.sleep(5)  # Longer wait for page load and potential Cloudflare
                        
                        # Check for Cloudflare verification
                        if _handle_cloudflare_verification(driver):
                            time.sleep(10)  # Wait for verification to complete
                        
                        # Take initial screenshot of job page
                        job_filename = f"{job_info['platform']}_{i+1:03d}_{job_info['title'][:30].replace(' ', '_').replace('/', '_')}.png"
                        job_filepath = screenshots_dir / job_filename
                        
                        driver.save_screenshot(str(job_filepath))
                        successful_screenshots += 1
                        print(f"✅ Captured job page screenshot: {job_filename}")
                        
                        # Try to find and click apply button for application form screenshot
                        form_captured = _capture_application_form(driver, job_info, i+1, screenshots_dir)
                        if form_captured:
                            successful_screenshots += 1
                        
                        # Emit progress update
                        socketio.emit('screenshot_status', {
                            'status': 'progress',
                            'message': f'Captured screenshot {i+1}/{len(screenshot_urls)}: {job_info["title"][:50]}...',
                            'total_jobs': len(screenshot_urls),
                            'completed': i + 1,
                            'successful': successful_screenshots,
                            'failed': failed_screenshots,
                            'can_background': True
                        })
                        
                        # Reasonable delay to avoid overwhelming servers and handle rate limiting
                        time.sleep(3)
                        
                    except Exception as e:
                        failed_screenshots += 1
                        print(f"❌ Error capturing screenshot for {job_info['title']}: {e}")
                        continue
                
                # Clean up
                driver.quit()
                
                # Final status update
                if hasattr(collect_screenshots_background, 'should_stop') and collect_screenshots_background.should_stop:
                    socketio.emit('screenshot_status', {
                        'status': 'stopped',
                        'message': f'Screenshot collection stopped by user. {successful_screenshots} screenshots captured before stopping.',
                        'total_jobs': len(screenshot_urls),
                        'completed': i + 1,  # Use actual completed count
                        'successful': successful_screenshots,
                        'failed': failed_screenshots,
                        'screenshots_dir': str(screenshots_dir),
                        'can_background': False,
                        'can_stop': False
                    })
                else:
                    socketio.emit('screenshot_status', {
                        'status': 'completed',
                        'message': f'Screenshot collection completed! {successful_screenshots} successful, {failed_screenshots} failed.',
                        'total_jobs': len(screenshot_urls),
                        'completed': len(screenshot_urls),
                        'successful': successful_screenshots,
                        'failed': failed_screenshots,
                        'screenshots_dir': str(screenshots_dir),
                        'can_background': False,
                        'can_stop': False
                    })
                
                print(f"📸 Screenshot collection completed: {successful_screenshots} successful, {failed_screenshots} failed")
                print(f"📁 Screenshots saved to: {screenshots_dir}")
                
            except Exception as e:
                print(f"❌ Screenshot collection failed: {e}")
                socketio.emit('screenshot_status', {
                    'status': 'error',
                    'message': f'Screenshot collection failed: {str(e)}'
                })
                
        except Exception as e:
            print(f"❌ Screenshot background task failed: {e}")
            socketio.emit('screenshot_status', {
                'status': 'error',
                'message': f'Screenshot task failed: {str(e)}'
            })

@app.route('/api/collect_screenshots', methods=['POST'])
def api_collect_screenshots():
    """API endpoint to collect screenshots from existing job URLs for ML training"""
    try:
        data = request.get_json()
        job_ids = data.get('job_ids', [])
        max_screenshots = data.get('max_screenshots', 50)
        
        if not job_ids:
            # Get recent jobs if no specific IDs provided
            recent_jobs = JobPosting.query.filter(
                JobPosting.url.isnot(None)
            ).order_by(JobPosting.scraped_date.desc()).limit(max_screenshots).all()
            job_ids = [job.id for job in recent_jobs]
        
        # Get job URLs from database
        jobs = JobPosting.query.filter(JobPosting.id.in_(job_ids)).all()
        screenshot_urls = []
        
        for job in jobs:
            if job.url:
                screenshot_urls.append({
                    'url': job.url,
                    'title': job.title,
                    'company': job.company,
                    'platform': job.job_board
                })
        
        if not screenshot_urls:
            return jsonify({'status': 'error', 'message': 'No valid job URLs found'}), 400
        
        # Start screenshot collection in background
        screenshot_thread = threading.Thread(
            target=collect_screenshots_background, 
            args=(screenshot_urls,)
        )
        screenshot_thread.daemon = True
        screenshot_thread.start()
        
        return jsonify({
            'status': 'success', 
            'message': f'Screenshot collection started for {len(screenshot_urls)} jobs',
            'job_count': len(screenshot_urls)
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/screenshot_control', methods=['POST'])
def api_screenshot_control():
    """API endpoint to control screenshot collection (background/stop)"""
    try:
        data = request.get_json()
        action = data.get('action')  # 'background' or 'stop'
        
        if action == 'background':
            socketio.emit('screenshot_status', {
                'status': 'backgrounded',
                'message': 'Screenshot collection moved to background. You can continue using the app.',
                'can_background': False,  # Hide background button
                'can_stop': True  # Show stop button
            })
            return jsonify({'status': 'success', 'message': 'Screenshot collection moved to background'})
            
        elif action == 'stop':
            # Set stop flag
            collect_screenshots_background.should_stop = True
            socketio.emit('screenshot_status', {
                'status': 'stopped',
                'message': 'Screenshot collection stopped by user.',
                'can_background': False,
                'can_stop': False
            })
            return jsonify({'status': 'success', 'message': 'Screenshot collection stopped'})
            
        else:
            return jsonify({'status': 'error', 'message': 'Invalid action'}), 400
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/apply_jobs', methods=['POST'])
def api_apply_jobs():
    """API endpoint to apply to jobs"""
    try:
        data = request.get_json()
        job_ids = data.get('job_ids', [])
        max_applications = data.get('max_applications', 10)
        
        # Clean logging
        print(f"📝 Job application request: {len(job_ids)} jobs, max_applications: {max_applications}")
        
        if job_ids:
                        # Apply to specific jobs
            def apply_specific_jobs_background():
                with app.app_context():  # Fix: Add Flask application context
                    try:
                        print(f"🔍 DEBUG: Starting background job application for {len(job_ids)} jobs")
                        applied_count = 0
                        failed_count = 0
                        
                        # Get current preferences to check external site settings
                        prefs = JobPreferences.query.first()
                        apply_to_external = prefs.apply_to_external_sites if prefs else True  # Default to True for manual applications
                        
                        print(f"🔍 DEBUG: Manual application request - will attempt to apply to all jobs")
                        print(f"🔍 DEBUG: Apply to external sites: {apply_to_external}")
                        
                        for job_id in job_ids:
                            print(f"🔍 DEBUG: Processing job_id = {job_id}")
                            # Get job from database
                            job = JobPosting.query.get(job_id)
                            print(f"🔍 DEBUG: Found job in database: {job.title if job else 'None'}")
                            print(f"🔍 DEBUG: Job status: {job.application_status if job else 'N/A'}")
                            
                            if job and job.application_status == 'not_applied':
                                # Check if this is a search redirect
                                if "View on Indeed" in job.title or "Multiple Companies" in job.company:
                                    print(f"🔍 DEBUG: Job {job_id} is a search redirect")
                                    job.application_status = 'failed'
                                    job.applied_date = datetime.utcnow()
                                    job.application_notes = 'Search redirect - click "View on Platform" to see jobs'
                                    failed_count += 1
                                else:
                                    print(f"🔍 DEBUG: Manual application request - attempting to apply to job {job_id}")
                                    
                                    # Check if external application is allowed
                                    is_external = job.url and not any(domain in job.url for domain in ['linkedin.com', 'indeed.com', 'glassdoor.com'])
                                    
                                    if is_external and not apply_to_external:
                                        print(f"🔍 DEBUG: Job {job_id} is external and external applications disabled")
                                        job.application_status = 'failed'
                                        job.applied_date = datetime.utcnow()
                                        job.application_notes = 'External application - disabled in preferences'
                                        failed_count += 1
                                    else:
                                        # Attempt actual application
                                        success = attempt_auto_application(job)
                                        if success:
                                            print(f"🔍 DEBUG: Successfully applied to job {job_id}")
                                            job.application_status = 'applied'
                                            job.applied_date = datetime.utcnow()
                                            job.status_changed_date = datetime.utcnow()
                                            job.application_notes = 'Applied successfully'
                                            applied_count += 1
                                        else:
                                            print(f"🔍 DEBUG: Application failed for job {job_id}")
                                            job.application_status = 'failed'
                                            job.applied_date = datetime.utcnow()
                                            job.status_changed_date = datetime.utcnow()
                                            job.application_notes = 'Application failed - may require manual application'
                                            failed_count += 1
                                
                                print(f"🔍 DEBUG: Committing changes for job {job_id}")
                                db.session.commit()
                                print(f"🔍 DEBUG: Successfully updated job {job_id} status to {job.application_status}")
                            else:
                                print(f"🔍 DEBUG: Skipping job {job_id} - either not found or already applied/failed")
                        
                        total_processed = applied_count + failed_count
                        print(f"🔍 DEBUG: Final counts - applied: {applied_count}, failed: {failed_count}, total: {total_processed}")
                        
                        if applied_count > 0:
                            message = f'Applied to {applied_count} job(s), {failed_count} require manual application.'
                            print(f"🔍 DEBUG: Emitting success status: {message}")
                            socketio.emit('application_status', {
                                'status': 'completed',
                                'message': message,
                                'applied_count': applied_count,
                                'failed_count': failed_count
                            })
                        else:
                            message = f'Processed {total_processed} job(s). All require manual application via "View on Platform".'
                            print(f"🔍 DEBUG: Emitting manual application status: {message}")
                            socketio.emit('application_status', {
                                'status': 'completed',
                                'message': message,
                                'failed_count': failed_count
                            })
                            
                    except Exception as e:
                        print(f"🔍 DEBUG: Exception in background thread: {str(e)}")
                        socketio.emit('application_status', {
                            'status': 'error',
                            'message': f'Application failed: {str(e)}'
                        })
                        
            def attempt_auto_application(job):
                """Attempt to automatically apply to a job using browser automation."""
                try:
                    print(f"🚀 REAL APPLICATION: Attempting to apply for {job.title} at {job.company}")
                    
                    # Import browser automation
                    from browser_automation import BrowserAutomator
                    
                    # Create browser automator instance
                    automator = BrowserAutomator()
                    
                    # Apply to the job
                    success = automator.apply_to_job(job.url, job.job_board)
                    
                    if success:
                        print(f"✅ REAL APPLICATION: Successfully applied to {job.title}")
                        return True
                    else:
                        print(f"❌ REAL APPLICATION: Failed to apply to {job.title}")
                        return False
                        
                except Exception as e:
                    print(f"🔍 DEBUG: Exception in real auto-application: {str(e)}")
                    return False
        else:
            # General job application not supported in web-app-only mode
            # Use "Apply Now" buttons on individual jobs instead
            def apply_jobs_background():
                with app.app_context():
                    socketio.emit('application_status', {
                        'status': 'error',
                        'message': 'General job application not supported. Use "Apply Now" buttons on individual jobs instead.'
                    })
        
        if job_ids:
            thread = threading.Thread(target=apply_specific_jobs_background)
        else:
            thread = threading.Thread(target=apply_jobs_background)
        
        thread.start()
        
        return jsonify({'status': 'success', 'message': 'Job applications started'})
    
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/job_stats')
def api_job_stats():
    """API endpoint to get job statistics"""
    try:
        total_jobs = JobPosting.query.count()
        applied_jobs = JobPosting.query.filter_by(application_status='applied').count()
        failed_jobs = JobPosting.query.filter_by(application_status='failed').count()
        pending_jobs = JobPosting.query.filter_by(application_status='not_applied').count()
        
        return jsonify({
            'total_jobs': total_jobs,
            'applied_jobs': applied_jobs,
            'failed_jobs': failed_jobs,
            'pending_jobs': pending_jobs
        })
    
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/job_details/<int:job_id>')
def api_job_details(job_id):
    """API endpoint to get job details"""
    try:
        job = JobPosting.query.get_or_404(job_id)
        return jsonify(job.to_dict())
    
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/jobs/<int:job_id>', methods=['DELETE'])
def api_delete_job(job_id):
    """API endpoint to delete a job posting"""
    try:
        job = JobPosting.query.get_or_404(job_id)
        job_title = job.title
        job_company = job.company
        
        db.session.delete(job)
        db.session.commit()
        
        return jsonify({
            'status': 'success', 
            'message': f'Successfully deleted job: {job_title} at {job_company}'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/jobs/<int:job_id>/mark-applied', methods=['POST'])
def api_mark_job_applied(job_id):
    """API endpoint to mark a job as manually applied"""
    try:
        job = JobPosting.query.get_or_404(job_id)
        job_title = job.title
        job_company = job.company
        
        # Update job status to applied
        job.application_status = 'applied'
        job.applied_date = datetime.utcnow()
        job.status_changed_date = datetime.utcnow()  # Record when status was changed
        
        db.session.commit()
        
        return jsonify({
            'status': 'success', 
            'message': f'Successfully marked as applied: {job_title} at {job_company}'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/jobs/bulk-delete', methods=['POST'])
def api_bulk_delete_jobs():
    """API endpoint to delete multiple job postings"""
    try:
        data = request.get_json()
        job_ids = data.get('job_ids', [])
        
        if not job_ids:
            return jsonify({'status': 'error', 'message': 'No job IDs provided'}), 400
        
        # Delete jobs
        deleted_count = 0
        for job_id in job_ids:
            job = JobPosting.query.get(job_id)
            if job:
                db.session.delete(job)
                deleted_count += 1
        
        db.session.commit()
        
        return jsonify({
            'status': 'success', 
            'message': f'Successfully deleted {deleted_count} job(s)',
            'deleted_count': deleted_count
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/preferences')
def api_get_preferences():
    """API endpoint to get current job preferences"""
    try:
        prefs = JobPreferences.query.first()
        if not prefs:
            return jsonify({})
        
        return jsonify({
            'keywords': json.loads(prefs.keywords) if prefs.keywords else [],
            'locations': json.loads(prefs.locations) if prefs.locations else [],
            'experience_levels': json.loads(prefs.experience_levels) if prefs.experience_levels else [],
            'job_types': json.loads(prefs.job_types) if prefs.job_types else [],
            'date_posted': prefs.date_posted,
            'salary_min': prefs.salary_min,
            'job_search_limit': prefs.job_search_limit,
            'auto_apply_enabled': prefs.auto_apply_enabled,
            'apply_to_external_sites': prefs.apply_to_external_sites
        })
    
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/jobs/<int:job_id>/notes', methods=['POST'])
def api_update_job_notes(job_id):
    """API endpoint to update job notes"""
    try:
        data = request.get_json()
        job = JobPosting.query.get_or_404(job_id)
        
        # Update notes
        job.application_notes = data.get('application_notes', '')
        job.recruiter_notes = data.get('recruiter_notes', '')
        
        db.session.commit()
        
        return jsonify({
            'status': 'success', 
            'message': 'Notes updated successfully'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/reclassify-indeed-jobs', methods=['POST'])
def api_reclassify_indeed_jobs():
    """API endpoint to reclassify existing Indeed jobs"""
    try:
        # Get all Indeed jobs that are currently marked as having easy apply
        indeed_jobs = JobPosting.query.filter(
            JobPosting.job_board == 'indeed',
            JobPosting.has_easy_apply == True
        ).all()
        
        reclassified_count = 0
        external_indicators = [
            'Apply on company site',
            'Apply on employer site',
            'Apply on company website', 
            'Apply directly',
            'Visit employer site',
            'Employer site',
            'Company site',
            'External site',
            'Redirects to company site',
            'Apply at company',
            'Visit company website'
        ]
        
        for job in indeed_jobs:
            # Check if description contains external application indicators
            description_text = (job.description or '').lower()
            title_text = (job.title or '').lower()
            
            should_be_manual = False
            for indicator in external_indicators:
                if indicator.lower() in description_text or indicator.lower() in title_text:
                    should_be_manual = True
                    break
            
            if should_be_manual:
                job.has_easy_apply = False
                reclassified_count += 1
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': f'Reclassified {reclassified_count} Indeed jobs from quick apply to manual apply',
            'reclassified_count': reclassified_count
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    print(f"🚀 Starting Flask app with SocketIO on http://0.0.0.0:5002/")
    socketio.run(app, debug=True, host='0.0.0.0', port=5002, allow_unsafe_werkzeug=True)
