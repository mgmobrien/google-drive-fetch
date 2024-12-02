"""
Transcript Syncer
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
import json
import warnings
import time

# Suppress oauth warning
warnings.filterwarnings('ignore', message='file_cache is only supported with oauth2client<4.0.0')

# Set up base directory and paths
BASE_DIR = '/Users/mattobrien/Documents/Projects/transcript-syncer'
LOG_DIR = f'{BASE_DIR}/logs'
STATE_FILE = f'{BASE_DIR}/state/processed_files.json'
CREDENTIALS_PATH = f'{BASE_DIR}/credentials/transcript-syncer-131b6cd620c8.json'

FOLDER_MAPPINGS = {
    "108_9MeB539PK6NVEjgARZuQKfms_PPt0": "/Users/mattobrien/Obsidian Main Vault/ObsidianVault/-No Instructions/User testing/Transcripts",  # Customer Calls
    "1FsPM-xB7EH6Fc2CCu67EHDhYMotx0EYc": "/Users/mattobrien/Obsidian Main Vault/ObsidianVault/Oceano/Principals/Dragon/=Dragon & Matt/Transcripts",  # Dragon
    "1EiScFFGiE6hdKBOZeSicnO_lxv2U3mcB": "/Users/mattobrien/Obsidian Main Vault/ObsidianVault/-No Instructions/Daily/Transcripts",  # Meetings
}

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
        logging.FileHandler(os.path.join(LOG_DIR, 'transcript_syncer.log'))
    ]
)

# Add error-only handler
error_handler = logging.FileHandler(os.path.join(LOG_DIR, 'launchd_err.log'))
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.getLogger('').addHandler(error_handler)

def should_process_file(file_id, file_name, processed_files):
    # Skip if in state file
    if file_id in processed_files:
        return False

    # Parse date from filename for new naming convention
    try:
        date_str = file_name.split(' - ')[1].split(' ')[0]  # Gets "2024/11/12"
        date_obj = datetime.strptime(date_str, "%Y/%m/%d")
        file_date = date_obj.strftime("%Y-%m-%d")
    except:
        file_date = datetime.now().strftime("%Y-%m-%d")

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
            save_processed_files(processed_files)
            return False

    return True

def load_processed_files():
    """Load state file with retry logic for potential race conditions"""
    max_retries = 3
    retry_delay = 0.1  # seconds

    for attempt in range(max_retries):
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, 'r') as f:
                    content = f.read().strip()
                    if not content:
                        return {}
                    return json.loads(content)
            return {}
        except (json.JSONDecodeError, IOError) as e:
            if attempt == max_retries - 1:  # Last attempt
                logging.error(f"Error reading state file after {max_retries} attempts: {e}")
                return {}
            time.sleep(retry_delay)
            continue

def save_processed_files(processed):
    """Safely write state file using atomic write pattern"""
    temp_file = STATE_FILE + '.tmp'
    try:
        with open(temp_file, 'w') as f:
            json.dump(processed, f, indent=2)  # Added indent for readability
        os.replace(temp_file, STATE_FILE)  # Atomic operation
    except Exception as e:
        logging.error(f"Error saving state file: {e}")
        if os.path.exists(temp_file):
            os.remove(temp_file)
        raise

def create_note_content(original_content, file_name, folder_id):
    timestamp = datetime.now().strftime("%Y-%m-%d %H.%M.%S")

    # Extract date from file name
    try:
        date_str = file_name.split(' - ')[1].split(' ')[0]  # Gets "2024/11/12"
        date_obj = datetime.strptime(date_str, "%Y/%m/%d")
        daily_note_date = date_obj.strftime("%Y-%m-%d")
        day_abbr = date_obj.strftime("%a")  # Gets Mon, Tue, etc.
    except:
        daily_note_date = datetime.now().strftime("%Y-%m-%d")
        day_abbr = datetime.now().strftime("%a")

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
    try:
        logging.info("Starting transcript sync")
        processed_files = load_processed_files()

        credentials = service_account.Credentials.from_service_account_file(
            CREDENTIALS_PATH,
            scopes=['https://www.googleapis.com/auth/drive.readonly']
        )

        service = build('drive', 'v3', credentials=credentials)

        for folder_id, download_path in FOLDER_MAPPINGS.items():
            logging.info(f"Processing folder: {folder_id}")

            query = f"'{folder_id}' in parents and name contains 'Transcript' and mimeType = 'application/vnd.google-apps.document'"

            results = service.files().list(
                q=query,
                orderBy='createdTime desc',
                fields="files(id, name, mimeType)",
                pageSize=3
            ).execute()

            files = results.get('files', [])

            if not files:
                logging.info(f'No transcript files found in folder {folder_id}')
                continue

            logging.info(f'Found {len(files)} transcripts in folder {folder_id}')
            for file in files:
                try:
                    file_id = file['id']

                    if not should_process_file(file_id, file['name'], processed_files):
                        logging.info(f"Skipping file: {file['name']}")
                        continue

                    logging.info(f"Processing new file: {file['name']}")

                    # Parse date from filename for new naming convention
                    try:
                        date_str = file['name'].split(' - ')[1].split(' ')[0]  # Gets "2024/11/12"
                        date_obj = datetime.strptime(date_str, "%Y/%m/%d")
                        file_date = date_obj.strftime("%Y-%m-%d")
                    except:
                        file_date = datetime.now().strftime("%Y-%m-%d")

                    # Create safe filename with new format
                    safe_filename = f"TS. {file_date} - {file['name'].replace('/', '-').replace(':', '-')}.md"
                    output_path = os.path.join(download_path, safe_filename)

                    try:
                        # Download markdown version
                        request = service.files().export_media(
                            fileId=file['id'],
                            mimeType='text/markdown'
                        )
                        fh = io.BytesIO()
                        downloader = MediaIoBaseDownload(fh, request)
                        done = False
                        while done is False:
                            status, done = downloader.next_chunk()
                            logging.info(f"Download progress: {int(status.progress() * 100)}%")
                    except HttpError as e:
                        logging.error(f"Google API error processing file {file['name']}: {e}")
                        continue

                    # Get content and add our header
                    content = fh.getvalue().decode('utf-8')
                    final_content = create_note_content(content, file['name'], folder_id)

                    # Save markdown file
                    with open(output_path, 'wb') as f:
                        f.write(final_content.encode('utf-8'))

                    logging.info(f"Saved to: {output_path}")

                    processed_files[file_id] = {
                        'name': file['name'],
                        'processed_at': datetime.now().isoformat()
                    }
                    save_processed_files(processed_files)

                except Exception as e:
                    logging.error(f"Error processing file {file['name']}: {e}")
                    continue

    except Exception as e:
        logging.error(f"Error in main sync process: {e}", exc_info=True)
        # Don't re-raise the error - let the script continue running

    logging.info("Sync completed")

if __name__ == '__main__':
    main()
