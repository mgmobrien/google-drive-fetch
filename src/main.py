"""
Google Drive text file fetcher
----------------
See README
"""

import os
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
import warnings
from date_parser import parse_date_from_filename
from state import FileProcessor
from content import ContentFormatter
from drive import DriveClient
from config import Config
from stats import FetchStats

# Suppress oauth warning
warnings.filterwarnings('ignore', message='file_cache is only supported with oauth2client<4.0.0')

# Set up base directory and initialize config
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
config = Config(BASE_DIR)

# Create necessary directories
config.create_directories()

# Initialize components with config
file_processor = FileProcessor(config.state_file)
content_formatter = ContentFormatter()
drive_client = DriveClient(config.credentials_path)

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        RotatingFileHandler(
            os.path.join(config.log_dir, 'transcript_syncer.log'),
            maxBytes=1024*1024,  # 1MB per file
            backupCount=5        # Keep 5 backup files
        )
    ]
)

# Add error-only handler
error_handler = RotatingFileHandler(
    os.path.join(config.log_dir, 'launchd_err.log'),
    maxBytes=1024*1024,
    backupCount=5
)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.getLogger('').addHandler(error_handler)

def should_process_file(file_id, file_name, processed_files):
    # Skip if in state file
    if file_id in processed_files:
        return False

    date_obj = parse_date_from_filename(file_name)
    file_date = date_obj.strftime("%Y-%m-%d")

    # Skip if file already exists in any of the folders
    safe_filename = f"TS. {file_date} - {file_name.replace('/', '-').replace(':', '-')}.md"
    for path in config.folder_mappings.values():
        output_path = os.path.join(path, safe_filename)
        if os.path.exists(output_path):
            logging.info(f"File already exists locally: {safe_filename}")
            # Add to state file so we don't check again
            processed_files[file_id] = {
                'name': file_name,
                'processed_at': datetime.now().isoformat()
            }
            file_processor.save_processed_files(processed_files)
            return False

    return True

def main():
    stats = FetchStats()
    try:
        logging.info("Starting fetch")
        processed_files = file_processor.load_processed_files()

        for folder_id, download_path in config.folder_mappings.items():
            logging.info(f"Processing folder: {folder_id}")

            files = drive_client.list_files(folder_id)

            if not files:
                logging.info(f'No transcript files found in folder {folder_id}')
                continue

            logging.info(f'Found {len(files)} transcripts in folder {folder_id}')
            for file in files:
                try:
                    if not file or 'id' not in file or 'name' not in file:
                        logging.error("Invalid file object received from API")
                        stats.errors += 1
                        continue

                    file_id = file.get('id')
                    file_name = file.get('name')

                    if not file_id or not file_name:
                        logging.error("Missing required file attributes")
                        stats.errors += 1
                        continue

                    if not should_process_file(file_id, file_name, processed_files):
                        logging.info(f"Skipping file: {file_name}")
                        stats.files_skipped += 1
                        continue

                    logging.info(f"Processing new file: {file_name}")

                    date_obj = parse_date_from_filename(file_name)
                    file_date = date_obj.strftime("%Y-%m-%d")

                    # Create safe filename with new format
                    safe_filename = f"TS. {file_date} - {file_name.replace('/', '-').replace(':', '-')}.md"
                    output_path = os.path.join(download_path, safe_filename)

                    try:
                        content = drive_client.download_file(file_id, file.get('mimeType'))
                    except Exception as e:
                        logging.error(f"Error downloading file {file_name}: {e}")
                        stats.errors += 1
                        continue

                    final_content = content_formatter.create_note_content(content, file_name, folder_id)

                    try:
                        # Save markdown file
                        with open(output_path, 'wb') as f:
                            f.write(final_content.encode('utf-8'))
                        logging.info(f"Saved to: {output_path}")
                    except IOError as e:
                        logging.error(f"Failed to write file {file_name} to {output_path}: {e}")
                        stats.errors += 1
                        continue  # Skip state update if write failed

                    # Only update state if write succeeded
                    processed_files[file_id] = {
                        'name': file_name,
                        'processed_at': datetime.now().isoformat()
                    }
                    file_processor.save_processed_files(processed_files)
                    stats.files_processed += 1

                except Exception as e:
                    logging.error(f"Error processing file {file_name}: {e}")
                    stats.errors += 1
                    continue

    except Exception as e:
        logging.error(f"Error in fetch process: {e}", exc_info=True)
        stats.errors += 1
        # Don't re-raise the error - let the script continue running

    logging.info(stats.get_summary())
    logging.info("Fetch completed")

if __name__ == '__main__':
    main()
