import asyncio
import json
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd

from web_scraper import WebScraper
from config import CONFIG, get_logger

logger = get_logger(__name__)

class ScrapingManager:
    def __init__(self):
        self.scraper = WebScraper()
        self.results: List[Dict[str, Any]] = []
        self.failed_items: List[Dict[str, Any]] = []
        self.start_time = datetime.now()

    async def process_keywords(self, keywords: List[str]):
        """Process a list of keywords by searching Google and scraping results"""
        all_urls = []
        
        for keyword in keywords:
            logger.info(f"Processing keyword: {keyword}")
            try:
                urls = self.scraper.search_google(keyword)
                if urls:
                    logger.info(f"Found {len(urls)} URLs for keyword: {keyword}")
                    all_urls.extend([{'url': url, 'keyword': keyword} for url in urls])
                else:
                    logger.warning(f"No URLs found for keyword: {keyword}")
                    self.failed_items.append({
                        'item': keyword,
                        'type': 'keyword',
                        'error': 'No URLs found',
                        'timestamp': datetime.now().isoformat()
                    })
            except Exception as e:
                logger.error(f"Error processing keyword {keyword}: {str(e)}")
                self.failed_items.append({
                    'item': keyword,
                    'type': 'keyword',
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                })

        if all_urls:
            await self.process_url_list([item['url'] for item in all_urls])
            # Add keyword information to results
            for result in self.results:
                matching_url = next((item for item in all_urls if item['url'] == result['url']), None)
                if matching_url:
                    result['keyword'] = matching_url['keyword']

    async def process_url_list(self, urls: List[str]):
        """Process a list of URLs directly"""
        results = await self.scraper.process_urls(urls)
        if results:
            self.results.extend(results)

    def save_final_report(self):
        """Save comprehensive final report"""
        try:
            timestamp = datetime.now().strftime(CONFIG['TIMESTAMP_FORMAT'])
            
            # Create report directory
            report_dir = Path(CONFIG['OUTPUT_DIR']) / 'reports' / timestamp
            report_dir.mkdir(parents=True, exist_ok=True)

            # Save successful results
            if self.results:
                # Excel format
                excel_path = report_dir / 'successful_results.xlsx'
                pd.DataFrame(self.results).to_excel(excel_path, index=False)
                
                # JSON format
                json_path = report_dir / 'successful_results.json'
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(self.results, f, ensure_ascii=False, indent=4)

            # Save failed items
            if self.failed_items:
                failed_path = report_dir / 'failed_items.json'
                with open(failed_path, 'w', encoding='utf-8') as f:
                    json.dump(self.failed_items, f, ensure_ascii=False, indent=4)

            # Generate summary report
            summary = {
                'start_time': self.start_time.isoformat(),
                'end_time': datetime.now().isoformat(),
                'total_duration': str(datetime.now() - self.start_time),
                'total_processed': len(self.results) + len(self.failed_items),
                'successful': len(self.results),
                'failed': len(self.failed_items),
                'success_rate': f"{(len(self.results) / (len(self.results) + len(self.failed_items)) * 100):.2f}%"
            }

            summary_path = report_dir / 'summary.json'
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=4)

            logger.info(f"Final report saved successfully in {report_dir}")
            logger.info(f"Success rate: {summary['success_rate']}")
            
            return report_dir

        except Exception as e:
            logger.error(f"Error saving final report: {str(e)}")
            return None

async def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Web scraping tool for keywords or URLs')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--keywords', type=str, help='Path to JSON file containing keywords')
    group.add_argument('--urls', type=str, help='Path to JSON file containing URLs')
    
    args = parser.parse_args()

    # Initialize scraping manager
    manager = ScrapingManager()
    
    try:
        if args.keywords:
            try:
                with open(args.keywords, 'r', encoding='utf-8') as f:
                    keywords = json.load(f)
                    if not isinstance(keywords, list):
                        raise ValueError("Keywords file must contain a JSON array")
                    
                logger.info(f"Loaded {len(keywords)} keywords from {args.keywords}")
                await manager.process_keywords(keywords)
                
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON format in keywords file: {args.keywords}")
                return
            except Exception as e:
                logger.error(f"Error loading keywords file: {str(e)}")
                return
                
        elif args.urls:
            try:
                with open(args.urls, 'r', encoding='utf-8') as f:
                    urls = json.load(f)
                    if not isinstance(urls, list):
                        raise ValueError("URLs file must contain a JSON array")
                    
                logger.info(f"Loaded {len(urls)} URLs from {args.urls}")
                await manager.process_url_list(urls)
                
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON format in URLs file: {args.urls}")
                return
            except Exception as e:
                logger.error(f"Error loading URLs file: {str(e)}")
                return

        # Save final report
        report_dir = manager.save_final_report()
        if report_dir:
            logger.info(f"Scraping completed. Reports saved in: {report_dir}")
        
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}")
    
    finally:
        # Cleanup
        try:
            manager.scraper.close()
            logger.info("Resources cleaned up successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")