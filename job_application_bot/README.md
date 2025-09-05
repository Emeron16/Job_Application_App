# Job Application Automation Bot

An automated system for searching and applying to job postings across multiple job boards (LinkedIn, Indeed, and Glassdoor).

## Features

- 🔍 **Multi-platform Job Search**: Search across LinkedIn, Indeed, and Glassdoor
- 📊 **Excel/Spreadsheet Integration**: Store job data in local Excel file (Job update.xlsx) with automatic updates when applications are submitted
- 🤖 **Automated Applications**: Submit applications with resume and cover letter
- ⚡ **Rate Limiting**: Intelligent rate limiting to avoid being blocked
- 🛡️ **Enhanced Security**: Google OAuth for Indeed login, secure credential storage
- 📝 **Comprehensive Logging**: Track all activities and application attempts
- 🎯 **Configurable Filters**: Customize search keywords, locations, and criteria
- 📈 **Statistics & Reporting**: Track application success rates and job statistics
- 🔐 **Google OAuth Integration**: Use Google login for Indeed authentication

## Installation

1. **Clone or download the project**
   ```bash
   cd job_application_bot
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Setup environment variables**
   ```bash
   cp .env.example .env
   # Edit .env file with your credentials
   ```

4. **Create necessary directories**
   ```bash
   mkdir -p documents credentials data logs
   ```

## Configuration

### 1. Environment Variables (.env)

```env
LINKEDIN_EMAIL=your.email@example.com
LINKEDIN_PASSWORD=your_password_here
# Indeed now uses Google OAuth login - no email/password needed
GOOGLE_CREDENTIALS_PATH=credentials/google_credentials.json
```

**Note**: Indeed authentication now uses Google OAuth. Make sure you're logged into your Google account in the browser, and the bot will use the "Login with Google" button on Indeed's sign-in page. **No Google API credentials file is needed** for this - it just uses your browser's saved Google login.

### 2. Documents

Place your documents in the `documents/` folder:
- `documents/resume.pdf` - Your resume file
- `documents/cover_letter.txt` - Your cover letter template

### 3. Job Application Tracking

The bot now automatically creates and updates an Excel file at `documents/Job update.xlsx` to track all job applications. This file includes the following columns:

- **title**: Job title
- **company**: Company name  
- **time_applied**: When the application was submitted
- **location**: Job location
- **description**: Job description
- **salary**: Salary range
- **experience**: Required experience level
- **job_type**: Full-time, contract, etc.
- **job_board**: Which platform (LinkedIn, Indeed, Glassdoor)
- **url**: Link to the job posting
- **application_status**: Current status (not_applied, applied, failed)

The file is automatically created if it doesn't exist and updated each time you run the bot.

### 4. Google Sheets Setup (Optional - Legacy)

**Note**: This is completely separate from the Google OAuth login for Indeed. Google Sheets requires API credentials, while Indeed login just uses your browser's Google session.

If you prefer Google Sheets integration (not recommended with new Excel system):

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable Google Sheets API and Google Drive API
4. Create a service account and download JSON credentials
5. Save credentials as `credentials/google_credentials.json`
6. Create a Google Sheet and share it with the service account email
7. Copy the Google Sheets ID from the URL

### 5. Configuration File

The bot will create a `config.json` file with default settings. You can customize:

```json
{
  "job_search": {
    "keywords": ["software engineer", "python developer"],
    "locations": ["Remote","Hybrid", "San Francisco", "New York"],
    "experience_levels": ["entry", "mid", "senior"],
    "job_types": ["full-time", "contract"],
    "exclude_keywords": [],
    "salary_min": null,
    "date_posted": "week"
  },
  "application": {
    "resume_path": "documents/resume.pdf",
    "cover_letter_path": "documents/cover_letter.txt",
    "daily_application_limit": 10,
    "auto_apply_enabled": false,
    "apply_to_external_sites": false
  },
  "rate_limit": {
    "requests_per_minute": 30,
    "requests_per_hour": 100,
    "retry_attempts": 3,
    "retry_delay_base": 1.0,
    "request_timeout": 30,
    "cooldown_period": 300
  },
  "storage": {
    "use_google_sheets": true,
    "google_sheets_id": null,
    "local_storage_path": "data/job_postings.json",
    "log_file_path": "logs/application_log.txt"
  }
}
```

## Usage

### Command Line Interface

1. **Search for jobs only**
   ```bash
   python main.py search
   python main.py search --boards linkedin indeed
   ```

2. **Apply to found jobs**
   ```bash
   python main.py apply --dry-run  # See what would be applied to
   python main.py apply --max-applications 5
   ```

3. **Run full cycle (search + apply)**
   ```bash
   python main.py run
   python main.py run --boards linkedin --max-applications 3
   ```

4. **View statistics**
   ```bash
   python main.py stats
   ```

5. **Validate configuration**
   ```bash
   python main.py validate
   ```

6. **Export data to CSV**
   ```bash
   python main.py export --output my_jobs.csv
   ```

### Python API

```python
from main import JobApplicationBot

# Initialize bot
bot = JobApplicationBot('config.json')

# Search for jobs
jobs = bot.search_jobs()

# Apply to jobs
results = bot.apply_to_jobs(max_applications=5)

# Run full cycle
bot.run_full_cycle()

# Get statistics
stats = bot.get_job_statistics()
```

## Safety Features

- **Rate Limiting**: Prevents overwhelming job boards with requests
- **Daily Limits**: Configurable daily application limits
- **Duplicate Detection**: Automatically removes duplicate job postings
- **Error Handling**: Comprehensive error handling and retry mechanisms
- **Dry Run Mode**: Test applications without actually submitting
- **Manual Override**: Disable auto-apply for manual review

## Important Notes

### Legal and Ethical Considerations

- **Terms of Service**: Ensure your usage complies with each job board's terms of service
- **Rate Limits**: The bot includes rate limiting, but be respectful of platform resources
- **Account Safety**: Use at your own risk - automated interactions may violate ToS
- **Manual Review**: Always review job postings before applying

### Security

- **Credentials**: Never commit credentials to version control
- **Environment Variables**: Store sensitive data in environment variables
- **2FA**: Some platforms may require manual intervention for 2FA

### Limitations

- **Anti-bot Measures**: Job boards have sophisticated anti-bot detection
- **CAPTCHA**: Manual intervention may be required for CAPTCHAs
- **External Applications**: Many jobs redirect to external sites for applications
- **Platform Changes**: Job board layouts change frequently, requiring updates

## Troubleshooting

### Common Issues

1. **Chrome Driver Issues**
   ```bash
   # Reinstall webdriver manager
   pip install --upgrade webdriver-manager
   ```

2. **Google Sheets Authentication**
   - Verify service account has access to the sheet
   - Check credentials file path and format
   - Ensure APIs are enabled in Google Cloud Console

3. **Login Failures**
   - Check credentials in .env file
   - Verify account isn't locked or requiring 2FA
   - Check for platform-specific security requirements

4. **Job Search Failures**
   - Platform may have changed their layout
   - Rate limits may have been exceeded
   - Network connectivity issues

### Logging

All activities are logged to `logs/application_log.txt`. Check this file for detailed error information.

## Development

### Project Structure

```
job_application_bot/
├── main.py                    # Main CLI application
├── config.py                  # Configuration management
├── models.py                  # Data models
├── job_searchers.py          # Job board search implementations
├── application_automation.py  # Application automation
├── storage.py                # Data storage (local/Google Sheets)
├── utils.py                  # Utility functions
├── requirements.txt          # Python dependencies
├── .env.example             # Environment variables template
└── README.md               # This file
```

### Contributing

1. Follow existing code style and patterns
2. Add tests for new functionality
3. Update documentation for any changes
4. Ensure compatibility with rate limiting and security features

## Disclaimer

This tool is for educational and personal use only. Users are responsible for:
- Complying with job board terms of service
- Respecting rate limits and platform policies
- Ensuring the accuracy of application information
- Following applicable laws and regulations

The authors are not responsible for any consequences of using this tool, including but not limited to account suspensions, rate limiting, or other platform restrictions.
