# web_scraper.py
# Created: 2025-01-29 12:39:29
# Author: drphon
# Description: Main web scraping implementation (Windows-optimized)

import os
import time
import asyncio
import aiohttp
import logging
import warnings
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from config import CONFIG
from utils import FileUtils, NetworkUtils, SystemUtils, SecurityUtils
from exceptions import (
    ScraperException, WindowsError, NetworkError, 
    ChromeDriverError, ResourceError, ExceptionHandler
)

logger = logging.getLogger(__name__)

class WebScraper:
    """Main web scraper class optimized for Windows"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the web scraper"""
        self.config = config or CONFIG
        self.downloads: Dict[str, Any] = {}
        self.driver: Optional[webdriver.Chrome] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self._setup_chrome()
        self._setup_async_session()

    def _setup_chrome(self) -> None:
        """Setup Chrome WebDriver"""
        try:
            service = Service(executable_path=self.config['chrome']['driver_path'])
            options = Options()
            
            # Add Chrome options
            for arg in self.config['browser_options']['arguments']:
                options.add_argument(arg)
            
            # Add experimental options
            for key, value in self.config['browser_options']['experimental_options']['prefs'].items():
                options.add_experimental_option(key, value)
            
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.set_page_load_timeout(self.config['network']['timeout']['read'])
            
        except WebDriverException as e:
            raise ChromeDriverError(
                message="Failed to initialize Chrome WebDriver",
                windows_error_code=e.errno if hasattr(e, 'errno') else 0,
                details={'original_error': str(e)}
            )

    def _setup_async_session(self) -> None:
        """Setup async HTTP session"""
        timeout = aiohttp.ClientTimeout(
            connect=self.config['network']['timeout']['connect'],
            total=self.config['network']['timeout']['read']
        )
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers=self.config['network']['headers']
        )

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    async def close(self) -> None:
        """Close all resources"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.error(f"Error closing Chrome driver: {e}")
        
        if self.session:
            try:
                await self.session.close()
            except Exception as e:
                logger.error(f"Error closing aiohttp session: {e}")

    async def scrape_url(self, url: str, save_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """Scrape a single URL"""
        with ExceptionHandler(f"Scraping {url}"):
            # Validate URL
            if not NetworkUtils.is_valid_url(url):
                raise NetworkError("Invalid URL", url=url)
            
            # Check domain safety
            if not SecurityUtils.is_safe_domain(url):
                raise SecurityError(
                    message="Domain not allowed",
                    security_type="DOMAIN_BLOCKED",
                    details={'url': url}
                )
            
            # Check system resources
            resources = SystemUtils.check_resources()
            if not all(resources.values()):
                raise ResourceError(
                    message="System resources exceeded limits",
                    resource_type="SYSTEM",
                    current_value=100,
                    limit=self.config['resources']['max_memory_percent']
                )
            
            # Prepare save path
            if save_path:
                save_path = FileUtils.get_safe_path(save_path)
            else:
                filename = FileUtils.get_safe_filename(url)
                save_path = Path(self.config['download_dir']) / filename
            
            # Scrape the page
            try:
                content = await self._fetch_page(url)
                if content:
                    success = await self._save_content(save_path, content)
                    return {
                        'url': url,
                        'status': 'success' if success else 'failed',
                        'save_path': str(save_path),
                        'timestamp': datetime.utcnow().isoformat(),
                        'size': len(content)
                    }
            except Exception as e:
                logger.error(f"Error scraping {url}: {e}")
                return {
                    'url': url,
                    'status': 'failed',
                    'error': str(e),
                    'timestamp': datetime.utcnow().isoformat()
                }

    async def scrape_urls(self, urls: List[str], 
                         concurrent_limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Scrape multiple URLs concurrently"""
        if concurrent_limit is None:
            concurrent_limit = self.config['performance']['max_concurrent_downloads']
        
        tasks = []
        results = []
        
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(concurrent_limit)
        
        async def bounded_scrape(url: str) -> Dict[str, Any]:
            async with semaphore:
                return await self.scrape_url(url)
        
        # Create tasks for all URLs
        for url in urls:
            tasks.append(asyncio.create_task(bounded_scrape(url)))
        
        # Wait for all tasks to complete
        completed = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for result in completed:
            if isinstance(result, Exception):
                logger.error(f"Task failed: {result}")
                results.append({
                    'status': 'failed',
                    'error': str(result),
                    'timestamp': datetime.utcnow().isoformat()
                })
            else:
                results.append(result)
        
        return results

    async def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch page content"""
        try:
            if self.session and not self.session.closed:
                async with self.session.get(url) as response:
                    if response.status == 200:
                        return await response.text()
                    raise NetworkError(
                        message=f"HTTP {response.status}",
                        url=url,
                        status_code=response.status
                    )
        except aiohttp.ClientError as e:
            raise NetworkError(
                message=str(e),
                url=url,
                details={'original_error': str(e)}
            )
        return None

    async def _save_content(self, path: Path, content: str) -> bool:
        """Save content to file"""
        try:
            return FileUtils.safe_write(path, content)
        except Exception as e:
            logger.error(f"Error saving content to {path}: {e}")
            return False

    def get_dynamic_content(self, url: str, 
                          wait_time: int = 10,
                          scroll: bool = True) -> Optional[str]:
        """Get content from dynamic pages using Selenium"""
        if not self.driver:
            raise ChromeDriverError(
                message="Chrome driver not initialized",
                windows_error_code=0
            )
        
        try:
            self.driver.get(url)
            
            # Wait for page load
            WebDriverWait(self.driver, wait_time).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Scroll if needed
            if scroll:
                self._scroll_page()
            
            return self.driver.page_source
            
        except TimeoutException:
            raise NetworkError(
                message="Page load timeout",
                url=url,
                details={'timeout': wait_time}
            )
        except WebDriverException as e:
            raise ChromeDriverError(
                message="Chrome driver error",
                windows_error_code=e.errno if hasattr(e, 'errno') else 0,
                details={'original_error': str(e)}
            )

    def _scroll_page(self, pause_time: float = 1.0) -> None:
        """Scroll page to load dynamic content"""
        try:
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            
            while True:
                # Scroll down
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                
                # Wait for content to load
                time.sleep(pause_time)
                
                # Calculate new scroll height
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                
                # Break if no more content
                if new_height == last_height:
                    break
                    
                last_height = new_height
                
        except Exception as e:
            logger.warning(f"Error during page scrolling: {e}")

    @staticmethod
    def extract_links(html_content: str, base_url: str) -> List[str]:
        """Extract links from HTML content"""
        from bs4 import BeautifulSoup
        
        links = []
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            for link in soup.find_all('a', href=True):
                href = link['href']
                if href:
                    absolute_url = urljoin(base_url, href)
                    if NetworkUtils.is_valid_url(absolute_url):
                        links.append(absolute_url)
        except Exception as e:
            logger.error(f"Error extracting links: {e}")
        
        return links

if __name__ == "__main__":
    # Example usage
    async def main():
        async with WebScraper() as scraper:
            urls = [
                "https://example.com",
                "https://example.org"
            ]
            results = await scraper.scrape_urls(urls)
            print(results)
    
    asyncio.run(main())