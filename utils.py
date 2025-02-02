# utils.py
# Created: 2025-01-29 13:06:17
# Author: drphon
# Description: Advanced utility functions and classes for Windows web scraping

import os
import re
import sys
import time
import psutil
import winreg
import win32api
import win32con
import win32file
import win32event
import win32process
import win32security
import win32service
import logging
import threading
import pythoncom
import win32com.client
from typing import Optional, Dict, List, Any, Union, Tuple, Generator
from pathlib import Path, WindowsPath
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from config import CONFIG
from exceptions import WindowsError, ResourceError

logger = logging.getLogger(__name__)

class WindowsSystemMonitor:
    """Advanced Windows system monitoring and management"""
    
    def __init__(self):
        self._initialize_com()
        self.wmi = win32com.client.GetObject("winmgmts:")
        self._setup_performance_counters()
        
    def _initialize_com(self):
        """Initialize COM for WMI"""
        try:
            pythoncom.CoInitialize()
        except Exception as e:
            logger.error(f"Failed to initialize COM: {e}")
            
    def _setup_performance_counters(self):
        """Setup Windows performance counters"""
        try:
            self.counters = {
                'cpu': win32pdh.AddCounter(self.query, "\\Processor(_Total)\\% Processor Time"),
                'memory': win32pdh.AddCounter(self.query, "\\Memory\\Available MBytes"),
                'disk': win32pdh.AddCounter(self.query, "\\PhysicalDisk(_Total)\\% Disk Time"),
                'network': win32pdh.AddCounter(self.query, "\\Network Interface(*)\\Bytes Total/sec")
            }
        except Exception as e:
            logger.error(f"Failed to setup performance counters: {e}")

    def get_system_metrics(self) -> Dict[str, Any]:
        """Get comprehensive system metrics"""
        metrics = {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory': psutil.virtual_memory()._asdict(),
            'disk': {disk.device: disk._asdict() 
                    for disk in psutil.disk_partitions()},
            'network': psutil.net_io_counters()._asdict(),
            'handles': self._get_handle_count(),
            'processes': len(psutil.pids()),
            'threads': self._get_thread_count()
        }
        return metrics

    def _get_handle_count(self) -> int:
        """Get total handle count"""
        try:
            return sum(proc.num_handles() 
                      for proc in psutil.process_iter(['num_handles']))
        except Exception:
            return 0

    def _get_thread_count(self) -> int:
        """Get total thread count"""
        try:
            return sum(proc.num_threads() 
                      for proc in psutil.process_iter(['num_threads']))
        except Exception:
            return 0

class MemoryManager:
    """Advanced memory management for Windows"""
    
    def __init__(self, threshold: float = CONFIG['resources']['max_memory_percent']):
        self.threshold = threshold
        self.warning_threshold = threshold * 0.8
        self._setup_memory_monitoring()

    def _setup_memory_monitoring(self):
        """Setup memory monitoring"""
        self.memory_event = win32event.CreateEvent(None, 0, 0, None)
        self.monitor_thread = threading.Thread(
            target=self._monitor_memory,
            daemon=True
        )
        self.monitor_thread.start()

    def _monitor_memory(self):
        """Monitor memory usage"""
        while True:
            try:
                memory = psutil.virtual_memory()
                if memory.percent >= self.threshold:
                    self._handle_memory_pressure()
                elif memory.percent >= self.warning_threshold:
                    logger.warning(f"Memory usage high: {memory.percent}%")
                time.sleep(1)
            except Exception as e:
                logger.error(f"Memory monitoring error: {e}")

    def _handle_memory_pressure(self):
        """Handle high memory pressure"""
        try:
            # Trigger garbage collection
            import gc
            gc.collect()
            
            # Clear disk cache
            win32api.GlobalMemoryStatus()
            
            # Adjust working set
            current_process = psutil.Process()
            current_process.memory_info()
            
            logger.info("Memory pressure handled")
        except Exception as e:
            logger.error(f"Failed to handle memory pressure: {e}")

    def allocate_memory(self, size: int) -> bool:
        """Safely allocate memory"""
        try:
            memory = psutil.virtual_memory()
            if memory.available >= size:
                return True
            raise ResourceError(
                message="Insufficient memory",
                resource_type="MEMORY",
                current_value=memory.available,
                limit=size
            )
        except Exception as e:
            logger.error(f"Memory allocation error: {e}")
            return False

class ProcessController:
    """Windows process management and control"""
    
    def __init__(self):
        self.processes: Dict[int, psutil.Process] = {}
        self._setup_job_object()

    def _setup_job_object(self):
        """Setup Windows job object for process management"""
        try:
            self.job = win32job.CreateJobObject(None, f"WebScraper_{id(self)}")
            limits = win32job.JOBOBJECT_BASIC_LIMIT_INFORMATION()
            limits.LimitFlags = (
                win32job.JOB_OBJECT_LIMIT_PROCESS_TIME |
                win32job.JOB_OBJECT_LIMIT_JOB_TIME |
                win32job.JOB_OBJECT_LIMIT_ACTIVE_PROCESS
            )
            win32job.SetInformationJobObject(
                self.job,
                win32job.JobObjectBasicLimitInformation,
                limits
            )
        except Exception as e:
            logger.error(f"Failed to setup job object: {e}")

    def create_process(self, command: str, **kwargs) -> Optional[psutil.Process]:
        """Create and manage new process"""
        try:
            process = psutil.Popen(command.split(), **kwargs)
            self.processes[process.pid] = process
            
            # Add to job object
            handle = win32api.OpenProcess(
                win32con.PROCESS_ALL_ACCESS,
                False,
                process.pid
            )
            win32job.AssignProcessToJobObject(self.job, handle)
            
            return process
        except Exception as e:
            logger.error(f"Failed to create process: {e}")
            return None

    def terminate_process(self, pid: int) -> bool:
        """Safely terminate process"""
        try:
            if pid in self.processes:
                process = self.processes[pid]
                process.terminate()
                process.wait(timeout=5)
                del self.processes[pid]
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to terminate process {pid}: {e}")
            return False

class FileSystemWatcher:
    """Windows filesystem monitoring and management"""
    
    def __init__(self, path: Union[str, Path]):
        self.path = Path(path)
        self.observer = Observer()
        self.event_handler = self._create_event_handler()
        self._setup_watcher()

    def _create_event_handler(self) -> FileSystemEventHandler:
        """Create file system event handler"""
        class Handler(FileSystemEventHandler):
            def on_created(self, event):
                if not event.is_directory:
                    logger.info(f"File created: {event.src_path}")
                    
            def on_modified(self, event):
                if not event.is_directory:
                    logger.info(f"File modified: {event.src_path}")
                    
            def on_deleted(self, event):
                if not event.is_directory:
                    logger.info(f"File deleted: {event.src_path}")
                    
            def on_moved(self, event):
                if not event.is_directory:
                    logger.info(f"File moved/renamed: {event.src_path} -> {event.dest_path}")
        
        return Handler()

    def _setup_watcher(self):
        """Setup filesystem watcher"""
        try:
            self.observer.schedule(
                self.event_handler,
                str(self.path),
                recursive=False
            )
            self.observer.start()
        except Exception as e:
            logger.error(f"Failed to setup filesystem watcher: {e}")

    def stop_watching(self):
        """Stop filesystem watching"""
        try:
            self.observer.stop()
            self.observer.join()
        except Exception as e:
            logger.error(f"Failed to stop filesystem watcher: {e}")

class RegistryManager:
    """Windows registry management"""
    
    def __init__(self):
        self.roots = {
            'HKLM': win32con.HKEY_LOCAL_MACHINE,
            'HKCU': win32con.HKEY_CURRENT_USER,
            'HKCR': win32con.HKEY_CLASSES_ROOT,
            'HKU': win32con.HKEY_USERS,
            'HKCC': win32con.HKEY_CURRENT_CONFIG
        }

    def read_value(self, key_path: str, value_name: str) -> Optional[Any]:
        """Read registry value"""
        try:
            root_name = key_path.split('\\')[0]
            sub_key = '\\'.join(key_path.split('\\')[1:])
            
            with winreg.OpenKey(self.roots[root_name], sub_key, 0,
                               winreg.KEY_READ) as key:
                value, type_ = winreg.QueryValueEx(key, value_name)
                return value
        except Exception as e:
            logger.error(f"Failed to read registry value: {e}")
            return None

    def write_value(self, key_path: str, value_name: str,
                   value: Any, value_type: int) -> bool:
        """Write registry value"""
        try:
            root_name = key_path.split('\\')[0]
            sub_key = '\\'.join(key_path.split('\\')[1:])
            
            with winreg.OpenKey(self.roots[root_name], sub_key, 0,
                               winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, value_name, 0, value_type, value)
                return True
        except Exception as e:
            logger.error(f"Failed to write registry value: {e}")
            return False

class FileCache:
    """File-based caching system"""
    
    def __init__(self, cache_dir: Union[str, Path]):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cleanup_old_cache()

    def _cleanup_old_cache(self):
        """Clean up old cache files"""
        try:
            current_time = time.time()
            for cache_file in self.cache_dir.glob('*'):
                if current_time - cache_file.stat().st_mtime > \
                   CONFIG['files']['temp_file_lifetime']:
                    cache_file.unlink()
        except Exception as e:
            logger.error(f"Cache cleanup error: {e}")

    def get(self, key: str) -> Optional[bytes]:
        """Get cached data"""
        try:
            cache_file = self.cache_dir / self._hash_key(key)
            if cache_file.exists():
                return cache_file.read_bytes()
            return None
        except Exception as e:
            logger.error(f"Cache read error: {e}")
            return None

    def set(self, key: str, data: bytes,
            expiry: Optional[int] = None) -> bool:
        """Set cached data"""
        try:
            cache_file = self.cache_dir / self._hash_key(key)
            cache_file.write_bytes(data)
            if expiry:
                # Set file modification time for expiry
                os.utime(cache_file, (time.time(), time.time() + expiry))
            return True
        except Exception as e:
            logger.error(f"Cache write error: {e}")
            return False

    @staticmethod
    def _hash_key(key: str) -> str:
        """Hash cache key"""
        import hashlib
        return hashlib.sha256(key.encode()).hexdigest()

class DownloadManager:
    """Concurrent download manager"""
    
    def __init__(self, max_workers: Optional[int] = None):
        self.max_workers = max_workers or CONFIG['performance']['thread_pool_size']
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self.downloads: Dict[str, Any] = {}
        self._setup_rate_limiting()

    def _setup_rate_limiting(self):
        """Setup download rate limiting"""
        self.rate_limit = float(CONFIG['network']['download_rate_limit'])
        self.rate_semaphore = threading.Semaphore(
            CONFIG['performance']['max_concurrent_downloads']
        )

    async def download_file(self, url: str, destination: Union[str, Path],
                          chunk_size: int = 8192) -> bool:
        """Download file with rate limiting and progress tracking"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        with open(destination, 'wb') as f:
                            while True:
                                chunk = await response.content.read(chunk_size)
                                if not chunk:
                                    break
                                f.write(chunk)
                        return True
            return False
        except Exception as e:
            logger.error(f"Download error: {e}")
            return False

    def cancel_download(self, url: str) -> bool:
        """Cancel ongoing download"""
        try:
            if url in self.downloads:
                self.downloads[url].cancel()
                del self.downloads[url]
                return True
            return False
        except Exception as e:
            logger.error(f"Cancel download error: {e}")
            return False

# Initialize global instances
system_monitor = WindowsSystemMonitor()
memory_manager = MemoryManager()
process_controller = ProcessController()
registry_manager = RegistryManager()
file_cache = FileCache(CONFIG['cache_dir'])
download_manager = DownloadManager()

def initialize_utils() -> None:
    """Initialize utility components"""
    try:
        # Set process priority
        process_controller.set_process_priority(CONFIG['windows']['process_priority'])
        
        # Setup file system watcher for download directory
        global file_watcher
        file_watcher = FileSystemWatcher(CONFIG['download_dir'])
        
        logger.info("Utility components initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize utilities: {e}")
        raise

# Initialize on import
initialize_utils()