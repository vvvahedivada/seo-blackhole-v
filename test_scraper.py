# test_scraper.py
# Created: 2025-01-29 10:30:10
# Author: drphon
# Description: Test suite for web scraping application

import pytest
import asyncio
from pathlib import Path
import json
from datetime import datetime
import os
from unittest.mock import Mock, patch

from web_scraper import WebScraper
from single_file import SingleFile
from exceptions import *
from utils import FileUtils, URLUtils, NetworkUtils
from config import CONFIG

class TestWebScraper:
    @pytest.fixture
    def scraper(self):
        """Create a WebScraper instance for testing"""
        scraper = WebScraper()
        yield scraper
        scraper.close()

    @pytest.fixture
    def sample_urls(self):
        """Sample URLs for testing"""
        return [
            "https://example.com/page1",
            "https://example.com/page2",
            "https://example.com/page3"
        ]

    @pytest.mark.asyncio
    async def test_initialization(self, scraper):
        """Test scraper initialization"""
        assert scraper is not None
        assert isinstance(scraper.downloads, dict)
        assert Path(CONFIG['OUTPUT_DIR']).exists()

    def test_search_google(self, scraper):
        """Test Google search functionality"""
        with patch('web_scraper.WebScraper.search_google') as mock_search:
            mock_search.return_value = ["https://example.com"]
            urls = scraper.search_google("test query")
            assert isinstance(urls, list)
            assert len(urls) > 0
            mock_search.assert_called_once_with("test query")

    @pytest.mark.asyncio
    async def test_process_urls(self, scraper, sample_urls):
        """Test URL processing"""
        with patch('web_scraper.WebScraper._download_single_page') as mock_download:
            mock_download.return_value = {
                'url': sample_urls[0],
                'status': 'success',
                'timestamp': datetime.now().isoformat()
            }
            results = await scraper.process_urls(sample_urls[:1])
            assert len(results) == 1
            assert results[0]['status'] == 'success'

class TestSingleFile:
    @pytest.fixture
    def single_file(self):
        """Create SingleFile instance for testing"""
        return SingleFile()

    def test_initialization(self, single_file):
        """Test SingleFile initialization"""
        assert single_file is not None
        assert single_file.cache is not None

    def test_save_file(self, single_file, tmp_path):
        """Test saving file functionality"""
        html_content = "<html><body>Test</body></html>"
        output_path = tmp_path / "test.html"
        
        result = single_file.save(
            html_content=html_content,
            output_path=output_path,
            base_url="https://example.com"
        )
        
        assert result is True
        assert output_path.exists()
        assert output_path.read_text().strip() == html_content.strip()

class TestUtils:
    def test_file_utils(self):
        """Test FileUtils functionality"""
        test_dir = Path("test_dir")
        
        # Test directory creation
        FileUtils.ensure_dir(test_dir)
        assert test_dir.exists()
        
        # Test safe filename generation
        url = "https://example.com/test/page.html"
        filename = FileUtils.get_safe_filename(url)
        assert isinstance(filename, str)
        assert ".html" in filename
        
        # Cleanup
        test_dir.rmdir()

    def test_url_utils(self):
        """Test URLUtils functionality"""
        # Test URL cleaning
        dirty_url = "https://example.com/page?utm_source=test&utm_medium=test"
        clean_url = URLUtils.clean_url(dirty_url)
        assert "utm_" not in clean_url
        
        # Test URL validation
        assert URLUtils.is_valid_url("https://example.com")
        assert not URLUtils.is_valid_url("not_a_url")
        
        # Test domain extraction
        assert URLUtils.get_domain("https://example.com/page") == "example.com"

    @patch('socket.create_connection')
    def test_network_utils(self, mock_socket):
        """Test NetworkUtils functionality"""
        # Test connection check
        mock_socket.return_value = True
        assert NetworkUtils.check_connection()
        
        mock_socket.side_effect = OSError
        assert not NetworkUtils.check_connection()

class TestExceptions:
    def test_scraper_exception(self):
        """Test custom exceptions"""
        # Test base exception
        exc = ScraperException(
            message="Test error",
            error_code="TEST_ERROR",
            details={"test": "value"}
        )
        assert exc.error_code == "TEST_ERROR"
        assert "test" in exc.details
        
        # Test network error
        net_exc = NetworkError(
            message="Network error",
            url="https://example.com",
            status_code=404
        )
        assert net_exc.details["status_code"] == 404
        
        # Test conversion to dict
        exc_dict = handle_exception(net_exc)
        assert exc_dict["error_code"] == "NETWORK_ERROR"
        assert exc_dict["type"] == "NetworkError"

@pytest.mark.integration
class TestIntegration:
    """Integration tests for the complete workflow"""
    
    @pytest.fixture
    def test_config(self):
        """Test configuration"""
        return {
            'keywords': ['test query'],
            'output_dir': 'test_output',
            'max_retries': 1
        }

    @pytest.mark.asyncio
    async def test_complete_workflow(self, test_config):
        """Test complete scraping workflow"""
        # Setup
        output_dir = Path(test_config['output_dir'])
        output_dir.mkdir(exist_ok=True)
        
        try:
            scraper = WebScraper()
            
            # Test search
            urls = scraper.search_google(test_config['keywords'][0])
            assert isinstance(urls, list)
            
            # Test processing
            if urls:
                results = await scraper.process_urls(urls[:1])
                assert isinstance(results, list)
                
                # Test output
                scraper.save_results(results)
                assert any(output_dir.glob('*.json'))
                
        finally:
            # Cleanup
            scraper.close()
            if output_dir.exists():
                for file in output_dir.glob('*'):
                    file.unlink()
                output_dir.rmdir()

if __name__ == '__main__':
    pytest.main(['-v', __file__])