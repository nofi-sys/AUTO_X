import os
import logging
import io
from typing import Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload, MediaFileUpload, MediaIoBaseDownload
from config import load_google_drive_workspace_id

# Configure logging
logger = logging.getLogger(__name__)

# --- Constants ---
# This scope allows the app to see, edit, create, and delete all of your
# files in Google Drive. For a real-world app, you might want to use a
# more restrictive scope like 'drive.file'.
SCOPES = ["https://www.googleapis.com/auth/drive"]
CREDENTIALS_FILE = "credentials.json"
GOOGLE_TOKEN_FILE = "google_token.json"
WORKSPACE_FOLDER_NAME = "AUTO_X_Workspace"
WORKSPACE_FOLDER_ID = load_google_drive_workspace_id()


def get_drive_service() -> Optional[Resource]:
    """
    Authenticate with Google Drive and return a service object.

    Handles the OAuth 2.0 flow, including token storage and refresh.
    Returns a Google Drive API v3 service object if successful, else None.
    """
    creds = None

    # --- Load existing token ---
    if os.path.exists(GOOGLE_TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN_FILE, SCOPES)
        except Exception as e:
            logger.error(f"Failed to load token from {GOOGLE_TOKEN_FILE}: {e}")
            creds = None

    # --- If no valid credentials, start the auth flow ---
    if not creds or not creds.valid:
        # --- Handle token refresh ---
        if creds and creds.expired and creds.refresh_token:
            logger.info("Google token has expired. Refreshing...")
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.error(f"Failed to refresh Google token: {e}")
                # If refresh fails, we'll need to re-authenticate
                creds = None
        # --- Handle initial authentication ---
        else:
            logger.info("Starting new Google Drive authentication flow.")
            if not os.path.exists(CREDENTIALS_FILE):
                logger.error(f"Credentials file not found at: {CREDENTIALS_FILE}")
                # We can't proceed without it.
                return None

            try:
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                # This will open a browser window for the user to authorize
                creds = flow.run_local_server(port=0)
            except Exception as e:
                logger.error(f"Failed to run authentication flow: {e}")
                return None

        # --- Save the credentials for the next run ---
        if creds:
            try:
                with open(GOOGLE_TOKEN_FILE, "w") as token_file:
                    token_file.write(creds.to_json())
                logger.info(f"Google token saved to {GOOGLE_TOKEN_FILE}")
            except IOError as e:
                logger.error(f"Failed to save Google token: {e}")

    # --- Build and return the service object ---
    if creds and creds.valid:
        try:
            service = build("drive", "v3", credentials=creds)
            logger.info("Google Drive service created successfully.")
            return service
        except Exception as e:
            logger.error(f"Failed to build Google Drive service: {e}")
    return None


def get_or_create_workspace_folder(drive_service: Resource) -> Optional[str]:
    """
    Find the app's workspace folder in Google Drive, creating it if it doesn't exist.

    Args:
        drive_service: An authenticated Google Drive API service object.

    Returns:
        The ID of the workspace folder, or None if an error occurs.
    """
    try:
        if WORKSPACE_FOLDER_ID:
            try:
                drive_service.files().get(fileId=WORKSPACE_FOLDER_ID, fields="id").execute()
                logger.info(f"Using configured workspace folder ID: {WORKSPACE_FOLDER_ID}")
                return WORKSPACE_FOLDER_ID
            except HttpError as e:
                logger.error(
                    f"Configured workspace folder ID '{WORKSPACE_FOLDER_ID}' is not accessible: {e}"
                )
                # Fall back to searching by name.
            except Exception as e:
                logger.error(
                    f"Unexpected error while validating configured folder ID '{WORKSPACE_FOLDER_ID}': {e}"
                )
                # Fall back to searching by name.

        # --- Search for the folder ---
        query = (
            f"mimeType='application/vnd.google-apps.folder' and "
            f"name='{WORKSPACE_FOLDER_NAME}' and trashed=false"
        )
        response = drive_service.files().list(q=query, spaces="drive", fields="files(id, name)").execute()
        files = response.get("files", [])

        if files:
            folder_id = files[0].get("id")
            logger.info(f"Found workspace folder '{WORKSPACE_FOLDER_NAME}' with ID: {folder_id}")
            return folder_id
        else:
            # --- Create the folder if it doesn't exist ---
            logger.info(f"Workspace folder '{WORKSPACE_FOLDER_NAME}' not found. Creating it...")
            file_metadata = {
                "name": WORKSPACE_FOLDER_NAME,
                "mimeType": "application/vnd.google-apps.folder",
            }
            folder = drive_service.files().create(body=file_metadata, fields="id").execute()
            folder_id = folder.get("id")
            logger.info(f"Created workspace folder '{WORKSPACE_FOLDER_NAME}' with ID: {folder_id}")
            return folder_id

    except HttpError as e:
        logger.error(f"An error occurred while accessing Google Drive: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return None


def find_file_in_folder(drive_service: Resource, filename: str, folder_id: str) -> Optional[str]:
    """Find a file by name within a specific folder and return its ID."""
    try:
        query = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
        response = drive_service.files().list(q=query, spaces="drive", fields="files(id)").execute()
        files = response.get("files", [])
        return files[0]["id"] if files else None
    except HttpError as e:
        logger.error(f"Error finding file '{filename}': {e}")
        return None


def read_file_content(drive_service: Resource, file_id: str) -> Optional[str]:
    """Read the content of a file from Google Drive."""
    try:
        request = drive_service.files().get_media(fileId=file_id)
        content = request.execute().decode("utf-8")
        return content
    except HttpError as e:
        logger.error(f"Error reading file content for file ID '{file_id}': {e}")
        return None


def write_file_content(drive_service: Resource, filename: str, content: str, folder_id: str, file_id: Optional[str] = None) -> Optional[str]:
    """Write content to a file in Google Drive, creating it if it doesn't exist."""
    try:
        file_metadata = {"name": filename, "parents": [folder_id]}
        media = io.BytesIO(content.encode("utf-8"))
        media_body = MediaIoBaseUpload(media, mimetype="application/json", resumable=True)

        if file_id:
            # Update existing file
            updated_file = drive_service.files().update(
                fileId=file_id,
                body=file_metadata,
                media_body=media_body,
                fields="id"
            ).execute()
            logger.info(f"Updated file '{filename}' with ID: {updated_file['id']}")
            return updated_file["id"]
        else:
            # Create new file
            created_file = drive_service.files().create(
                body=file_metadata,
                media_body=media_body,
                fields="id"
            ).execute()
            logger.info(f"Created file '{filename}' with ID: {created_file['id']}")
            return created_file["id"]
    except HttpError as e:
        logger.error(f"Error writing file '{filename}': {e}")
        return None


def upload_image(drive_service: Resource, local_image_path: str, folder_id: str) -> Optional[str]:
    """Upload a local image to a specific folder in Google Drive and return its ID."""
    try:
        filename = os.path.basename(local_image_path)
        file_metadata = {"name": filename, "parents": [folder_id]}
        media = MediaFileUpload(local_image_path, resumable=True)

        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()

        image_id = file.get('id')
        logger.info(f"Uploaded image '{filename}' with ID: {image_id}")
        return image_id
    except HttpError as e:
        logger.error(f"Error uploading image '{local_image_path}': {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during image upload: {e}")
        return None


def delete_file(drive_service: Resource, file_id: str) -> bool:
    """Delete a file from Google Drive."""
    try:
        drive_service.files().delete(fileId=file_id).execute()
        logger.info(f"Successfully deleted file with ID: {file_id}")
        return True
    except HttpError as e:
        logger.error(f"Error deleting file with ID '{file_id}': {e}")
        return False


def download_file(drive_service: Resource, file_id: str, local_destination_path: str) -> bool:
    """Download a file from Google Drive to a local path."""
    try:
        request = drive_service.files().get_media(fileId=file_id)
        fh = io.FileIO(local_destination_path, "wb")
        downloader = MediaIoBaseDownload(fh, request)

        done = False
        while not done:
            status, done = downloader.next_chunk()
            logger.info(f"Download {int(status.progress() * 100)}%.")

        logger.info(f"Successfully downloaded file ID {file_id} to {local_destination_path}")
        return True
    except HttpError as e:
        logger.error(f"Error downloading file with ID '{file_id}': {e}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during file download: {e}")
        return False


def get_or_create_subfolder(drive_service: Resource, folder_name: str, parent_folder_id: str) -> Optional[str]:
    """Find or create a subfolder within a parent folder and return its ID."""
    try:
        query = (
            f"mimeType='application/vnd.google-apps.folder' and "
            f"name='{folder_name}' and '{parent_folder_id}' in parents and trashed=false"
        )
        response = drive_service.files().list(q=query, spaces="drive", fields="files(id)").execute()
        files = response.get("files", [])

        if files:
            return files[0]["id"]
        else:
            file_metadata = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_folder_id],
            }
            folder = drive_service.files().create(body=file_metadata, fields="id").execute()
            logger.info(f"Created subfolder '{folder_name}' with ID: {folder.get('id')}")
            return folder.get("id")
    except HttpError as e:
        logger.error(f"Error finding or creating subfolder '{folder_name}': {e}")
        return None


def list_files_in_folder(drive_service: Resource, folder_id: str, mime_type: str = "application/json") -> List[Dict[str, str]]:
    """List files of a specific mime type in a given Google Drive folder."""
    try:
        query = f"'{folder_id}' in parents and mimeType='{mime_type}' and trashed=false"
        response = drive_service.files().list(
            q=query,
            spaces="drive",
            fields="files(id, name)",
            orderBy="name"
        ).execute()
        return response.get("files", [])
    except HttpError as e:
        logger.error(f"Error listing files in folder '{folder_id}': {e}")
        return []


def move_file(drive_service: Resource, file_id: str, new_parent_id: str) -> bool:
    """Move a file to a different folder in Google Drive."""
    try:
        # Retrieve the existing parents to remove them
        file = drive_service.files().get(fileId=file_id, fields='parents').execute()
        previous_parents = ",".join(file.get('parents'))

        # Move the file by adding the new parent and removing the old ones
        drive_service.files().update(
            fileId=file_id,
            addParents=new_parent_id,
            removeParents=previous_parents,
            fields='id, parents'
        ).execute()
        logger.info(f"Successfully moved file {file_id} to folder {new_parent_id}")
        return True
    except HttpError as e:
        logger.error(f"Error moving file {file_id}: {e}")
        return False
