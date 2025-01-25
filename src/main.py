"""
Google Drive text file fetcher
----------------
See README
"""

from google.oauth2 import service_account
from googleapiclient.discovery import build
import os
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError
import io
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
import json
import warnings
import time
import re
import yaml
from date_parser import parse_date_from_filename
from state import FileProcessor

# Suppress oauth warning
warnings.filterwarnings('ignore', message='file_cache is only supported with oauth2client<4.0.0')

# Load config
try:
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
except FileNotFoundError:
    raise FileNotFoundError("config.yaml not found. Please copy config.example.yaml to config.yaml and update with your settings.")

# Set up base directory and paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, 'logs')
STATE_FILE = os.path.join(BASE_DIR, 'state', 'processed_files.json')
CREDENTIALS_PATH = os.path.join(BASE_DIR, config['credentials']['service_account_path'])

# Create file processor
file_processor = FileProcessor(STATE_FILE)

# Get folder mappings from config
FOLDER_MAPPINGS = {
    folder_config['google_drive_id']: folder_config['local_path']
    for folder_config in config['folders'].values()
}

class SyncStats:
    def __init__(self):
        self.files_processed = 0
        self.files_skipped = 0
        self.errors = 0
        self.start_time = datetime.now()

    def get_summary(self):
        duration = datetime.now() - self.start_time
        return f"""
Sync Summary:
------------
Duration: {duration}
Files processed: {self.files_processed}
Files skipped: {self.files_skipped}
Errors: {self.errors}
"""

# Create necessary directories
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
for path in FOLDER_MAPPINGS.values():
    os.makedirs(path, exist_ok=True)

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        RotatingFileHandler(
            os.path.join(LOG_DIR, 'transcript_syncer.log'),
            maxBytes=1024*1024,  # 1MB per file
            backupCount=5        # Keep 5 backup files
        )
    ]
)

# Add error-only handler
error_handler = RotatingFileHandler(
    os.path.join(LOG_DIR, 'launchd_err.log'),
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
    for path in FOLDER_MAPPINGS.values():
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

def create_note_content(original_content, file_name, folder_id):
    timestamp = datetime.now().strftime("%Y-%m-%d %H.%M.%S")

    date_obj = parse_date_from_filename(file_name)
    daily_note_date = date_obj.strftime("%Y-%m-%d")
    day_abbr = date_obj.strftime("%a")

    # Different related notes based on folder
    if folder_id == "1FsPM-xB7EH6Fc2CCu67EHDhYMotx0EYc":  # Dragon
        related_notes = "[[Dashboard. Dragon]]"
    elif folder_id == "1EiScFFGiE6hdKBOZeSicnO_lxv2U3mcB":  # Meetings
        related_notes = f"[[No {daily_note_date} {day_abbr}]]"
    else:  # Customer calls
        related_notes = "[[S3. Establish and maintain user testing pipeline]]"

    header = f'''*Created by [[Transcript Syncer]] at {timestamp}*

> [!-cf-]+ [[Related notes]]
> - {related_notes}




---

'''
    return header + original_content

def main():
    stats = SyncStats()
    try:
        logging.info("Starting transcript sync")
        processed_files = file_processor.load_processed_files()

        credentials = service_account.Credentials.from_service_account_file(
            CREDENTIALS_PATH,
            scopes=['https://www.googleapis.com/auth/drive.readonly']
        )

        service = build('drive', 'v3', credentials=credentials)

        for folder_id, download_path in FOLDER_MAPPINGS.items():
            logging.info(f"Processing folder: {folder_id}")

            query = f"'{folder_id}' in parents and (name contains 'Transcript' and (mimeType = 'application/vnd.google-apps.document' or mimeType = 'text/markdown'))"

            results = service.files().list(
                q=query,
                orderBy='createdTime desc',
                fields="files(id, name, mimeType)"
            ).execute()

            files = results.get('files', [])

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
                        # Download based on mime type
                        if file.get('mimeType') == 'text/markdown':
                            request = service.files().get_media(fileId=file_id)
                        else:
                            request = service.files().export_media(
                                fileId=file_id,
                                mimeType='text/markdown'
                            )
                        fh = io.BytesIO()
                        downloader = MediaIoBaseDownload(fh, request)
                        done = False
                        while done is False:
                            status, done = downloader.next_chunk()
                            logging.info(f"Download progress: {int(status.progress() * 100)}%")
                    except HttpError as e:
                        if "Failed to establish a new connection" in str(e) or "Connection refused" in str(e) or "Unable to find the server" in str(e):
                            logging.error(f"Network connectivity issue while processing {file_name}: {e}")
                        else:
                            logging.error(f"Google API error processing file {file_name}: {e}")
                        stats.errors += 1
                        continue

                    # Get content and add our header
                    content = fh.getvalue().decode('utf-8')
                    final_content = create_note_content(content, file_name, folder_id)

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
        logging.error(f"Error in main sync process: {e}", exc_info=True)
        stats.errors += 1
        # Don't re-raise the error - let the script continue running

    logging.info(stats.get_summary())
    logging.info("Sync completed")

if __name__ == '__main__':
    main()