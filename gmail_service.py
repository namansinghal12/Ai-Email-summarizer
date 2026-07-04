import os
import base64
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import config
from utils import logger
from email_parser import parse_raw_email

def get_gmail_credentials() -> Credentials:
    """Loads existing credentials, refreshes them if expired, or runs new OAuth flow."""
    creds = None
    
    # Check if token.json exists
    if os.path.exists(config.TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(config.TOKEN_FILE, config.GMAIL_SCOPES)
            logger.info("Loaded credentials from token.json")
        except Exception as e:
            logger.error(f"Failed to load credentials from token file: {e}")
            creds = None

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                logger.info("Token expired. Refreshing OAuth token...")
                creds.refresh(Request())
                # Save refreshed token
                with open(config.TOKEN_FILE, "w") as token:
                    token.write(creds.to_json())
                logger.info("Refreshed OAuth token successfully.")
                return creds
            except Exception as e:
                logger.error(f"Failed to refresh OAuth token: {e}")
                creds = None

        # Run InstalledAppFlow
        if not os.path.exists(config.CREDENTIALS_FILE):
            logger.error(f"credentials.json not found at {config.CREDENTIALS_FILE}")
            raise FileNotFoundError(
                f"credentials.json is missing in the '{config.CREDENTIALS_DIR.name}' folder. "
                "Please configure Gmail API OAuth client secrets file to proceed."
            )

        logger.info("Starting local Gmail OAuth browser-based login flow...")
        flow = InstalledAppFlow.from_client_secrets_file(
            str(config.CREDENTIALS_FILE), config.GMAIL_SCOPES
        )
        # Opens local browser window for user to authorize scopes
        creds = flow.run_local_server(port=0)
        
        # Save credentials
        with open(config.TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
        logger.info("Gmail OAuth authentication successful. Saved token to token.json.")

    return creds

def get_gmail_service():
    """Builds and returns the Gmail service object."""
    try:
        creds = get_gmail_credentials()
        return build("gmail", "v1", credentials=creds)
    except Exception as e:
        logger.error(f"Failed to build Gmail service client: {e}")
        raise e

def fetch_emails(service, query_filter: str = "is:unread", max_results: int = 10) -> list:
    """Fetches a list of email message metadata matching the query filter."""
    try:
        logger.info(f"Fetching messages matching query: '{query_filter}' (Max results: {max_results})")
        results = service.users().messages().list(
            userId="me", q=query_filter, maxResults=max_results
        ).execute()
        
        messages = results.get("messages", [])
        logger.info(f"Found {len(messages)} messages matching filter.")
        return messages
    except Exception as e:
        logger.error(f"Error listing emails: {e}", exc_info=True)
        return []

def get_message_detail(service, msg_id: str) -> dict:
    """Retrieves and parses a single message by ID, returning metadata and body."""
    try:
        logger.info(f"Fetching raw email content for ID: {msg_id}")
        # Fetch the message in RAW format
        message = service.users().messages().get(
            userId="me", id=msg_id, format="raw"
        ).execute()
        
        # Decode raw MIME bytes
        msg_bytes = base64.urlsafe_b64decode(message["raw"].encode("ASCII"))
        
        # Parse MIME structure
        parsed_email = parse_raw_email(msg_bytes)
        parsed_email["id"] = msg_id
        
        # Extract additional Gmail API metadata (labels, snippet, size)
        full_meta = service.users().messages().get(
            userId="me", id=msg_id, format="minimal"
        ).execute()
        parsed_email["gmail_labels"] = full_meta.get("labelIds", [])
        
        return parsed_email
    except Exception as e:
        logger.error(f"Error fetching message details for {msg_id}: {e}", exc_info=True)
        return None

def get_or_create_gmail_label(service, label_name: str) -> str:
    """Finds or creates a Gmail label and returns its ID."""
    try:
        results = service.users().labels().list(userId="me").execute()
        labels = results.get("labels", [])
        
        # Look for existing label
        for label in labels:
            if label["name"].lower() == label_name.lower():
                return label["id"]
                
        # Create new label
        label_body = {
            "name": label_name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show"
        }
        logger.info(f"Creating new Gmail label: '{label_name}'")
        new_label = service.users().labels().create(userId="me", body=label_body).execute()
        return new_label["id"]
    except Exception as e:
        logger.error(f"Error creating/retrieving label '{label_name}': {e}", exc_info=True)
        return None

def apply_labels_to_email(service, msg_id: str, label_names: list):
    """Automatically applies multiple labels to an email in Gmail."""
    try:
        label_ids = []
        for name in label_names:
            label_id = get_or_create_gmail_label(service, name)
            if label_id:
                label_ids.append(label_id)
                
        if label_ids:
            body = {"addLabelIds": label_ids}
            service.users().messages().modify(userId="me", id=msg_id, body=body).execute()
            logger.info(f"Successfully applied labels {label_names} to message ID: {msg_id}")
    except Exception as e:
        logger.error(f"Error modifying labels for email {msg_id}: {e}", exc_info=True)

def mark_email_as_read(service, msg_id: str):
    """Removes the UNREAD label from a message."""
    try:
        body = {"removeLabelIds": ["UNREAD"]}
        service.users().messages().modify(userId="me", id=msg_id, body=body).execute()
        logger.info(f"Marked email {msg_id} as READ.")
    except Exception as e:
        logger.error(f"Error marking email {msg_id} as read: {e}", exc_info=True)
