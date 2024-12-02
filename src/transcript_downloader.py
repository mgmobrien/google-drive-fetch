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

# Suppress oauth warning
warnings.filterwarnings('ignore', message='file_cache is only supported with oauth2client<4.0.0')

# Set up base directory and paths
BASE_DIR = '/Users/mattobrien/Documents/Projects/transcript-syncer'
LOG_DIR = f'{BASE_DIR}/logs'
STATE_FILE = f'{BASE_DIR}/state/processed_files.json'
CREDENTIALS_PATH = f'{BASE_DIR}/credentials/transcript-syncer-131b6cd620c8.json'
DOWNLOADS_DIR = '/Users/mattobrien/Documents/Projects/transcript-syncer/downloads/Customer Calls Transcripts'

# Create necessary directories
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

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

FOLDER_ID = "108_9MeB539PK6NVEjgARZuQKfms_PPt0"  # CUSTOMER_FOLDER_ID

def should_process_file(file_id, file_name, processed_files):
    # Skip if in state file
    if file_id in processed_files:
        return False

    # Skip if file already exists
    safe_filename = "Transcript. " + file_name.replace('/', '-').replace(':', '-') + '.md'
    output_path = os.path.join(DOWNLOADS_DIR, safe_filename)
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
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                content = f.read().strip()
                if not content:  # File is empty
                    logging.info("State file is empty, starting fresh")
                    return {}
                try:
                    return json.load(f)
                except json.JSONDecodeError as e:
                    logging.error(f"Error parsing state file: {e}")
                    logging.error(f"State file content: {content[:200]}...")  # Log first 200 chars
                    # Instead of crashing, back up the corrupt file and start fresh
                    backup_path = f"{STATE_FILE}.backup"
                    os.rename(STATE_FILE, backup_path)
                    logging.info(f"Backed up potentially corrupt state file to {backup_path}")
                    return {}
        return {}
    except Exception as e:
        logging.error(f"Unexpected error reading state file: {e}")
        return {}  # Continue with empty state rather than crashing

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

def create_note_content(original_content):
    # Get current time for the creation timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H.%M.%S")

    # Create the header content
    header = f'''*Created by [[Transcript Syncer]] at {timestamp}*

> [!-cf-]+ [[Related notes]]
> - [[S3. Establish and maintain user testing pipeline]]




---

'''
    # Combine header with original content
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

        query = f"'{FOLDER_ID}' in parents and name contains 'Transcript' and mimeType = 'application/vnd.google-apps.document'"

        results = service.files().list(
            q=query,
            orderBy='createdTime desc',
            fields="files(id, name, mimeType)"
        ).execute()

        files = results.get('files', [])

        if not files:
            logging.info('No transcript files found.')
        else:
            logging.info(f'Found {len(files)} transcripts')
            for file in files:
                try:
                    file_id = file['id']

                    if not should_process_file(file_id, file['name'], processed_files):
                        logging.info(f"Skipping file: {file['name']}")
                        continue

                    logging.info(f"Processing new file: {file['name']}")

                    # Create safe filename
                    safe_filename = "Transcript. " + file['name'].replace('/', '-').replace(':', '-') + '.md'
                    output_path = os.path.join(DOWNLOADS_DIR, safe_filename)

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

                    # Get content and add our header
                    content = fh.getvalue().decode('utf-8')
                    final_content = create_note_content(content)

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
