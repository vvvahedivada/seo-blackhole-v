import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import logging
import os
from pathlib import Path
import json
import time
import random

from config import CONFIG, get_logger

logger = get_logger(__name__)

class ContentScraper:
    def __init__(self):
        self.output_dir = Path(CONFIG['OUTPUT_DIR'])
        self.content_dir = self.output_dir / "content"
        self.content_dir.mkdir(parents=True, exist_ok=True)

    def fetch_page_content(self, url):
        """دریافت محتوای صفحه از طریق URL"""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(url, headers=headers, timeout=CONFIG['TIMEOUT'])
            response.raise_for_status()
            time.sleep(random.uniform(1, 3))
            return response.text
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching {url}: {str(e)}")
            return None

    def extract_content(self, html_content, url):
        """استخراج محتوای صفحه از HTML"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # استخراج عنوان صفحه
            title = soup.title.string if soup.title else "No Title"
            title = title.strip()
            
            # استخراج متن اصلی صفحه
            paragraphs = []
            for p in soup.find_all('p'):
                text = p.get_text().strip()
                if text:  # فقط پاراگراف‌های غیر خالی
                    paragraphs.append(text)
            text_content = "\n\n".join(paragraphs)
            
            # استخراج هدینگ‌ها
            headings = {}
            for i in range(1, 7):
                headings[f'h{i}'] = [h.get_text().strip() for h in soup.find_all(f'h{i}') if h.get_text().strip()]
            
            # استخراج لینک‌های داخلی
            internal_links = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                if href.startswith('/') or href.startswith(url):
                    internal_links.append(href)
            
            # استخراج تصاویر با alt text
            images = []
            for img in soup.find_all('img', src=True):
                img_data = {
                    'src': img['src'],
                    'alt': img.get('alt', '').strip()
                }
                images.append(img_data)
            
            # استخراج جدول‌ها
            tables = []
            for table in soup.find_all('table'):
                tables.append(str(table))
            
            return {
                'url': url,
                'title': title,
                'text_content': text_content,
                'headings': headings,
                'internal_links': internal_links,
                'images': images,
                'tables': tables,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {str(e)}")
            return None

    def save_content_to_excel(self, url, content, excel_file):
        """ذخیره محتوای استخراج شده در فایل اکسل"""
        try:
            if not content:
                logger.warning(f"No content to save for {url}")
                return

            data = {
                'URL': [url],
                'Title': [content['title']],
                'Text Content': [content['text_content']],
                'Headings': [json.dumps(content['headings'], ensure_ascii=False)],
                'Internal Links': [json.dumps(content['internal_links'], ensure_ascii=False)],
                'Images': [json.dumps(content['images'], ensure_ascii=False)],
                'Tables': [json.dumps(content['tables'], ensure_ascii=False)],
                'Timestamp': [content['timestamp']]
            }
            df = pd.DataFrame(data)
            
            excel_path = Path(excel_file)
            if excel_path.exists():
                try:
                    existing_df = pd.read_excel(excel_path)
                    # حذف ردیف‌های تکراری بر اساس URL
                    existing_df = existing_df[existing_df['URL'] != url]
                    df = pd.concat([existing_df, df], ignore_index=True)
                except Exception as e:
                    logger.error(f"Error reading existing Excel file: {str(e)}")
                    # اگر خواندن فایل موجود با مشکل مواجه شد، فقط داده‌های جدید را ذخیره می‌کنیم
            
            df.to_excel(excel_path, index=False, engine='openpyxl')
            logger.info(f"Content saved to {excel_file}")
        except Exception as e:
            logger.error(f"Error saving content to Excel: {str(e)}")

    def scrape_content_from_url(self, url, excel_file):
        """اسکرپ محتوای یک URL و ذخیره در اکسل"""
        try:
            logger.info(f"Scraping content from: {url}")
            html_content = self.fetch_page_content(url)
            if html_content:
                content = self.extract_content(html_content, url)
                if content:
                    self.save_content_to_excel(url, content, excel_file)
                    return True
            return False
        except Exception as e:
            logger.error(f"Error scraping content from {url}: {str(e)}")
            return False

    def scrape_content_from_excel(self, input_excel_file, output_excel_file):
        """اسکرپ محتوای لینک‌ها از یک فایل اکسل"""
        try:
            logger.info(f"Reading links from: {input_excel_file}")
            df = pd.read_excel(input_excel_file)
            
            if 'link' in df.columns:
                unique_links = df['link'].unique()
                total_links = len(unique_links)
                logger.info(f"Found {total_links} unique links to process")
                
                for index, url in enumerate(unique_links, 1):
                    logger.info(f"Processing link {index}/{total_links}: {url}")
                    success = self.scrape_content_from_url(url, output_excel_file)
                    if success:
                        time.sleep(random.uniform(2, 4))  # تاخیر بین درخواست‌های موفق
                
                logger.info("Content scraping completed successfully")
            else:
                logger.error("Column 'link' not found in the Excel file")
                
        except Exception as e:
            logger.error(f"Error processing Excel file: {str(e)}")