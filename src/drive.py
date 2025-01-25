"""
Google Drive interaction logic
"""

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError
import logging
import io

class DriveClient:
    def __init__(self, credentials_path: str):
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=['https://www.googleapis.com/auth/drive.readonly']
        )
        self.service = build('drive', 'v3', credentials=credentials)

    def list_files(self, folder_id: str):
        """List all transcript files in a folder"""
        query = f"'{folder_id}' in parents and (name contains 'Transcript' and (mimeType = 'application/vnd.google-apps.document' or mimeType = 'text/markdown'))"
        
        try:
            results = self.service.files().list(
                q=query,
                orderBy='createdTime desc',
                fields="files(id, name, mimeType)"
            ).execute()
            
            return results.get('files', [])
        except HttpError as e:
            logging.error(f"Error listing files: {e}")
            return []

    def download_file(self, file_id: str, mime_type: str) -> str:
        """Download a file's content"""
        try:
            if mime_type == 'text/markdown':
                request = self.service.files().get_media(fileId=file_id)
            else:
                request = self.service.files().export_media(
                    fileId=file_id,
                    mimeType='text/markdown'
                )

            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                logging.info(f"Download progress: {int(status.progress() * 100)}%")

            return fh.getvalue().decode('utf-8')

        except HttpError as e:
            if any(msg in str(e) for msg in ["Failed to establish a new connection", "Connection refused", "Unable to find the server"]):
                logging.error(f"Network connectivity issue downloading file {file_id}: {e}")
            else:
                logging.error(f"Google API error downloading file {file_id}: {e}")
            raise
