import os
from bs4 import BeautifulSoup
import base64
import requests
from urllib.parse import urljoin, urlparse
import logging
from pathlib import Path
import hashlib
import re
from typing import Optional, Dict, List, Union
import mimetypes
import concurrent.futures
from config import CONFIG, get_logger

logger = get_logger(__name__)

class SingleFile:
    def __init__(self):
        self.resources: Dict[str, str] = {}
        self.failed_resources: Dict[str, str] = {}
        self.base_url: Optional[str] = None
        self.options = CONFIG['SINGLE_FILE_OPTIONS']
        self.session = requests.Session()
        self.resource_count = 0
        self.max_threads = 5

    def _get_resource_hash(self, url: str) -> str:
        """Generate a unique hash for a resource URL"""
        return hashlib.md5(url.encode()).hexdigest()

    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid and should be processed"""
        try:
            parsed = urlparse(url)
            return bool(parsed.netloc) and bool(parsed.scheme)
        except Exception:
            return False

    def _download_resource(self, url: str) -> Optional[str]:
        """Download and encode a single resource"""
        try:
            if not self._is_valid_url(url):
                return None

            # Check cache first
            resource_hash = self._get_resource_hash(url)
            cache_path = Path(CONFIG['CACHE_DIR']) / f"{resource_hash}.cache"
            
            if cache_path.exists() and self.options.get('use_cache', True):
                with open(cache_path, 'r', encoding='utf-8') as f:
                    return f.read()

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }

            response = self.session.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                self.failed_resources[url] = f"HTTP {response.status_code}"
                return None

            content_type = response.headers.get('content-type', '').split(';')[0]
            if not content_type:
                content_type = mimetypes.guess_type(url)[0] or 'application/octet-stream'

            # Convert to base64
            encoded = base64.b64encode(response.content).decode('utf-8')
            data_url = f"data:{content_type};base64,{encoded}"

            # Cache the result
            if self.options.get('use_cache', True):
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                with open(cache_path, 'w', encoding='utf-8') as f:
                    f.write(data_url)

            return data_url

        except Exception as e:
            self.failed_resources[url] = str(e)
            logger.warning(f"Failed to download resource {url}: {str(e)}")
            return None

    def _process_stylesheets(self, soup: BeautifulSoup) -> None:
        """Process and inline CSS stylesheets"""
        for link in soup.find_all('link', rel='stylesheet'):
            try:
                if 'href' in link.attrs:
                    href = urljoin(self.base_url, link['href'])
                    css_content = self._download_resource(href)
                    if css_content:
                        style = soup.new_tag('style')
                        style.string = css_content
                        link.replace_with(style)
            except Exception as e:
                logger.warning(f"Failed to process stylesheet {link.get('href', '')}: {str(e)}")

    def _process_scripts(self, soup: BeautifulSoup) -> None:
        """Process and inline JavaScript files"""
        if not self.options.get('include_scripts', True):
            for script in soup.find_all('script'):
                script.decompose()
            return

        for script in soup.find_all('script', src=True):
            try:
                src = urljoin(self.base_url, script['src'])
                js_content = self._download_resource(src)
                if js_content:
                    new_script = soup.new_tag('script')
                    new_script.string = js_content
                    script.replace_with(new_script)
            except Exception as e:
                logger.warning(f"Failed to process script {script.get('src', '')}: {str(e)}")

    def _process_images(self, soup: BeautifulSoup) -> None:
        """Process and inline images"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            futures = []
            for img in soup.find_all('img', src=True):
                src = urljoin(self.base_url, img['src'])
                futures.append(executor.submit(self._download_resource, src))

            for img, future in zip(soup.find_all('img', src=True), futures):
                try:
                    data_url = future.result()
                    if data_url:
                        img['src'] = data_url
                        self.resource_count += 1
                except Exception as e:
                    logger.warning(f"Failed to process image {img.get('src', '')}: {str(e)}")

    def _clean_html(self, soup: BeautifulSoup) -> None:
        """Clean and optimize HTML content"""
        if self.options.get('remove_hidden_elements', True):
            for elem in soup.find_all(style=re.compile(r'display:\s*none')):
                elem.decompose()

        if self.options.get('remove_comments', True):
            for comment in soup.find_all(text=lambda text: isinstance(text, Comment)):
                comment.extract()

        if self.options.get('remove_unused_styles', True):
            # Implement style cleanup logic here
            pass

    def save(self, html_content: str, output_path: Path, base_url: Optional[str] = None) -> bool:
        """Save page with all resources in a single HTML file"""
        try:
            self.base_url = base_url
            self.resource_count = 0
            self.failed_resources.clear()

            logger.info(f"Starting to process page for {output_path}")
            
            # Parse HTML
            soup = BeautifulSoup(html_content, 'lxml')

            # Add meta tags
            meta_charset = soup.new_tag('meta')
            meta_charset['charset'] = 'UTF-8'
            if soup.head:
                soup.head.insert(0, meta_charset)
            else:
                head = soup.new_tag('head')
                head.append(meta_charset)
                soup.html.insert(0, head)

            # Process resources
            self._process_stylesheets(soup)
            self._process_images(soup)
            self._process_scripts(soup)
            self._clean_html(soup)

            # Save file
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(str(soup))
            
            # Log results
            logger.info(f"Page saved successfully to {output_path}")
            logger.info(f"Processed {self.resource_count} resources")
            if self.failed_resources:
                logger.warning(f"Failed to process {len(self.failed_resources)} resources")
                for url, error in self.failed_resources.items():
                    logger.debug(f"Resource {url} failed: {error}")

            return True

        except Exception as e:
            logger.error(f"Error saving page: {e}")
            return False

    def cleanup(self):
        """Cleanup resources"""
        try:
            self.session.close()
            self.resources.clear()
            self.failed_resources.clear()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")