import os
from dotenv import load_dotenv
import logging
import json
from msal import PublicClientApplication, SerializableTokenCache

load_dotenv()
OUTLOOK_CLIENT_ID = os.getenv("OUTLOOK_CLIENT_ID")
OUTLOOK_URL = "https://graph.microsoft.com/v1.0/" # Used API version 1.0
AUTHORITY = "https://login.microsoftonline.com/consumers"
SCOPES = ["Mail.Read", "User.Read"]
CACHE_FILE = "msal_cache.bin"

class AuthManager:
    def __init__(self):
        self.cache = SerializableTokenCache() # Read token cache from file if exists
        if os.path.exists(CACHE_FILE):
            self.cache.deserialize(open(CACHE_FILE, "r").read())

        self.app = PublicClientApplication(
            OUTLOOK_CLIENT_ID,
            authority=AUTHORITY,
            token_cache=self.cache,
        )
        
        token = self.get_access_token() # Get access token interactively or silently
        self.headers = {"Authorization": f"Bearer {token}"}
    
    def _save_cache(self):
        if self.cache.has_state_changed:
            with open(CACHE_FILE, "w") as f:
                f.write(self.cache.serialize())
                
    def get_access_token(self):
        """Acquire access token if needed."""
        account = self.app.get_accounts() 
        if account: # Try to acquire token silently
            result = self.app.acquire_token_silent(SCOPES, account=account[0])
        else:
            result = None
            
        if not result or "access_token" not in result: # Try interactive if silent acquisition fails
            logging.error("No valid token found in cache, acquiring new token interactively...")
            flow = self.app.initiate_device_flow(scopes=SCOPES)
            if "user_code" not in flow:
                raise Exception("Failed to create device flow. Err: %s" % json.dumps(flow, indent=4))
            logging.info("Go to this URL: %s", flow["verification_uri"])
            logging.info("And enter the code: %s", flow["user_code"])
            logging.info("Enter the email address: chinabaseningbo@outlook.com .")
            logging.info("Enter the received code to authenticate.")
            result = self.app.acquire_token_by_device_flow(flow)
                        
        if "access_token" not in result:
            raise Exception("Could not obtain access token. Err: %s" % json.dumps(result, indent=4))
        
        self._save_cache()  # Save the new token to cache file
        return result['access_token']

if __name__ == "__main__":
    auth_manager = AuthManager()
    token = auth_manager.get_access_token()
    print("Access Token:", token)