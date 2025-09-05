# Job Application Bot - Web Interface

A modern web-based interface for the Job Application Bot with PostgreSQL database storage.

## 🌟 Features

### Web Interface
- **📊 Interactive Dashboard**: Real-time statistics and job tracking
- **🔍 Advanced Job Search**: Filter and manage job postings
- **⚙️ Preferences Configuration**: Customize search criteria and application settings
- **📈 Visual Analytics**: Charts and graphs showing application progress
- **📱 Responsive Design**: Works on desktop, tablet, and mobile devices

### Backend Features
- **🐘 PostgreSQL Database**: Scalable and reliable data storage
- **🔄 Real-time Updates**: Live status updates and notifications
- **🤖 Automated Applications**: Background job application processing
- **🔐 Google OAuth**: Secure Indeed login integration
- **⚡ Rate Limiting**: Intelligent request throttling

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- PostgreSQL 12+
- Chrome browser (for automation)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Up PostgreSQL Database
```bash
# Start PostgreSQL (varies by system)
# macOS with Homebrew:
brew services start postgresql

# Create database
createdb job_application_bot

# Or use the automated setup:
python setup_database.py
```

### 3. Configure Environment
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your settings:
DATABASE_URL=postgresql://username:password@localhost/job_application_bot
SECRET_KEY=your-secret-key-here
LINKEDIN_EMAIL=your.email@example.com
LINKEDIN_PASSWORD=your_password_here
```

### 4. Run the Web Application
```bash
python app.py
```

Visit http://localhost:5000 in your browser!

## 📖 Detailed Setup Guide

### Database Configuration

#### Option 1: Automatic Setup
```bash
python setup_database.py
```

#### Option 2: Manual Setup
```bash
# Create database
createdb job_application_bot

# Run the Flask app to create tables
python -c "from app import app, db; app.app_context().push(); db.create_all()"
```

#### Option 3: Using Docker
```bash
# Start PostgreSQL with Docker
docker run --name job-app-postgres -e POSTGRES_DB=job_application_bot -e POSTGRES_USER=jobbot -e POSTGRES_PASSWORD=password -p 5432:5432 -d postgres:14

# Update your DATABASE_URL
export DATABASE_URL=postgresql://jobbot:password@localhost/job_application_bot
```

### Environment Variables

Create a `.env` file with the following variables:

```env
# Database
DATABASE_URL=postgresql://username:password@localhost/job_application_bot

# Flask
SECRET_KEY=your-super-secret-key-change-this-in-production
FLASK_ENV=development

# LinkedIn (optional - for automated applications)
LINKEDIN_EMAIL=your.email@example.com
LINKEDIN_PASSWORD=your_password_here

# Indeed uses Google OAuth - no credentials needed

# Application Settings
DEBUG=True
```

## 🎯 Using the Web Interface

### Dashboard
- View real-time statistics of your job applications
- See recent job postings and their status
- Quick access to search and apply functions
- Visual charts showing progress and trends

### Job Search & Management
- **Search Jobs**: Find new opportunities across LinkedIn, Indeed, and Glassdoor
- **Filter Results**: Filter by status, platform, keywords, and more
- **Bulk Actions**: Apply to multiple jobs at once
- **Job Details**: View complete job information and descriptions

### Preferences Configuration
- **Search Criteria**: Set keywords, locations, experience levels
- **Application Settings**: Configure daily limits and auto-apply options
- **Exclusion Filters**: Specify keywords to avoid
- **Salary Requirements**: Set minimum salary expectations

## 🔧 API Endpoints

The web interface provides several API endpoints for integration:

### Job Management
- `POST /api/search_jobs` - Start job search process
- `POST /api/apply_jobs` - Apply to selected jobs
- `GET /api/job_stats` - Get current job statistics

### Example API Usage
```javascript
// Search for jobs
fetch('/api/search_jobs', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        job_boards: ['linkedin', 'indeed', 'glassdoor']
    })
});

// Apply to jobs
fetch('/api/apply_jobs', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        max_applications: 5
    })
});
```

## 🎨 Customization

### Themes and Styling
The interface uses Bootstrap 5 with custom CSS. Modify `app/static/css/style.css` to customize:
- Colors and branding
- Layout and spacing
- Component styling
- Responsive breakpoints

### Adding New Features
1. Create new routes in `app.py`
2. Add corresponding templates in `app/templates/`
3. Update navigation in `base.html`
4. Add any required JavaScript in `app/static/js/main.js`

## 🔒 Security Considerations

### Production Deployment
- Change the `SECRET_KEY` to a secure random value
- Use environment variables for all sensitive data
- Enable SSL/HTTPS
- Configure proper database permissions
- Use a reverse proxy (nginx/Apache)

### Database Security
- Use strong database passwords
- Limit database user permissions
- Enable SSL for database connections
- Regular backups and security updates

## 📊 Database Schema

### Main Tables
- **job_postings**: Job listing information and application status
- **job_preferences**: User search and application preferences
- **application_logs**: Detailed logs of application attempts

### Key Relationships
```sql
job_postings (1) -> (many) application_logs
job_preferences (1) -> (1) user_settings
```

## 🐛 Troubleshooting

### Common Issues

#### Database Connection Errors
```bash
# Check PostgreSQL is running
pg_isready

# Test connection
psql postgresql://username:password@localhost/job_application_bot
```

#### Port Already in Use
```bash
# Find process using port 5000
lsof -i :5000

# Kill process if needed
kill -9 <PID>
```

#### Template Not Found Errors
- Ensure templates are in `app/templates/`
- Check Flask app initialization includes template folder

#### Static Files Not Loading
- Verify static files are in `app/static/`
- Check Flask static folder configuration
- Clear browser cache

### Logging and Debugging

Enable detailed logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Check application logs for detailed error information.

## 🚀 Deployment

### Production Deployment with Gunicorn
```bash
# Install Gunicorn
pip install gunicorn

# Run with Gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Docker Deployment
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 5000

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

### Environment-Specific Configuration
- Development: Use SQLite for testing
- Staging: Use PostgreSQL with test data
- Production: Use managed PostgreSQL service

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- Check the troubleshooting section above
- Review the logs for error details
- Ensure all dependencies are installed correctly
- Verify PostgreSQL is running and accessible

---

**Happy Job Hunting! 🎯**
