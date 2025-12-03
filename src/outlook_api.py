'''
Outlook API uses Microsoft Graph to fetch emails and events.
url = "https://developer.microsoft.com/en-us/graph/graph-explorer"
Token is generated via graph explorer.
'''
from urllib import response
import requests
import os
from dotenv import load_dotenv
import json
from datetime import date, datetime, time, timedelta, timezone
from pymongo import MongoClient
import html2text
import src.mongo_service as mongodb
from msal import PublicClientApplication, SerializableTokenCache
from src.auth import AuthManager
import logging

load_dotenv()
OUTLOOK_CLIENT_ID = os.getenv("OUTLOOK_CLIENT_ID")
OUTLOOK_URL = "https://graph.microsoft.com/v1.0/" # Used API version 1.0
AUTHORITY = "https://login.microsoftonline.com/consumers"
SCOPES = ["Mail.Read", "User.Read"]
CACHE_FILE = "msal_cache.bin"


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

    def get_user_bloomberg_folder_id(self):
        url = f"{OUTLOOK_URL}/me/mailFolders"
        response = requests.get(url, headers=self._auth_headers())
        folders = response.json().get('value', [])
        for folder in folders:
            if folder.get('displayName') == 'Bloomberg':
                return folder.get('id')
        return None
    
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

    def subscribe_outlook_webhook(self, callback_url):
        """
        Subscribe to Outlook webhook notifications
        callback_url: The URL of AWS EC2 instance to receive notifications
        """
        url = f"{OUTLOOK_URL}/subscriptions"
        folder_id = self.get_user_bloomberg_folder_id()
        data = {
            "changeType": "created,updated",
            "notificationUrl": callback_url,
            "resource": f"me/mailFolders/{folder_id}/messages",
            "expirationDateTime": (datetime.now(timezone.utc) + timedelta(days=6, hours=23)).strftime('%Y-%m-%dT%H:%M:%SZ'),
            "clientState": "secretClientValue"
        }
        response = requests.post(url, headers=self._auth_headers(), json=data)
        return response.json()
    
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
        
    def get_bloomberg_emails_by_range(self, start, end):
        folder_id = self.get_user_bloomberg_folder_id()
        if not folder_id:
            print("Bloomberg folder not found")
            return []

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
        return response.json().get('value', [])

    @staticmethod
    def html_to_markdown(html):
        h = html2text.HTML2Text()
        h.ignore_images = True
        h.ignore_emphasis = False
        h.body_width = 0
        return h.handle(html)
    
    def process_emails(self, emails):
        processed_emails = []
        for email in emails:
            raw_time = email.get("receivedDateTime")
            dt = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
            
            processed_email = {
                "id": email.get("id"),
                "subject": email.get("subject"),
                "body": self.html_to_markdown(email.get("body", {}).get("content")),
                "time": dt,
                "from": email.get("from", {}).get("emailAddress", {}).get("address"),
            }
            processed_emails.append(processed_email)
        return processed_emails
    
    def save_emails_to_db(self, emails):
        processed_emails = self.process_emails(emails)
        # print("Processed Emails:", json.dumps(processed_emails, default=str, indent=2))
        
        mongodb_client = mongodb.MongoDBClient(mongodb.MONGO_URI, mongodb.MONGO_DB_NAME)
        inserted_count = mongodb_client.save_bloomberg_emails_to_db(processed_emails)
        logging.info("Saved %d emails to MongoDB.", inserted_count)
        mongodb_client.client.close()
        return inserted_count
