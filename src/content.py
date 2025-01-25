"""
Content creation and formatting for markdown files
"""

from datetime import datetime
from date_parser import parse_date_from_filename

class ContentFormatter:
    def __init__(self):
        self.folder_mappings = {
            "1FsPM-xB7EH6Fc2CCu67EHDhYMotx0EYc": "[[Dashboard. Dragon]]",  # Dragon
            "1EiScFFGiE6hdKBOZeSicnO_lxv2U3mcB": lambda date: f"[[No {date} {date.strftime('%a')}]]",  # Meetings
            "default": "[[S3. Establish and maintain user testing pipeline]]"  # Customer calls
        }

    def create_note_content(self, original_content: str, file_name: str, folder_id: str) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H.%M.%S")
        date_obj = parse_date_from_filename(file_name)
        daily_note_date = date_obj.strftime("%Y-%m-%d")

        # Get related notes based on folder
        related_notes = self.folder_mappings.get(folder_id, self.folder_mappings["default"])
        if callable(related_notes):
            related_notes = related_notes(date_obj)

        header = f'''*Created by [[Transcript Syncer]] at {timestamp}*

> [!-cf-]+ [[Related notes]]
> - {related_notes}




---

'''
        return header + original_content
