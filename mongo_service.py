import os
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import BulkWriteError
import logging

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
BLOOMBERG_COLLECTION_NAME = os.getenv("MONGO_COLLECTION_BLOOMBERG") # Collection for Bloomberg_API

class MongoDBClient:
    def __init__(self, uri, db_name):
        self.client = MongoClient(uri)
        self.db = self.client[db_name]

    def get_mongo_client(self):
        """Get MongoDB client connection"""
        return self.client

    def get_mongo_collection(self, collection_name):
        """Get a specific MongoDB collection"""
        return self.db[collection_name]
    
    def save_bloomberg_emails_to_db(self, emails):
        """Save Bloomberg emails to MongoDB"""
        if not emails:
            return 0
        try:
            collection = self.get_mongo_collection(BLOOMBERG_COLLECTION_NAME)
            ops = []

            for email in emails:
                id = email.get("id")
                if not id:
                    continue 
                email_doc = {
                    "_id": str(id),
                    "subject": email.get("subject"),
                    "body": email.get("body"),
                    "time": email.get("time"),
                    "from": email.get("from"),
                }
                ops.append(email_doc)

            if not ops:
                return 0

            result = collection.insert_many(ops, ordered=False)
            inserted = len(result.inserted_ids) if result.inserted_ids else 0

            logging.info("Inserted %d new emails (skipped duplicates).", inserted)
            return inserted

        except BulkWriteError as e:
            # Count duplicates vs other errors without dumping giant logs
            details = getattr(e, "details", {}) or {}
            write_errors = details.get("writeErrors", [])
            non_dup = [x for x in write_errors if x.get("code") != 11000]
            if not non_dup:
                attempted = len(ops)
                dup_count = len(write_errors)
                return max(0, attempted - dup_count)
            brief = "; ".join((x.get("errmsg") or str(x.get("code")))[:160] for x in non_dup[:3])
            raise RuntimeError(f"insert_many failed (non-duplicate): {brief}") from None

        except Exception as e:
            # Short, actionable error
            raise RuntimeError(f"save_bloomberg_emails_to_db error: {type(e).__name__}: {e}") from None
    
    def close_connection(self):
        self.client.close()