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

from main import JobApplicationBot
from models import JobBoard, ApplicationStatus

# Initialize Flask app
app = Flask(__name__, template_folder='app/templates', static_folder='app/static')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Database configuration
database_url = os.environ.get('DATABASE_URL', 'postgresql://localhost/job_application_bot')
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)
socketio = SocketIO(app, cors_allowed_origins="*")

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
    application_status = db.Column(db.String(50), default='not_applied')
    applied_date = db.Column(db.DateTime)
    application_notes = db.Column(db.Text)
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
            'application_status': self.application_status,
            'applied_date': self.applied_date.isoformat() if self.applied_date else None,
            'application_notes': self.application_notes,
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
    daily_application_limit = db.Column(db.Integer, default=10)
    job_search_limit = db.Column(db.Integer, default=20)
    auto_apply_enabled = db.Column(db.Boolean, default=False)
    apply_to_external_sites = db.Column(db.Boolean, default=False)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    updated_date = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Global bot instance
bot_instance = None

def get_bot():
    global bot_instance
    if bot_instance is None:
        bot_instance = JobApplicationBot()
    return bot_instance

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
    search_query = request.args.get('search', '')
    
    # Build query
    query = JobPosting.query
    
    if status_filter != 'all':
        query = query.filter_by(application_status=status_filter)
    
    if board_filter != 'all':
        query = query.filter_by(job_board=board_filter)
    
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
    prefs.keywords = json.dumps(request.form.getlist('keywords'))
    prefs.locations = json.dumps(request.form.getlist('locations'))
    prefs.experience_levels = json.dumps(request.form.getlist('experience_levels'))
    prefs.job_types = json.dumps(request.form.getlist('job_types'))
    prefs.exclude_keywords = json.dumps(request.form.getlist('exclude_keywords'))
    
    # Handle salary_min - convert to int if not empty, otherwise None
    salary_min_value = request.form.get('salary_min', '').strip()
    prefs.salary_min = int(salary_min_value) if salary_min_value else None
    
    prefs.date_posted = request.form.get('date_posted', 'week')
    prefs.daily_application_limit = int(request.form.get('daily_application_limit', 10))
    prefs.job_search_limit = int(request.form.get('job_search_limit', 20))
    prefs.auto_apply_enabled = 'auto_apply_enabled' in request.form
    prefs.apply_to_external_sites = 'apply_to_external_sites' in request.form
    prefs.updated_date = datetime.utcnow()
    
    db.session.commit()
    flash('Preferences updated successfully!', 'success')
    return redirect(url_for('preferences'))

@app.route('/api/search_jobs', methods=['POST'])
def api_search_jobs():
    """API endpoint to search for new jobs"""
    try:
        data = request.get_json()
        job_boards = data.get('job_boards', ['linkedin', 'indeed', 'glassdoor'])
        
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
            try:
                socketio.emit('search_status', {'status': 'started', 'message': 'Job search started...'})
                
                def progress_callback(data):
                    socketio.emit('search_status', data)
                
                bot = get_bot()
                # Pass job limit and progress callback to the search function
                jobs = bot.search_jobs_with_limit(board_enums, job_limit, progress_callback)
                
                socketio.emit('search_status', {
                    'status': 'completed', 
                    'message': f'Search completed! Found {len(jobs)} jobs.',
                    'jobs_count': len(jobs)
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
                        
                        # Get current preferences to check auto-apply settings
                        prefs = JobPreferences.query.first()
                        auto_apply_enabled = prefs.auto_apply_enabled if prefs else False
                        apply_to_external = prefs.apply_to_external_sites if prefs else False
                        
                        print(f"🔍 DEBUG: Auto-apply enabled: {auto_apply_enabled}")
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
                                elif auto_apply_enabled:
                                    print(f"🔍 DEBUG: Auto-apply enabled - attempting to apply to job {job_id}")
                                    
                                    # Check if external application is allowed
                                    is_external = job.url and not any(domain in job.url for domain in ['linkedin.com', 'indeed.com', 'glassdoor.com'])
                                    
                                    if is_external and not apply_to_external:
                                        print(f"🔍 DEBUG: Job {job_id} is external and external applications disabled")
                                        job.application_status = 'failed'
                                        job.applied_date = datetime.utcnow()
                                        job.application_notes = 'External application - disabled in preferences'
                                        failed_count += 1
                                    else:
                                        # Attempt actual auto-application
                                        success = attempt_auto_application(job)
                                        if success:
                                            print(f"🔍 DEBUG: Successfully applied to job {job_id}")
                                            job.application_status = 'applied'
                                            job.applied_date = datetime.utcnow()
                                            job.application_notes = 'Auto-applied successfully'
                                            applied_count += 1
                                        else:
                                            print(f"🔍 DEBUG: Auto-application failed for job {job_id}")
                                            job.application_status = 'failed'
                                            job.applied_date = datetime.utcnow()
                                            job.application_notes = 'Auto-application failed - requires manual application'
                                            failed_count += 1
                                else:
                                    print(f"🔍 DEBUG: Auto-apply disabled - marking job {job_id} for manual application")
                                    job.application_status = 'ready_to_apply'  # Better status name
                                    job.applied_date = datetime.utcnow()
                                    job.application_notes = 'Ready for manual application - click "View on Platform"'
                                    failed_count += 1  # Count as failed for now, but with better messaging
                                
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
            # Apply to jobs generally
            def apply_jobs_background():
                with app.app_context():  # Fix: Add Flask application context
                    bot = get_bot()
                    bot.apply_to_jobs(max_applications)
        
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

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True, host='0.0.0.0', port=5002)
