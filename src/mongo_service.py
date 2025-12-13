import os
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import BulkWriteError
import logging
import gridfs

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
BLOOMBERG_COLLECTION_NAME = os.getenv("MONGO_COLLECTION_BLOOMBERG") # Collection for Bloomberg
SHUCHUANG_COLLECTION_NAME = os.getenv("MONGO_COLLECTION_SHUCHUANG") # Collection for Shuchuang
SHUCHUANG_FS_COLLECTION_NAME = os.getenv("MONGO_COLLECTION_SHUCHUANG_FS") # GridFS collection for Shuchuang attachments

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
        
    
    def save_shuchuang_attachments_to_db(self, attachments):
        """Save Shuchuang attachments to MongoDB"""
        if not attachments:
            return 0
        collection = self.get_mongo_collection(SHUCHUANG_COLLECTION_NAME)
        db = collection.database
        fs = gridfs.GridFS(db, collection=SHUCHUANG_FS_COLLECTION_NAME)
        inserted = 0

        for attachment in attachments:
            id = attachment.get("id")
            attachment_content = attachment.get("content")
            filename = attachment.get("name")
            content_type = attachment.get("content_type")
            time = attachment.get("time")
            
            if collection.find_one({"_id": str(id)}):
                logging.info("Attachment with id %s already exists. Skipping.", id)
                continue
            
            if not id:
                continue
            
            gridfs_id = fs.put(
                attachment_content,
                filename=filename,
                contentType=content_type,
                messageId=str(id)
            )
            
            attachment_doc = {
                "_id": str(id),
                "filename": filename,
                "contentType": content_type,
                "gridfs_id": gridfs_id,
                "time": time,
            }
            collection.insert_one(attachment_doc)
            inserted += 1

        logging.info("Inserted %d new attachments (skipped duplicates).", inserted)
        return inserted

    def close_connection(self):
        self.client.close()