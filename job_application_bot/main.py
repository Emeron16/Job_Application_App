"""Main application orchestrator for the job application automation system."""

import os
import sys
import time
from datetime import datetime
from typing import List, Optional
import click
from colorama import init, Fore, Style

# Initialize colorama for cross-platform colored output
init()

from config import Config
from models import JobPosting, JobBoard, ApplicationStatus
from job_searchers import JobSearchManager
from application_automation import ApplicationManager
from storage import StorageManager
from flask_storage import FlaskDatabaseStorage
from utils import Logger, RateLimiter


class JobApplicationBot:
    """Main orchestrator for the job application automation system."""
    
    def __init__(self, config_path: str = "config.json"):
        # Load configuration
        self.config = Config.load_from_file(config_path)
        
        # Initialize components
        self.logger = Logger(
            log_file=self.config.storage.log_file_path,
            level="INFO"
        )
        
        self.rate_limiter = RateLimiter(
            requests_per_minute=self.config.rate_limit.requests_per_minute,
            requests_per_hour=self.config.rate_limit.requests_per_hour
        )
        
        self.search_manager = JobSearchManager(self.rate_limiter, self.logger)
        self.application_manager = ApplicationManager(self.config, self.logger, self.rate_limiter)
        
        # Use Flask database storage for web integration
        self.storage_manager = FlaskDatabaseStorage(self.logger)
        
        self.logger.info("Job Application Bot initialized successfully")
    
    def validate_configuration(self) -> bool:
        """Validate the configuration and return True if valid."""
        errors = self.config.validate()
        
        if errors:
            self.logger.error("Configuration validation failed:")
            for error in errors:
                self.logger.error(f"  - {error}")
            return False
        
        self.logger.info("Configuration validation passed")
        return True
    
    def search_jobs(self, job_boards: Optional[List[JobBoard]] = None) -> List[JobPosting]:
        """Search for jobs across specified job boards."""
        self.logger.info("Starting job search...")
        
        if job_boards is None:
            job_boards = [JobBoard.LINKEDIN, JobBoard.INDEED, JobBoard.GLASSDOOR]
        
        # Search for jobs
        search_results = self.search_manager.search_all_boards(
            keywords=self.config.job_search.keywords,
            locations=self.config.job_search.locations,
            job_boards=job_boards
        )
        
        # Collect all found jobs
        all_jobs = []
        for result in search_results:
            all_jobs.extend(result.jobs_found)
            
            if result.errors:
                for error in result.errors:
                    self.logger.error(f"Search error on {result.job_board.value}: {error}")
        
        # Remove duplicates
        unique_jobs = self.search_manager.deduplicate_jobs(all_jobs)
        
        self.logger.info(f"Found {len(unique_jobs)} unique job postings")
        
        # Save jobs to storage
        if unique_jobs:
            self.storage_manager.save_jobs(unique_jobs)
        
        return unique_jobs
    
    def search_jobs_with_limit(self, job_boards: Optional[List[JobBoard]] = None, job_limit: int = 20, progress_callback=None) -> List[JobPosting]:
        """Search for jobs across specified job boards with a specific limit."""
        self.logger.info(f"Starting job search with limit of {job_limit} jobs per board...")
        
        if job_boards is None:
            job_boards = [JobBoard.LINKEDIN, JobBoard.INDEED, JobBoard.GLASSDOOR]
        
        # Search for jobs with limit
        search_results = self.search_manager.search_all_boards_with_limit(
            keywords=self.config.job_search.keywords,
            locations=self.config.job_search.locations,
            job_boards=job_boards,
            job_limit=job_limit,
            progress_callback=progress_callback
        )
        
        # Collect all found jobs and emit individual job events with global limit
        all_jobs = []
        jobs_found_count = 0
        
        for result in search_results:
            # Apply global limit
            jobs_to_add = result.jobs_found
            if jobs_found_count + len(jobs_to_add) > job_limit:
                jobs_to_add = jobs_to_add[:job_limit - jobs_found_count]
            
            all_jobs.extend(jobs_to_add)
            jobs_found_count += len(jobs_to_add)
            
            # Emit progress for each result
            if progress_callback and jobs_to_add:
                progress_callback({
                    'status': 'progress',
                    'message': f'Found {len(jobs_to_add)} jobs on {result.job_board.value}',
                    'jobs_count': jobs_found_count,
                    'board': result.job_board.value
                })
                
                # Emit individual job events for live display
                for job in jobs_to_add:
                    progress_callback({
                        'status': 'job_found',
                        'job': job.to_dict(),
                        'total_found': jobs_found_count
                    })
            
            if result.errors:
                for error in result.errors:
                    self.logger.error(f"Search error on {result.job_board.value}: {error}")
            
            # Stop if we've reached the global limit
            if jobs_found_count >= job_limit:
                self.logger.info(f"Reached global job limit of {job_limit}, stopping search")
                break
        
        # Remove duplicates
        unique_jobs = self.search_manager.deduplicate_jobs(all_jobs)
        
        self.logger.info(f"Found {len(unique_jobs)} unique job postings")
        
        # Save jobs to storage
        if unique_jobs:
            self.storage_manager.save_jobs(unique_jobs)
        
        return unique_jobs
    
    def apply_to_jobs(self, max_applications: Optional[int] = None) -> List:
        """Apply to unapplied jobs."""
        self.logger.info("Starting job application process...")
        
        # Get unapplied jobs
        unapplied_jobs = self.storage_manager.get_unapplied_jobs()
        
        if not unapplied_jobs:
            self.logger.info("No unapplied jobs found")
            return []
        
        # Limit number of applications if specified
        if max_applications:
            unapplied_jobs = unapplied_jobs[:max_applications]
        
        self.logger.info(f"Attempting to apply to {len(unapplied_jobs)} jobs")
        
        # Apply to jobs
        results = self.application_manager.apply_to_jobs(unapplied_jobs)
        
        # Update job statuses and log results
        for result in results:
            status = ApplicationStatus.APPLIED if result.success else ApplicationStatus.FAILED
            
            self.storage_manager.update_job_status(
                job_id=result.job_posting.job_id,
                status=status,
                applied_date=result.timestamp if result.success else None,
                notes=result.message
            )
            
            # Log application attempt
            self.storage_manager.log_application(result)
            self.logger.log_application(
                job_title=result.job_posting.title,
                company=result.job_posting.company,
                success=result.success,
                message=result.message
            )
        
        # Generate and log report
        report = self.application_manager.generate_application_report(results)
        self.logger.info(f"Application session completed: {report['successful_applications']}/{report['total_applications']} successful")
        
        return results
    
    def run_full_cycle(self, job_boards: Optional[List[JobBoard]] = None, 
                      max_applications: Optional[int] = None):
        """Run a complete search and apply cycle."""
        self.logger.info("Starting full job application cycle")
        
        # Validate configuration
        if not self.validate_configuration():
            self.logger.error("Configuration validation failed. Aborting.")
            return False
        
        try:
            # Search for jobs
            new_jobs = self.search_jobs(job_boards)
            
            if not new_jobs:
                self.logger.info("No new jobs found")
                return True
            
            # Apply to jobs if auto-apply is enabled
            if self.config.application.auto_apply_enabled:
                self.apply_to_jobs(max_applications)
            else:
                self.logger.info("Auto-apply disabled. Jobs saved for manual review.")
            
            self.logger.info("Full cycle completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error during full cycle: {e}")
            return False
    
    def get_job_statistics(self) -> dict:
        """Get statistics about stored jobs."""
        jobs = self.storage_manager.load_jobs()
        
        if not jobs:
            return {"total_jobs": 0}
        
        stats = {
            "total_jobs": len(jobs),
            "by_status": {},
            "by_job_board": {},
            "by_company": {},
            "recent_jobs": 0
        }
        
        # Count by status
        for job in jobs:
            status = job.application_status.value
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
        
        # Count by job board
        for job in jobs:
            board = job.job_board.value
            stats["by_job_board"][board] = stats["by_job_board"].get(board, 0) + 1
        
        # Count by company
        for job in jobs:
            company = job.company
            stats["by_company"][company] = stats["by_company"].get(company, 0) + 1
        
        # Count recent jobs (last 7 days)
        from datetime import timedelta
        recent_cutoff = datetime.now() - timedelta(days=7)
        stats["recent_jobs"] = sum(1 for job in jobs if job.scraped_date >= recent_cutoff)
        
        return stats


# CLI Interface
@click.group()
@click.option('--config', default='config.json', help='Path to configuration file')
@click.pass_context
def cli(ctx, config):
    """Job Application Automation Bot"""
    ctx.ensure_object(dict)
    ctx.obj['config_path'] = config


@cli.command()
@click.option('--boards', multiple=True, type=click.Choice(['linkedin', 'indeed', 'glassdoor']), 
              help='Job boards to search (default: all)')
@click.pass_context
def search(ctx, boards):
    """Search for job postings"""
    click.echo(f"{Fore.GREEN}🔍 Searching for jobs...{Style.RESET_ALL}")
    
    bot = JobApplicationBot(ctx.obj['config_path'])
    
    # Convert board names to JobBoard enums
    job_boards = None
    if boards:
        job_boards = [JobBoard(board) for board in boards]
    
    jobs = bot.search_jobs(job_boards)
    
    click.echo(f"{Fore.GREEN}✅ Found {len(jobs)} unique job postings{Style.RESET_ALL}")
    
    # Display sample jobs
    if jobs:
        click.echo(f"\n{Fore.CYAN}Sample jobs found:{Style.RESET_ALL}")
        for job in jobs[:5]:
            click.echo(f"  • {job.title} at {job.company} - {job.location}")


@cli.command()
@click.option('--max-applications', type=int, help='Maximum number of applications to submit')
@click.option('--dry-run', is_flag=True, help='Show what would be applied to without actually applying')
@click.pass_context
def apply(ctx, max_applications, dry_run):
    """Apply to job postings"""
    bot = JobApplicationBot(ctx.obj['config_path'])
    
    if dry_run:
        click.echo(f"{Fore.YELLOW}🔍 Dry run mode - showing jobs that would be applied to{Style.RESET_ALL}")
        unapplied_jobs = bot.storage_manager.get_unapplied_jobs()
        
        if max_applications:
            unapplied_jobs = unapplied_jobs[:max_applications]
        
        if not unapplied_jobs:
            click.echo(f"{Fore.YELLOW}No unapplied jobs found{Style.RESET_ALL}")
            return
        
        click.echo(f"\n{Fore.CYAN}Jobs that would be applied to:{Style.RESET_ALL}")
        for job in unapplied_jobs:
            click.echo(f"  • {job.title} at {job.company} - {job.location}")
        
        click.echo(f"\n{Fore.GREEN}Would apply to {len(unapplied_jobs)} jobs{Style.RESET_ALL}")
    else:
        click.echo(f"{Fore.GREEN}📝 Applying to jobs...{Style.RESET_ALL}")
        results = bot.apply_to_jobs(max_applications)
        
        successful = sum(1 for r in results if r.success)
        click.echo(f"{Fore.GREEN}✅ Applied to {successful}/{len(results)} jobs successfully{Style.RESET_ALL}")


@cli.command()
@click.option('--boards', multiple=True, type=click.Choice(['linkedin', 'indeed', 'glassdoor']), 
              help='Job boards to search (default: all)')
@click.option('--max-applications', type=int, help='Maximum number of applications to submit')
@click.pass_context
def run(ctx, boards, max_applications):
    """Run full search and apply cycle"""
    click.echo(f"{Fore.GREEN}🚀 Starting full job application cycle...{Style.RESET_ALL}")
    
    bot = JobApplicationBot(ctx.obj['config_path'])
    
    # Convert board names to JobBoard enums
    job_boards = None
    if boards:
        job_boards = [JobBoard(board) for board in boards]
    
    success = bot.run_full_cycle(job_boards, max_applications)
    
    if success:
        click.echo(f"{Fore.GREEN}✅ Full cycle completed successfully{Style.RESET_ALL}")
    else:
        click.echo(f"{Fore.RED}❌ Full cycle failed{Style.RESET_ALL}")
        sys.exit(1)


@cli.command()
@click.pass_context
def stats(ctx):
    """Show job statistics"""
    bot = JobApplicationBot(ctx.obj['config_path'])
    statistics = bot.get_job_statistics()
    
    click.echo(f"{Fore.CYAN}📊 Job Statistics{Style.RESET_ALL}")
    click.echo(f"Total jobs: {statistics['total_jobs']}")
    click.echo(f"Recent jobs (7 days): {statistics.get('recent_jobs', 0)}")
    
    if statistics.get('by_status'):
        click.echo(f"\n{Fore.CYAN}By Status:{Style.RESET_ALL}")
        for status, count in statistics['by_status'].items():
            click.echo(f"  {status}: {count}")
    
    if statistics.get('by_job_board'):
        click.echo(f"\n{Fore.CYAN}By Job Board:{Style.RESET_ALL}")
        for board, count in statistics['by_job_board'].items():
            click.echo(f"  {board}: {count}")


@cli.command()
@click.pass_context
def validate(ctx):
    """Validate configuration"""
    click.echo(f"{Fore.YELLOW}🔧 Validating configuration...{Style.RESET_ALL}")
    
    bot = JobApplicationBot(ctx.obj['config_path'])
    
    if bot.validate_configuration():
        click.echo(f"{Fore.GREEN}✅ Configuration is valid{Style.RESET_ALL}")
    else:
        click.echo(f"{Fore.RED}❌ Configuration validation failed{Style.RESET_ALL}")
        sys.exit(1)


@cli.command()
@click.option('--output', default='jobs_export.csv', help='Output CSV file path')
@click.pass_context
def export(ctx, output):
    """Export jobs to CSV"""
    click.echo(f"{Fore.YELLOW}📤 Exporting jobs to CSV...{Style.RESET_ALL}")
    
    bot = JobApplicationBot(ctx.obj['config_path'])
    
    if bot.storage_manager.export_to_csv(output):
        click.echo(f"{Fore.GREEN}✅ Jobs exported to {output}{Style.RESET_ALL}")
    else:
        click.echo(f"{Fore.RED}❌ Export failed{Style.RESET_ALL}")
        sys.exit(1)


if __name__ == "__main__":
    cli()
