// Main JavaScript for Job Application Bot

// Global variables
let loadingModal;
let socket;

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap components
    loadingModal = new bootstrap.Modal(document.getElementById('loadingModal'));
    
    // Initialize WebSocket connection
    initializeWebSocket();
    
    // Add fade-in animation to cards
    const cards = document.querySelectorAll('.card');
    cards.forEach((card, index) => {
        setTimeout(() => {
            card.classList.add('fade-in-up');
        }, index * 100);
    });
    
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

// WebSocket Functions
function initializeWebSocket() {
    // Only initialize if Socket.IO is available
    if (typeof io !== 'undefined') {
        socket = io();
        
        socket.on('connect', function() {
            console.log('WebSocket connected');
        });
        
        socket.on('disconnect', function() {
            console.log('WebSocket disconnected');
        });
        
        socket.on('search_status', function(data) {
            if (data.status === 'job_found') {
                handleNewJob(data);
            } else {
                handleSearchStatus(data);
            }
        });
        
        socket.on('job_found', function(data) {
            handleNewJob(data);
        });
    }
}

function handleSearchStatus(data) {
    const { status, message, jobs_count } = data;
    
    if (status === 'started') {
        showLiveSearchProgress('Job search started...', 0);
    } else if (status === 'completed') {
        showAlert('success', message);
        hideLoading();
        refreshStats();
        // Refresh the jobs page if we're on it
        if (window.location.pathname === '/jobs') {
            setTimeout(() => window.location.reload(), 2000);
        }
    } else if (status === 'error') {
        showAlert('error', message);
        hideLoading();
    } else if (status === 'progress') {
        showLiveSearchProgress(message, jobs_count || 0);
    }
}

function handleNewJob(data) {
    // Add new job to the live list if we're on the jobs page
    if (window.location.pathname === '/jobs' && data.job) {
        addJobToLiveList(data.job);
    }
    updateJobCounter(data.total_found || 0);
}

function showLiveSearchProgress(message, jobCount) {
    const loadingText = document.getElementById('loadingText');
    if (loadingText) {
        loadingText.textContent = `${message} (${jobCount} jobs found)`;
    }
    
    // Update any progress indicators
    const progressElements = document.querySelectorAll('.search-progress');
    progressElements.forEach(el => {
        el.textContent = `Found ${jobCount} jobs so far...`;
    });
}

function addJobToLiveList(jobData) {
    const jobsList = document.querySelector('.jobs-list, .job-cards');
    if (!jobsList) return;
    
    const jobCard = createJobCard(jobData);
    jobsList.insertAdjacentHTML('afterbegin', jobCard);
    
    // Add animation to new job
    const newCard = jobsList.firstElementChild;
    newCard.classList.add('new-job-animation');
    setTimeout(() => {
        newCard.classList.remove('new-job-animation');
    }, 2000);
}

function createJobCard(job) {
    return `
        <div class="card mb-3 new-job-card">
            <div class="card-body">
                <div class="row">
                    <div class="col-md-8">
                        <h5 class="card-title">
                            <a href="${job.url}" target="_blank" class="text-decoration-none">
                                ${job.title}
                            </a>
                            <span class="badge bg-success ms-2">NEW</span>
                        </h5>
                        <p class="card-text">
                            <strong>${job.company}</strong> • ${job.location}
                        </p>
                        <p class="card-text">
                            <small class="text-muted">
                                <i class="fas fa-calendar-alt me-1"></i>${job.posting_date}
                                <i class="fas fa-globe ms-3 me-1"></i>${job.job_board}
                            </small>
                        </p>
                    </div>
                    <div class="col-md-4 text-end">
                        <span class="badge bg-primary mb-2">${job.application_status}</span>
                        <br>
                        <input type="checkbox" class="job-checkbox" value="${job.id}">
                    </div>
                </div>
            </div>
        </div>
    `;
}

function updateJobCounter(count) {
    const counters = document.querySelectorAll('.job-counter');
    counters.forEach(counter => {
        counter.textContent = count;
    });
}

// Utility Functions
function showLoading(message = 'Processing...') {
    document.getElementById('loadingText').textContent = message;
    loadingModal.show();
}

function hideLoading() {
    loadingModal.hide();
}

function showAlert(type, message) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    // Insert at the top of the main container
    const main = document.querySelector('main.container');
    if (main) {
        main.insertBefore(alertDiv, main.firstChild);
    }
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

// API Functions
async function makeApiRequest(url, options = {}) {
    try {
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }
        
        return data;
    } catch (error) {
        console.error('API request failed:', error);
        throw error;
    }
}

// Job Search Functions
async function searchJobs(jobBoards = ['linkedin', 'indeed', 'glassdoor']) {
    if (!confirm('Start searching for new jobs? This may take a few minutes.')) {
        return;
    }
    
    showLoading('Searching for jobs across platforms...');
    
    try {
        const data = await makeApiRequest('/api/search_jobs', {
            method: 'POST',
            body: JSON.stringify({ job_boards: jobBoards })
        });
        
        hideLoading();
        showAlert('success', 'Job search started! New jobs will appear in the jobs page shortly.');
        
        // Refresh stats after a delay
        setTimeout(refreshStats, 5000);
        
    } catch (error) {
        hideLoading();
        showAlert('error', `Failed to start job search: ${error.message}`);
    }
}

async function applyToJobs(maxApplications = 10) {
    if (!confirm(`Start applying to up to ${maxApplications} jobs? Make sure your preferences are configured correctly.`)) {
        return;
    }
    
    showLoading('Applying to jobs...');
    
    try {
        const data = await makeApiRequest('/api/apply_jobs', {
            method: 'POST',
            body: JSON.stringify({ max_applications: maxApplications })
        });
        
        hideLoading();
        showAlert('success', 'Job applications started! Check back in a few minutes for updates.');
        
        // Refresh stats after a delay
        setTimeout(refreshStats, 10000);
        
    } catch (error) {
        hideLoading();
        showAlert('error', `Failed to start job applications: ${error.message}`);
    }
}

async function refreshStats() {
    try {
        const data = await makeApiRequest('/api/job_stats');
        
        // Update stat cards if they exist
        updateStatCard('total_jobs', data.total_jobs);
        updateStatCard('applied_jobs', data.applied_jobs);
        updateStatCard('pending_jobs', data.pending_jobs);
        updateStatCard('failed_jobs', data.failed_jobs);
        
        // Update charts if they exist
        if (typeof statusChart !== 'undefined') {
            statusChart.data.datasets[0].data = [data.applied_jobs, data.pending_jobs, data.failed_jobs];
            statusChart.update();
        }
        
        showAlert('info', 'Statistics refreshed successfully!');
        
    } catch (error) {
        showAlert('error', `Failed to refresh statistics: ${error.message}`);
    }
}

function updateStatCard(type, value) {
    const cards = document.querySelectorAll('.card');
    cards.forEach(card => {
        const title = card.querySelector('.card-title');
        if (title && title.textContent.toLowerCase().includes(type.replace('_', ' '))) {
            const valueElement = card.querySelector('h2');
            if (valueElement) {
                // Animate the number change
                animateNumber(valueElement, parseInt(valueElement.textContent) || 0, value);
            }
        }
    });
}

function animateNumber(element, start, end) {
    const duration = 1000;
    const startTime = performance.now();
    
    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        const current = Math.round(start + (end - start) * progress);
        element.textContent = current;
        
        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }
    
    requestAnimationFrame(update);
}

// Form Validation
function validateForm(form) {
    const requiredFields = form.querySelectorAll('[required]');
    let isValid = true;
    
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            field.classList.add('is-invalid');
            isValid = false;
        } else {
            field.classList.remove('is-invalid');
        }
    });
    
    return isValid;
}

// Job Management Functions
function selectAllJobs(checkbox) {
    const jobCheckboxes = document.querySelectorAll('.job-checkbox:not([disabled])');
    jobCheckboxes.forEach(cb => {
        cb.checked = checkbox.checked;
    });
}

async function applyToSelectedJobs() {
    const selectedJobs = Array.from(document.querySelectorAll('.job-checkbox:checked')).map(cb => cb.value);
    
    if (selectedJobs.length === 0) {
        showAlert('warning', 'Please select at least one job to apply to.');
        return;
    }
    
    if (!confirm(`Apply to ${selectedJobs.length} selected jobs?`)) {
        return;
    }
    
    showLoading(`Applying to ${selectedJobs.length} jobs...`);
    
    try {
        const data = await makeApiRequest('/api/apply_jobs', {
            method: 'POST',
            body: JSON.stringify({
                job_ids: selectedJobs,
                max_applications: selectedJobs.length
            })
        });
        
        hideLoading();
        showAlert('success', 'Job applications started! The page will refresh shortly.');
        
        // Refresh page after delay
        setTimeout(() => window.location.reload(), 3000);
        
    } catch (error) {
        hideLoading();
        showAlert('error', `Failed to start job applications: ${error.message}`);
    }
}

// Preferences Functions
function addDynamicField(containerId, fieldName, fieldType = 'text', options = []) {
    const container = document.getElementById(containerId);
    const div = document.createElement('div');
    div.className = 'input-group mb-2';
    
    let inputHtml;
    if (fieldType === 'select') {
        inputHtml = `<select class="form-select" name="${fieldName}">`;
        options.forEach(option => {
            inputHtml += `<option value="${option.value}">${option.text}</option>`;
        });
        inputHtml += `</select>`;
    } else {
        inputHtml = `<input type="${fieldType}" class="form-control" name="${fieldName}" placeholder="${getPlaceholder(fieldName)}">`;
    }
    
    div.innerHTML = `
        ${inputHtml}
        <button type="button" class="btn btn-outline-danger" onclick="removeField(this)">
            <i class="fas fa-times"></i>
        </button>
    `;
    
    container.appendChild(div);
}

function removeField(button) {
    button.parentElement.remove();
}

function getPlaceholder(fieldName) {
    const placeholders = {
        'keywords': 'e.g. Software Engineer',
        'locations': 'e.g. Remote, San Francisco',
        'exclude_keywords': 'e.g. unpaid, intern'
    };
    
    return placeholders[fieldName] || '';
}

// Search and Filter Functions
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Auto-save preferences (debounced)
const autoSavePreferences = debounce(function() {
    const form = document.querySelector('form');
    if (form && form.action.includes('preferences')) {
        // Could implement auto-save here
        console.log('Auto-saving preferences...');
    }
}, 2000);

// Add event listeners for auto-save
document.addEventListener('change', function(e) {
    if (e.target.matches('input, select, textarea')) {
        autoSavePreferences();
    }
});

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Ctrl/Cmd + S to save (on preferences page)
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        const form = document.querySelector('form[method="POST"]');
        if (form) {
            e.preventDefault();
            form.submit();
        }
    }
    
    // Ctrl/Cmd + F to focus search
    if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
        const searchInput = document.querySelector('input[name="search"]');
        if (searchInput) {
            e.preventDefault();
            searchInput.focus();
        }
    }
});

// Progress tracking
function updateProgress(current, total) {
    const percentage = Math.round((current / total) * 100);
    const progressBars = document.querySelectorAll('.progress-bar');
    
    progressBars.forEach(bar => {
        bar.style.width = `${percentage}%`;
        bar.setAttribute('aria-valuenow', percentage);
        bar.textContent = `${percentage}%`;
    });
}

// Error handling
window.addEventListener('error', function(e) {
    console.error('JavaScript error:', e.error);
    showAlert('error', 'An unexpected error occurred. Please refresh the page and try again.');
});

// Unhandled promise rejection handling
window.addEventListener('unhandledrejection', function(e) {
    console.error('Unhandled promise rejection:', e.reason);
    showAlert('error', 'An unexpected error occurred. Please try again.');
});

// Export functions for use in templates
window.jobAppBot = {
    searchJobs,
    applyToJobs,
    refreshStats,
    showAlert,
    showLoading,
    hideLoading,
    selectAllJobs,
    applyToSelectedJobs,
    addDynamicField,
    removeField
};
