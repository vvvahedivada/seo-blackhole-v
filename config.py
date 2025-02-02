# config.py
# Created: 2025-01-29 12:33:44
# Author: drphon
# Description: Configuration settings for web scraping application (Windows-optimized)

import os
import sys
from pathlib import Path
from typing import Dict, Any

# Base Directories
BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
DOWNLOAD_DIR = BASE_DIR / 'downloads'
CACHE_DIR = BASE_DIR / 'cache'
LOG_DIR = BASE_DIR / 'logs'
TEMP_DIR = BASE_DIR / 'temp'

# Ensure all directories exist
for directory in [DOWNLOAD_DIR, CACHE_DIR, LOG_DIR, TEMP_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Chrome and ChromeDriver Settings
CHROME_SETTINGS = {
    'driver_path': str(BASE_DIR / 'drivers' / 'chromedriver.exe'),
    'binary_location': r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    'version_check': True,
    'auto_download': True,
    'headless': True,
    'window_size': (1920, 1080),
}

# Browser Options
BROWSER_OPTIONS = {
    'arguments': [
        '--headless',
        '--disable-gpu',
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--disable-notifications',
        '--disable-infobars',
        '--disable-extensions',
        '--disable-logging',
        f'--user-data-dir={str(CACHE_DIR / "chrome_profile")}',
        f'--disk-cache-dir={str(CACHE_DIR / "chrome_cache")}',
    ],
    'experimental_options': {
        'prefs': {
            'download.default_directory': str(DOWNLOAD_DIR),
            'download.prompt_for_download': False,
            'download.directory_upgrade': True,
            'safebrowsing.enabled': True,
            'profile.default_content_setting_values.notifications': 2,
        }
    }
}

# Resource Management
RESOURCE_LIMITS = {
    'max_memory_percent': 75.0,  # Maximum memory usage percentage
    'max_cpu_percent': 85.0,     # Maximum CPU usage percentage
    'max_connections': 100,      # Maximum concurrent connections
    'connection_timeout': 30,    # Connection timeout in seconds
    'max_retries': 3,           # Maximum retry attempts
    'retry_delay': 5,           # Delay between retries in seconds
}

# File Management
FILE_SETTINGS = {
    'max_file_size': 100 * 1024 * 1024,  # 100MB in bytes
    'allowed_extensions': ['.html', '.htm', '.pdf', '.jpg', '.png', '.gif'],
    'compression_level': 6,  # 0-9 (0=none, 9=maximum)
    'chunk_size': 8192,     # File reading/writing chunk size
    'temp_file_lifetime': 3600,  # Temporary file lifetime in seconds
}

# Network Settings
NETWORK_SETTINGS = {
    'timeout': {
        'connect': 10,
        'read': 30,
        'write': 30
    },
    'headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
    },
    'ssl_verify': True,
    'proxy': None,  # Set to dict with 'http' and 'https' keys if needed
}

# Logging Configuration
LOG_SETTINGS = {
    'filename': str(LOG_DIR / 'scraper.log'),
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'level': 'INFO',
    'rotation': '1 day',
    'retention': '30 days',
    'encoding': 'utf-8',
}

# Error Management
ERROR_SETTINGS = {
    'max_errors': 50,           # Maximum number of errors before stopping
    'error_threshold': 0.3,     # Error rate threshold (30%)
    'log_errors': True,         # Log errors to file
    'notify_errors': False,     # Send error notifications
    'screenshot_on_error': True, # Take screenshot on error
}

# Performance Optimization
PERFORMANCE_SETTINGS = {
    'thread_pool_size': min(32, (os.cpu_count() or 1) * 4),
    'process_pool_size': max(1, (os.cpu_count() or 1) - 1),
    'chunk_size': 10,          # Number of URLs to process in one batch
    'max_concurrent_downloads': 5,
    'memory_cleanup_threshold': 85.0,  # Memory threshold for cleanup
}

# Security Settings
SECURITY_SETTINGS = {
    'verify_ssl': True,
    'allow_redirects': True,
    'max_redirects': 5,
    'trusted_domains': [],      # List of trusted domains
    'blocked_domains': [],      # List of blocked domains
    'request_delay': 1.0,      # Delay between requests in seconds
}

# Windows-Specific Settings
WINDOWS_SETTINGS = {
    'long_path_enabled': True,  # Enable long path support
    'use_tempfile': True,      # Use temporary files for downloads
    'file_lock_timeout': 30,   # File lock timeout in seconds
    'antivirus_skip_paths': [str(TEMP_DIR)],  # Paths to exclude from antivirus
    'process_priority': 'NORMAL',  # IDLE, BELOW_NORMAL, NORMAL, ABOVE_NORMAL, HIGH
}

# Export all settings as a single dictionary
CONFIG: Dict[str, Any] = {
    'base_dir': BASE_DIR,
    'download_dir': DOWNLOAD_DIR,
    'cache_dir': CACHE_DIR,
    'log_dir': LOG_DIR,
    'temp_dir': TEMP_DIR,
    'chrome': CHROME_SETTINGS,
    'browser_options': BROWSER_OPTIONS,
    'resources': RESOURCE_LIMITS,
    'files': FILE_SETTINGS,
    'network': NETWORK_SETTINGS,
    'logging': LOG_SETTINGS,
    'errors': ERROR_SETTINGS,
    'performance': PERFORMANCE_SETTINGS,
    'security': SECURITY_SETTINGS,
    'windows': WINDOWS_SETTINGS,
}

def get_config() -> Dict[str, Any]:
    """Return the current configuration"""
    return CONFIG

def update_config(new_settings: Dict[str, Any]) -> None:
    """Update configuration with new settings"""
    CONFIG.update(new_settings)

# Validate critical paths on startup
def validate_paths() -> None:
    """Validate and create necessary directories"""
    try:
        for directory in [DOWNLOAD_DIR, CACHE_DIR, LOG_DIR, TEMP_DIR]:
            if not directory.exists():
                directory.mkdir(parents=True)
            # Test write permissions
            test_file = directory / '.test'
            test_file.touch()
            test_file.unlink()
    except Exception as e:
        sys.exit(f"Failed to validate paths: {str(e)}")

# Run validation on import
validate_paths()