# exceptions.py
# Created: 2025-01-29 12:38:20
# Author: drphon
# Description: Custom exceptions for web scraping application (Windows-optimized)

import sys
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class ScraperException(Exception):
    """Base exception class for scraper application"""
    def __init__(self, message: str, error_code: str = "GENERAL_ERROR",
                 details: Optional[Dict[str, Any]] = None) -> None:
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.timestamp = datetime.utcnow()
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary format"""
        return {
            'error_code': self.error_code,
            'message': self.message,
            'details': self.details,
            'timestamp': self.timestamp.isoformat(),
            'type': self.__class__.__name__
        }

class WindowsError(ScraperException):
    """Windows-specific errors"""
    def __init__(self, message: str, windows_error_code: int,
                 details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(
            message=message,
            error_code=f"WINDOWS_ERROR_{windows_error_code}",
            details={
                'windows_error_code': windows_error_code,
                'windows_error_name': self._get_windows_error_name(windows_error_code),
                **(details or {})
            }
        )

    @staticmethod
    def _get_windows_error_name(error_code: int) -> str:
        """Get Windows error name from error code"""
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        buf = ctypes.create_unicode_buffer(1024)
        
        flags = 0x00001000  # FORMAT_MESSAGE_FROM_SYSTEM
        kernel32.FormatMessageW(flags, None, error_code, 0, buf, len(buf), None)
        return buf.value.strip()

class FileSystemError(WindowsError):
    """File system related errors"""
    def __init__(self, message: str, path: Path, windows_error_code: int,
                 details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(
            message=message,
            windows_error_code=windows_error_code,
            details={
                'path': str(path),
                'is_file': path.is_file() if path.exists() else None,
                'is_dir': path.is_dir() if path.exists() else None,
                'exists': path.exists(),
                **(details or {})
            }
        )

class NetworkError(ScraperException):
    """Network related errors"""
    def __init__(self, message: str, url: str, status_code: Optional[int] = None,
                 details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(
            message=message,
            error_code="NETWORK_ERROR",
            details={
                'url': url,
                'status_code': status_code,
                'timestamp': datetime.utcnow().isoformat(),
                **(details or {})
            }
        )

class ChromeDriverError(WindowsError):
    """ChromeDriver specific errors"""
    def __init__(self, message: str, windows_error_code: int,
                 driver_version: Optional[str] = None,
                 details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(
            message=message,
            windows_error_code=windows_error_code,
            details={
                'driver_version': driver_version,
                'chrome_version': self._get_chrome_version(),
                **(details or {})
            }
        )

    @staticmethod
    def _get_chrome_version() -> Optional[str]:
        """Get installed Chrome version"""
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                               r"Software\Google\Chrome\BLBeacon")
            version, _ = winreg.QueryValueEx(key, "version")
            return version
        except Exception:
            return None

class ResourceError(ScraperException):
    """Resource management errors"""
    def __init__(self, message: str, resource_type: str,
                 current_value: float, limit: float,
                 details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(
            message=message,
            error_code="RESOURCE_ERROR",
            details={
                'resource_type': resource_type,
                'current_value': current_value,
                'limit': limit,
                'usage_percent': (current_value / limit) * 100,
                **(details or {})
            }
        )

class SecurityError(ScraperException):
    """Security related errors"""
    def __init__(self, message: str, security_type: str,
                 details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(
            message=message,
            error_code="SECURITY_ERROR",
            details={
                'security_type': security_type,
                'timestamp': datetime.utcnow().isoformat(),
                **(details or {})
            }
        )

def handle_exception(exc: Exception) -> Dict[str, Any]:
    """Handle and log exceptions"""
    if isinstance(exc, ScraperException):
        error_dict = exc.to_dict()
    else:
        error_dict = {
            'error_code': 'UNHANDLED_ERROR',
            'message': str(exc),
            'type': exc.__class__.__name__,
            'timestamp': datetime.utcnow().isoformat(),
            'details': {
                'traceback': sys.exc_info()[2].tb_frame.f_code.co_filename,
                'line_number': sys.exc_info()[2].tb_lineno
            }
        }

    # Log the error
    logger.error(
        f"Error occurred: {error_dict['type']} - {error_dict['message']}",
        extra={'error_details': error_dict}
    )

    return error_dict

def is_critical_error(error_dict: Dict[str, Any]) -> bool:
    """Determine if an error is critical"""
    critical_codes = {
        'SECURITY_ERROR',
        'RESOURCE_ERROR',
        'WINDOWS_ERROR_5',  # Access Denied
        'WINDOWS_ERROR_32',  # Sharing Violation
    }
    return (
        error_dict['error_code'] in critical_codes or
        error_dict.get('details', {}).get('windows_error_code', 0) in {5, 32}
    )

class ExceptionHandler:
    """Context manager for handling exceptions"""
    def __init__(self, context: str = ""):
        self.context = context

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            error_dict = handle_exception(exc_val)
            if is_critical_error(error_dict):
                logger.critical(
                    f"Critical error in {self.context}: {error_dict['message']}"
                )
                return False  # Re-raise the exception
            logger.error(
                f"Error in {self.context}: {error_dict['message']}"
            )
            return True  # Suppress the exception