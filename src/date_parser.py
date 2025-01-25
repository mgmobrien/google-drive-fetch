"""
Date parsing utilities for transcript filenames
"""

from datetime import datetime
import logging
import re

def parse_date_from_filename(file_name: str) -> datetime:
    # Normalize all dashes and add debug logging
    normalized_name = file_name.replace('–', '-')
    logging.debug(f"Normalized filename: {normalized_name}")

    # First try format: "- 2024/11/26 12:58 PST -"
    try:
        parts = normalized_name.split(' - ')
        logging.debug(f"Split parts: {parts}")
        date_str = parts[1].split(' ')[0]
        logging.debug(f"Extracted date string: {date_str}")
        return datetime.strptime(date_str, "%Y/%m/%d")
    except Exception as e:
        logging.debug(f"First format parse failed: {e}")
        pass

    # Then try format: "(2024-07-11 15:23 GMT-7)"
    try:
        match = re.search(r'\((\d{4}-\d{2}-\d{2})', normalized_name)
        if match:
            date_str = match.group(1)
            logging.debug(f"Regex matched date: {date_str}")
            return datetime.strptime(date_str, "%Y-%m-%d")
    except Exception as e:
        logging.debug(f"Second format parse failed: {e}")
        pass

    # Try one more format: "– 2024/11/07" (anywhere in string)
    try:
        match = re.search(r'[–-]\s*(\d{4}/\d{2}/\d{2})', normalized_name)
        if match:
            date_str = match.group(1)
            logging.debug(f"Third format matched date: {date_str}")
            return datetime.strptime(date_str, "%Y/%m/%d")
    except Exception as e:
        logging.debug(f"Third format parse failed: {e}")
        pass

    # Try Dragon format: "Dragon & Matt - 2023/10/31"
    try:
        match = re.search(r'Dragon & Matt - (\d{4}/\d{2}/\d{2})', normalized_name)
        if match:
            date_str = match.group(1)
            logging.debug(f"Dragon format matched date: {date_str}")
            return datetime.strptime(date_str, "%Y/%m/%d")
    except Exception as e:
        logging.debug(f"Dragon format parse failed: {e}")
        pass

    logging.warning(f"Could not parse date from filename: {file_name}")
    return datetime.now()
