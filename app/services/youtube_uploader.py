import asyncio
import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from app.services.client import logger

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

class YouTubeUploader:
    def __init__(self, secrets_file='client_secrets.json', token_file='token.pickle'):
        self.secrets_file = secrets_file
        self.token_file = token_file
        self.youtube = None

    def _get_service(self):
        """Internal helper to get/refresh the service safely inside a thread."""
        creds = None
        if os.path.exists(self.token_file):
            with open(self.token_file, 'rb') as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # WARNING: This will open a browser window on the server machine
                flow = InstalledAppFlow.from_client_secrets_file(self.secrets_file, SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open(self.token_file, 'wb') as token:
                pickle.dump(creds, token)

        return build('youtube', 'v3', credentials=creds)

    async def upload_video(self, file_path, title, description, tags, category_id="27"):
        """Entry point: Runs the blocking upload logic in a separate thread."""
        return await asyncio.to_thread(
            self._upload_video_sync,
            file_path,
            title,
            description,
            tags,
            category_id,
        )

    def _upload_video_sync(self, file_path, title, description, tags, category_id):
        # Initialize service INSIDE the thread to avoid blocking the main event loop
        if not self.youtube:
            self.youtube = self._get_service()

        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags.split(',') if isinstance(tags, str) else tags,
                'categoryId': category_id
            },
            'status': {
                'privacyStatus': 'private', # Good for testing; change to 'public' when ready
                'selfDeclaredMadeForKids': False,
                'selfDeclaredAlteredContent': True,
            }
        }

        logger.info(f"YouTube upload starting: {file_path}")

        insert_request = self.youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=MediaFileUpload(file_path, chunksize=-1, resumable=True)
        )

        response = None
        while response is None:
            status, response = insert_request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                logger.info(f"Upload progress: {progress}%")

        video_id = response.get("id")
        return f"https://www.youtube.com/watch?v={video_id}"