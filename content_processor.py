import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from tqdm import tqdm
from colorama import Fore, Style
import time
import logging
import shutil
import os

from config import CONFIG, get_logger, STATUS_MESSAGES, PROGRESS_BAR_FORMAT
from web_scraper import WebScraper

logger = get_logger(__name__)

class ContentProcessor(WebScraper):
    def __init__(self):
        """Initialize ContentProcessor with necessary directories and configurations"""
        super().__init__()
        self.output_dir = CONFIG['OUTPUT_DIR']
        self.backup_dir = self.output_dir / 'backup'
        self.failed_dir = self.output_dir / 'failed'
        self.setup_directories()
        self.stats = {
            'processed_keywords': 0,
            'successful_searches': 0,
            'failed_searches': 0,
            'total_results': 0,
            'start_time': datetime.now(),
            'errors': []
        }

    def setup_directories(self):
        """Create necessary directories for output management"""
        directories = [
            self.output_dir,
            self.backup_dir,
            self.failed_dir,
            self.output_dir / 'json',
            self.output_dir / 'excel',
            self.output_dir / 'logs'
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created directory: {directory}")

    def backup_existing_files(self):
        """Backup existing result files before new processing"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_subdir = self.backup_dir / timestamp
            backup_subdir.mkdir(parents=True, exist_ok=True)

            # Move existing files to backup
            for ext in ['*.json', '*.xlsx']:
                for file in self.output_dir.glob(ext):
                    if file.is_file():
                        shutil.move(str(file), str(backup_subdir / file.name))
                        logger.debug(f"Backed up: {file.name}")

            logger.info(f"Previous results backed up to: {backup_subdir}")
        except Exception as e:
            logger.error(f"Backup error: {str(e)}")

    def process_result(self, result: Dict) -> Dict:
        """Process and enrich a single search result"""
        try:
            processed_data = {
                'title': result.get('title', '').strip(),
                'link': result.get('link', '').strip(),
                'description': result.get('description', '').strip(),
                'keyword': result.get('keyword', self.current_keyword),
                'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                'processing_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'source': result.get('source', 'Google Search'),
                'rank': result.get('rank', 0),
                'status': 'processed'
            }
            
            # Validate processed data
            if not processed_data['title'] or not processed_data['link']:
                logger.warning(f"Invalid result data: {processed_data}")
                return None
                
            return processed_data

        except Exception as e:
            logger.error(f"Error processing result: {str(e)}")
            self.stats['errors'].append(str(e))
            return None

    def process_keyword(self, keyword: str) -> List[Dict]:
        """Process a single keyword and return results"""
        logger.info(f"Processing keyword: {keyword}")
        self.stats['processed_keywords'] += 1
        results = []
        
        try:
            # Perform search
            search_results = self.search_google(keyword)
            
            if not search_results:
                logger.warning(f"No results found for keyword: {keyword}")
                self.stats['failed_searches'] += 1
                return results
            
            # Process each result
            for index, result in enumerate(search_results, 1):
                try:
                    result['rank'] = index
                    processed_result = self.process_result(result)
                    if processed_result:
                        results.append(processed_result)
                except Exception as e:
                    logger.error(f"Error processing result {index} for {keyword}: {str(e)}")
                    continue
            
            if results:
                self.stats['successful_searches'] += 1
                self.stats['total_results'] += len(results)
            
            return results

        except Exception as e:
            error_msg = f"Error processing keyword {keyword}: {str(e)}"
            logger.error(error_msg)
            self.stats['errors'].append(error_msg)
            self.stats['failed_searches'] += 1
            return []

    def save_results(self, keyword: str, results: List[Dict], retry: bool = True):
        """Save results to JSON and Excel files with retry mechanism"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Prepare output data
        output_data = {
            'keyword': keyword,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'results': results,
            'total_results': len(results),
            'processing_stats': {
                'duration': str(datetime.now() - self.stats['start_time']),
                'success_rate': f"{(self.stats['successful_searches'] / max(1, self.stats['processed_keywords'])) * 100:.2f}%"
            }
        }
        
        try:
            # Save JSON
            json_filename = self.output_dir / 'json' / f"results_{keyword}_{timestamp}.json"
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            
            # Save Excel with additional formatting
            df = pd.DataFrame(results)
            excel_filename = self.output_dir / 'excel' / f"results_{keyword}_{timestamp}.xlsx"
            
            with pd.ExcelWriter(excel_filename, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Results')
                
                # Get workbook and worksheet objects
                workbook = writer.book
                worksheet = writer.sheets['Results']
                
                # Add formats
                header_format = workbook.add_format({
                    'bold': True,
                    'text_wrap': True,
                    'valign': 'top',
                    'bg_color': '#D9EAD3',
                    'border': 1
                })
                
                # Format headers
                for col_num, value in enumerate(df.columns.values):
                    worksheet.write(0, col_num, value, header_format)
                    worksheet.set_column(col_num, col_num, 15)  # Set column width
                
                # Add summary sheet
                summary_df = pd.DataFrame([{
                    'Keyword': keyword,
                    'Total Results': len(results),
                    'Processing Time': output_data['processing_stats']['duration'],
                    'Success Rate': output_data['processing_stats']['success_rate'],
                    'Timestamp': output_data['timestamp']
                }])
                
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            logger.info(f"Results saved successfully:")
            logger.info(f"├── JSON: {json_filename.name}")
            logger.info(f"└── Excel: {excel_filename.name}")
            
        except Exception as e:
            error_msg = f"Error saving results for {keyword}: {str(e)}"
            logger.error(error_msg)
            
            if retry:
                logger.info("Retrying save operation...")
                time.sleep(2)
                return self.save_results(keyword, results, retry=False)
            else:
                # Save to failed directory as last resort
                failed_file = self.failed_dir / f"failed_{keyword}_{timestamp}.json"
                try:
                    with open(failed_file, 'w', encoding='utf-8') as f:
                        json.dump(output_data, f, ensure_ascii=False, indent=2)
                    logger.info(f"Results saved to failed directory: {failed_file.name}")
                except Exception as backup_error:
                    logger.error(f"Critical: Could not save to failed directory: {str(backup_error)}")

    def process_keywords(self, keywords: List[str]):
        """Process multiple keywords with progress tracking and error handling"""
        logger.info(STATUS_MESSAGES['start'])
        self.backup_existing_files()
        
        try:
            with tqdm(total=len(keywords), **PROGRESS_BAR_FORMAT) as self.progress_bar:
                for keyword in keywords:
                    try:
                        self.progress_bar.set_description(f"Processing: {keyword}")
                        results = self.process_keyword(keyword)
                        
                        if results:
                            self.save_results(keyword, results)
                            logger.info(f"Successfully processed keyword: {keyword}")
                        else:
                            logger.warning(f"No results found for keyword: {keyword}")
                        
                    except Exception as e:
                        error_msg = f"Error processing keyword {keyword}: {str(e)}"
                        logger.error(error_msg)
                        self.stats['errors'].append(error_msg)
                        continue
                    
                    finally:
                        self.progress_bar.update(1)
                        time.sleep(0.1)  # Prevent GUI flicker
            
            self.save_processing_stats()
            logger.info(STATUS_MESSAGES['complete'])
            
        except KeyboardInterrupt:
            logger.warning("Processing interrupted by user")
            self.save_processing_stats()
            raise
        
        except Exception as e:
            logger.error(f"Critical error in process_keywords: {str(e)}")
            self.save_processing_stats()
            raise

    def save_processing_stats(self):
        """Save processing statistics to a log file"""
        try:
            stats_file = self.output_dir / 'logs' / f"processing_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            final_stats = {
                **self.stats,
                'end_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'total_duration': str(datetime.now() - self.stats['start_time']),
                'success_rate': f"{(self.stats['successful_searches'] / max(1, self.stats['processed_keywords'])) * 100:.2f}%"
            }
            
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(final_stats, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Processing statistics saved to: {stats_file.name}")
            
        except Exception as e:
            logger.error(f"Error saving processing stats: {str(e)}")

    def cleanup(self):
        """Cleanup temporary files and resources"""
        try:
            # Cleanup code here if needed
            logger.info("Cleanup completed successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")

    def __del__(self):
        """Destructor to ensure proper cleanup"""
        self.cleanup()
        super().__del__()