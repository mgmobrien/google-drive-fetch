"""
Logging configuration for fetch operations
"""

import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logging(log_dir: str):
    """Configure logging with both general and error-specific handlers"""
    
    # Create log directory if it doesn't exist
    os.makedirs(log_dir, exist_ok=True)
    
    # Set up main logger
    logging.basicConfig(
        format='%(asctime)s - %(levelname)s - %(message)s',
        level=logging.INFO,
        handlers=[
            RotatingFileHandler(
                os.path.join(log_dir, 'transcript_syncer.log'),
                maxBytes=1024*1024,  # 1MB per file
                backupCount=5        # Keep 5 backup files
            )
        ]
    )

    # Add error-only handler
    error_handler = RotatingFileHandler(
        os.path.join(log_dir, 'launchd_err.log'),
        maxBytes=1024*1024,
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logging.getLogger('').addHandler(error_handler)

    return logging.getLogger(__name__)
