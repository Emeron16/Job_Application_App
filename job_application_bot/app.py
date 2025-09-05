"""
Flask Web Application for Job Application Bot
"""

import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
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
    prefs.salary_min = int(request.form.get('salary_min', 0)) or None
    prefs.date_posted = request.form.get('date_posted', 'week')
    prefs.daily_application_limit = int(request.form.get('daily_application_limit', 10))
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
        
        # Convert string names to JobBoard enums
        board_enums = []
        for board in job_boards:
            if board == 'linkedin':
                board_enums.append(JobBoard.LINKEDIN)
            elif board == 'indeed':
                board_enums.append(JobBoard.INDEED)
            elif board == 'glassdoor':
                board_enums.append(JobBoard.GLASSDOOR)
        
        # Run job search in background thread
        def search_jobs_background():
            bot = get_bot()
            bot.search_jobs(board_enums)
        
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
        max_applications = data.get('max_applications', 10)
        
        # Run applications in background thread
        def apply_jobs_background():
            bot = get_bot()
            bot.apply_to_jobs(max_applications)
        
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

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)
