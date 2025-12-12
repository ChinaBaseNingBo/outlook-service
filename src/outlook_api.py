'''
Outlook API uses Microsoft Graph to fetch emails and events.
url = "https://developer.microsoft.com/en-us/graph/graph-explorer"
Token is generated via graph explorer.
'''
import requests
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import html2text
import src.mongo_service as mongodb
from src.auth import AuthManager
import logging
import sys
import base64

load_dotenv()
OUTLOOK_CLIENT_ID = os.getenv("OUTLOOK_CLIENT_ID")
OUTLOOK_URL = "https://graph.microsoft.com/v1.0/" # Used API version 1.0
AUTHORITY = "https://login.microsoftonline.com/consumers"
SCOPES = ["Mail.Read", "User.Read"]
CACHE_FILE = "msal_cache.bin"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

def iso_z(dt: datetime) -> str:
    """Format a tz-aware datetime as ISO-8601 with trailing Z."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


class OutlookAPI:
    def __init__(self, auth=AuthManager()):
        self.auth = auth
    
    def _auth_headers(self):
        token = self.auth.get_access_token()
        return {"Authorization": f"Bearer {token}"}

    def get_user_info(self):
        url = f"{OUTLOOK_URL}/me"
        response = requests.get(url, headers=self._auth_headers())
        return response.json()

    def get_user_folder_ids(self):
        url = f"{OUTLOOK_URL}/me/mailFolders"
        response = requests.get(url, headers=self._auth_headers())
        folders = response.json().get('value', [])
        folder_ids = []
        for folder in folders:
            if folder.get('displayName') == 'Bloomberg' or folder.get('displayName') == 'Shuchuang':
                folder_ids.append(folder.get('id'))
                
        return folder_ids if len(folder_ids) != 0 else None
    

    def get_email_by_resource(self, resource):
        """
        Fetch email details using the resource URL from notification
        resource: The resource URL from the notification
        """
        resource = resource.lstrip('/')
        url = f"{OUTLOOK_URL}/{resource}"
        response = requests.get(url, headers=self._auth_headers())
        response.raise_for_status()
        return response.json()

    def subscribe_single_outlook_webhook(self, callback_url, folder_id): # Changed
        """
        Subscribe to Outlook webhook notifications for a single folder
        callback_url: The URL of AWS EC2 instance to receive notifications
        """
        url = f"{OUTLOOK_URL}/subscriptions"
        data = {
            "changeType": "created,updated",
            "notificationUrl": callback_url,
            "resource": f"me/mailFolders/{folder_id}/messages",
            "expirationDateTime": (datetime.now(timezone.utc) + timedelta(days=6, hours=23)).strftime('%Y-%m-%dT%H:%M:%SZ'),
            "clientState": "secretClientValue"
        }
        response = requests.post(url, headers=self._auth_headers(), json=data)
        return response.json()
    
    def subscribe_outlook_webhook(self, callback_url): # Changed
        """
        Subscribe outlook webhooks for multiple folders
        callback_url: The URL of AWS EC2 instance to receive notifications
        """
        folder_ids = self.get_user_folder_ids()
        
        if (not folder_ids):
            logging.error("No target folders found for subscription.")
            return None
        
        for folder_id in folder_ids:
            response = self.subscribe_single_outlook_webhook(callback_url, folder_id)
            logging.info(f"Subscribe successfully to {folder_id}, getting response {response}.")
    
    def patch_subscription_expiration(self, subscription_id):
        """
        Patch subscription to extend expiration
        subscription_id: The ID of the subscription to patch
        """
        url = f"{OUTLOOK_URL}/subscriptions/{subscription_id}"
        data = {
            "expirationDateTime": (datetime.now(timezone.utc) + timedelta(days=6, hours=23)).strftime('%Y-%m-%dT%H:%M:%SZ')
        }
        response = requests.patch(url, headers=self._auth_headers(), json=data)
        return response.json()

    @staticmethod
    def html_to_markdown(html):
        h = html2text.HTML2Text()
        h.ignore_images = True
        h.ignore_emphasis = False
        h.body_width = 0
        return h.handle(html)
    
    def process_emails(self, emails):
        """
        Process emails based on categories
        emails: list of email JSON objects
        
        return: dict of processed emails
        """
        processed_emails = {
            "bloomberg_emails": [],
            "shuchuang_emails": [],
        }
        for email in emails:
            if email.get("categories")[0] == "Blue Category":
                email_id = email.get("id")
                attachment = self.get_attachment_by_email_id(email_id)
                process_attachment = self.process_attachment_from_email(attachment[0]) if attachment else None
                processed_emails["shuchuang_emails"].append(process_attachment)
            elif email.get("categories")[0] == "Green Category":
                processed_email = self.process_message_from_email(email)
                processed_emails["bloomberg_emails"].append(processed_email)
        return processed_emails
    
    def save_emails_to_db(self, emails):
        processed_emails = self.process_emails(emails)
        # print("Processed Emails:", json.dumps(processed_emails, default=str, indent=2))
        
        mongodb_client = mongodb.MongoDBClient(mongodb.MONGO_URI, mongodb.MONGO_DB_NAME)
        inserted_bloomberg = 0
        inserted_shuchuang = 0
        
        try:
            shuchuang_attachments = processed_emails["shuchuang_emails"]
            if shuchuang_attachments:
                inserted_shuchuang = mongodb_client.save_shuchuang_attachments_to_db(shuchuang_attachments)
        
            bloomberg_emails = processed_emails["bloomberg_emails"]
            if bloomberg_emails:
                inserted_bloomberg = mongodb_client.save_bloomberg_emails_to_db(bloomberg_emails)
            
            inserted_count = inserted_shuchuang + inserted_bloomberg
            logging.info("Saved %d emails to MongoDB.", inserted_count)
            return inserted_count
        finally:
            mongodb_client.client.close()
    
    def get_attachment_by_email_id(self, email_id):
        url = f"{OUTLOOK_URL}/me/messages/{email_id}/attachments"
        response = requests.get(url, headers=self._auth_headers())
        logging.info(response.raise_for_status())
        return response.json().get('value', [])
    
    def process_message_from_email(self, email):
        """
        Process the plain body of email message
        email: email JSON object
        """
        raw_time = email.get("receivedDateTime")
        dt = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
        
        processed_email = {
            "id": email.get("id"),
            "subject": email.get("subject"),
            "body": self.html_to_markdown(email.get("body", {}).get("content")),
            "time": dt,
            "from": email.get("from", {}).get("emailAddress", {}).get("address"),
        }
        return processed_email
    
    def process_attachment_from_email(self, attachment):
        """
        Process the attachment content of email
        attachment: attachment JSON object
        
        return: decoded content bytes
        """
        raw_time = attachment.get("lastModifiedDateTime")
        dt = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
        id = attachment.get("id")
        name = attachment.get("name")
        content_type = attachment.get("contentType")
        content_bytes = attachment.get("contentBytes")
        
        if content_bytes:
            content = base64.b64decode(content_bytes)
            
            processed_attachment = {
                "id": id,
                "name": name,
                "time": dt,
                "content_type": content_type,
                "content": content,
            }
            return processed_attachment
        return None

    def get_targeted_emails_by_range_mailfolders(self, start, end, folder_id=None):
        folder_ids = self.get_user_folder_ids() if not folder_id else folder_id
        if not folder_ids:
            logging.error("No target folder found for fetching emails.")
            return []
        
        emails = []
        
        for folder_id in folder_ids:  
            url = f"{OUTLOOK_URL}/me/mailFolders/{folder_id}/messages"
            params = {
                "$select": "id,subject,receivedDateTime,bodyPreview,body,from",
                "$orderby": "receivedDateTime desc",
                "$top": 50,
                "$filter": (
                    f"receivedDateTime ge {iso_z(start)} "
                    f"and receivedDateTime lt {iso_z(end)}"
                ),
            }
            response = requests.get(url, headers=self._auth_headers(), params=params)
            emails.append(response.json().get('value', []))
            
        return emails