"""
State management for tracking processed files
"""

import json
import logging
import time
import os
from datetime import datetime
from date_parser import parse_date_from_filename
from logger import setup_logging

class FileProcessor:
    def __init__(self, state_file_path: str):
        self.state_file_path = state_file_path
        self.max_retries = 3
        self.retry_delay = 0.1  # seconds
        self.logger = setup_logging(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/logs')

    def load_processed_files(self):
        """Load state file with retry logic for potential race conditions"""
        for attempt in range(self.max_retries):
            try:
                if os.path.exists(self.state_file_path):
                    with open(self.state_file_path, 'r') as f:
                        content = f.read().strip()
                        if not content:
                            return {}
                        return json.loads(content)
                return {}
            except (json.JSONDecodeError, IOError) as e:
                if attempt == self.max_retries - 1:  # Last attempt
                    self.logger.error(f"Error reading state file after {self.max_retries} attempts: {e}")
                    return {}
                time.sleep(self.retry_delay)
                continue

    def save_processed_files(self, processed):
        """Safely write state file using atomic write pattern"""
        temp_file = self.state_file_path + '.tmp'
        try:
            with open(temp_file, 'w') as f:
                json.dump(processed, f, indent=2)  # Added indent for readability
            os.replace(temp_file, self.state_file_path)  # Atomic operation
        except Exception as e:
            self.logger.error(f"Error saving state file: {e}")
            if os.path.exists(temp_file):
                os.remove(temp_file)
            raise

    def should_process_file(self, file_id: str, file_name: str, folder_mappings: dict) -> bool:
        """Determine if a file needs processing based on state and existing files"""
        processed_files = self.load_processed_files()

        # Skip if in state file
        if file_id in processed_files:
            return False

        date_obj = parse_date_from_filename(file_name)
        file_date = date_obj.strftime("%Y-%m-%d")

        # Skip if file exists in any folders
        safe_filename = f"TS. {file_date} - {file_name.replace('/', '-').replace(':', '-')}.md"
        for path in folder_mappings.values():
            output_path = os.path.join(path, safe_filename)
            if os.path.exists(output_path):
                self.logger.info(f"File already exists locally: {safe_filename}")
                # Add to state file
                processed_files[file_id] = {
                    'name': file_name,
                    'processed_at': datetime.now().isoformat()
                }
                self.save_processed_files(processed_files)
                return False

        return True
