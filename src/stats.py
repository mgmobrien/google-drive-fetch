"""
Stats tracking for file retrieval (fetch) operations
"""

from datetime import datetime

class FetchStats:
    def __init__(self):
        self.files_processed = 0
        self.files_skipped = 0
        self.errors = 0
        self.start_time = datetime.now()

    def get_summary(self):
        duration = datetime.now() - self.start_time
        return f"""
Fetch Summary:
------------
Duration: {duration}
Files processed: {self.files_processed}
Files skipped: {self.files_skipped}
Errors: {self.errors}
"""
