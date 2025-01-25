"""
State management for tracking processed files
"""

import json
import logging
import time
import os

class FileProcessor:
    def __init__(self, state_file_path: str):
        self.state_file_path = state_file_path
        self.max_retries = 3
        self.retry_delay = 0.1  # seconds

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
                    logging.error(f"Error reading state file after {self.max_retries} attempts: {e}")
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
            logging.error(f"Error saving state file: {e}")
            if os.path.exists(temp_file):
                os.remove(temp_file)
            raise
