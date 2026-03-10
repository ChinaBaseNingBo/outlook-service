from src.outlook_api import OutlookAPI
from datetime import date, datetime, timedelta, timezone
import time
import logging

class OutlookService:
    def __init__(self, outlook_api=OutlookAPI()):
        self.api = outlook_api

    def handle_notification_batch(self, notifications):
        """
        Process incoming notification from Outlook webhook
        notification: The notification payload from Outlook
        """
        email_data = []
        for notification in notifications:
            resource = notification.get('resource')
            if not resource:
                print("No resource found in notification.")
                return None
            email_data.append(self.api.get_email_by_resource(resource))
        return self.api.save_emails_to_db(email_data)
    
    def update_access_token(self):
        """Update the access token for Outlook API"""
        self.api.renew_access_token()
    
    def create_subscription(self, callback_url):
        """
        Create a new subscription for Outlook webhook
        callback_url: The URL to receive notifications
        """
        return self.api.subscribe_outlook_webhook(callback_url)
    
    def extend_subscription(self, subscription_id):
        """
        Extend the expiration of an existing subscription
        subscription_id: The ID of the subscription to extend
        """
        return self.api.patch_subscription_expiration(subscription_id) 
    
    def subscription_lifecycle(self, callback_url, renew_margin_minutes=60):
        """
        Manage subscription lifecycle: create, monitor, and extend all subscriptions.
        :param callback_url: The URL to receive notifications
        :param renew_margin_minutes: Minutes before expiration to trigger renewal
        """
        subs = self.create_subscription(callback_url)
        logging.info("Created %d subscription(s): %s", len(subs), subs)

        while True:
            for i, sub in enumerate(subs):
                exp_str = sub.get("expirationDateTime")
                expiration = datetime.fromisoformat(exp_str.replace("Z", "+00:00"))
                minutes_left = (expiration - datetime.now(timezone.utc)).total_seconds() / 60

                logging.info("[Service] Subscription %d/%d (%s) expires in %.1f minutes",
                             i + 1, len(subs), sub['id'], minutes_left)

                if minutes_left <= renew_margin_minutes:
                    logging.info("[Service] Renewing subscription %s ...", sub['id'])
                    try:
                        subs[i] = self.extend_subscription(sub["id"])
                        logging.info("[Service] New expiration: %s", subs[i]["expirationDateTime"])
                    except Exception:
                        logging.exception("[Service] Failed to renew subscription %s, will retry next cycle", sub['id'])

            time.sleep(300)  # check every 5 minutes