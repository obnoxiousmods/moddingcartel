import logging
import os
import shutil
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from arangoasync import ArangoClient
from arangoasync.auth import Auth
from arangoasync.collection import StandardCollection
from arangoasync.database import StandardDatabase

from app.config import Config

logger = logging.getLogger(__name__)

# Constants
BYTES_PER_GB = 1024**3  # 1073741824 bytes per GB


class Database:
    """ArangoDB database connection and operations"""

    def __init__(self):
        self.client: Optional[ArangoClient] = None
        self.db: Optional[StandardDatabase] = None
        self.entries_collection: Optional[StandardCollection] = None
        self.users_collection: Optional[StandardCollection] = None
        self.directories_collection: Optional[StandardCollection] = None
        self.download_history_collection: Optional[StandardCollection] = None
        self.requests_collection: Optional[StandardCollection] = None
        self.api_keys_collection: Optional[StandardCollection] = None
        self.api_usage_collection: Optional[StandardCollection] = None
        self.audit_logs_collection: Optional[StandardCollection] = None
        self.activity_logs_collection: Optional[StandardCollection] = None
        self.upload_statistics_collection: Optional[StandardCollection] = None
        self.reports_collection: Optional[StandardCollection] = None
        self.comments_collection: Optional[StandardCollection] = None
        self.likes_collection: Optional[StandardCollection] = None
        self.comment_likes_collection: Optional[StandardCollection] = None
        self.send_queue_collection: Optional[StandardCollection] = None

    async def connect(self):
        """Connect to ArangoDB and initialize database/collections"""
        try:
            # Initialize ArangoDB client
            self.client = ArangoClient(hosts=Config.get_arangodb_url())

            # Create auth object
            auth = Auth(
                username=Config.ARANGODB_USERNAME(), password=Config.ARANGODB_PASSWORD()
            )

            # Connect to _system database to check if our database exists
            sys_db = await self.client.db("_system", auth=auth)

            # Create database if it doesn't exist
            if not await sys_db.has_database(Config.ARANGODB_DATABASE()):
                await sys_db.create_database(Config.ARANGODB_DATABASE())
                logger.info(f"Created database: {Config.ARANGODB_DATABASE()}")

            # Connect to the application database
            self.db = await self.client.db(Config.ARANGODB_DATABASE(), auth=auth)

            # Create entries collection if it doesn't exist
            if not await self.db.has_collection("entries"):
                self.entries_collection = await self.db.create_collection("entries")
                logger.info("Created collection: entries")
            else:
                self.entries_collection = self.db.collection("entries")

            # Create users collection if it doesn't exist
            if not await self.db.has_collection("users"):
                self.users_collection = await self.db.create_collection("users")
                logger.info("Created collection: users")
            else:
                self.users_collection = self.db.collection("users")

            # Create directories collection if it doesn't exist
            if not await self.db.has_collection("directories"):
                self.directories_collection = await self.db.create_collection(
                    "directories"
                )
                logger.info("Created collection: directories")
            else:
                self.directories_collection = self.db.collection("directories")

            # Create download_history collection if it doesn't exist
            if not await self.db.has_collection("download_history"):
                self.download_history_collection = await self.db.create_collection(
                    "download_history"
                )
                logger.info("Created collection: download_history")
            else:
                self.download_history_collection = self.db.collection(
                    "download_history"
                )

            # Create requests collection if it doesn't exist
            if not await self.db.has_collection("requests"):
                self.requests_collection = await self.db.create_collection("requests")
                logger.info("Created collection: requests")
            else:
                self.requests_collection = self.db.collection("requests")

            # Create api_keys collection if it doesn't exist
            if not await self.db.has_collection("api_keys"):
                self.api_keys_collection = await self.db.create_collection("api_keys")
                logger.info("Created collection: api_keys")
            else:
                self.api_keys_collection = self.db.collection("api_keys")

            # Create api_usage collection if it doesn't exist
            if not await self.db.has_collection("api_usage"):
                self.api_usage_collection = await self.db.create_collection("api_usage")
                logger.info("Created collection: api_usage")
            else:
                self.api_usage_collection = self.db.collection("api_usage")

            # Create audit_logs collection if it doesn't exist
            if not await self.db.has_collection("audit_logs"):
                self.audit_logs_collection = await self.db.create_collection(
                    "audit_logs"
                )
                logger.info("Created collection: audit_logs")
            else:
                self.audit_logs_collection = self.db.collection("audit_logs")

            # Create activity_logs collection if it doesn't exist
            if not await self.db.has_collection("activity_logs"):
                self.activity_logs_collection = await self.db.create_collection(
                    "activity_logs"
                )
                logger.info("Created collection: activity_logs")
            else:
                self.activity_logs_collection = self.db.collection("activity_logs")

            # Create upload_statistics collection if it doesn't exist
            if not await self.db.has_collection("upload_statistics"):
                self.upload_statistics_collection = await self.db.create_collection(
                    "upload_statistics"
                )
                logger.info("Created collection: upload_statistics")
            else:
                self.upload_statistics_collection = self.db.collection(
                    "upload_statistics"
                )

            # Create reports collection if it doesn't exist
            if not await self.db.has_collection("reports"):
                self.reports_collection = await self.db.create_collection("reports")
                logger.info("Created collection: reports")
            else:
                self.reports_collection = self.db.collection("reports")

            # Create comments collection if it doesn't exist
            if not await self.db.has_collection("comments"):
                self.comments_collection = await self.db.create_collection("comments")
                logger.info("Created collection: comments")
            else:
                self.comments_collection = self.db.collection("comments")

            # Create likes collection if it doesn't exist
            if not await self.db.has_collection("likes"):
                self.likes_collection = await self.db.create_collection("likes")
                logger.info("Created collection: likes")
            else:
                self.likes_collection = self.db.collection("likes")

            # Create comment_likes collection if it doesn't exist
            if not await self.db.has_collection("comment_likes"):
                self.comment_likes_collection = await self.db.create_collection("comment_likes")
                logger.info("Created collection: comment_likes")
            else:
                self.comment_likes_collection = self.db.collection("comment_likes")

            # Create send_queue collection if it doesn't exist
            if not await self.db.has_collection("send_queue"):
                self.send_queue_collection = await self.db.create_collection("send_queue")
                logger.info("Created collection: send_queue")
            else:
                self.send_queue_collection = self.db.collection("send_queue")

            logger.info("Successfully connected to ArangoDB")

        except Exception as e:
            logger.error(f"Failed to connect to ArangoDB: {e}")
            raise

    async def ping(self) -> bool:
        """Check if the ArangoDB connection is still valid"""
        try:
            if self.db is None:
                return False
            await self.db.aql.execute("RETURN 1")
            return True
        except Exception:
            return False

    async def disconnect(self):
        """Close database connection"""
        if self.client:
            await self.client.close()
            logger.info("Disconnected from ArangoDB")

    async def get_all_entries(self) -> List[Dict[str, Any]]:
        """Get all entries from the database"""
        try:
            cursor = await self.db.aql.execute(
                "FOR doc IN entries SORT doc.size DESC RETURN doc"
            )
            entries = []
            async with cursor:
                async for doc in cursor:
                    # Convert _key to id for API response
                    entry = {
                        "id": doc.get("_key"),
                        "name": doc.get("name"),
                        "source": doc.get("source"),
                        "type": doc.get("type"),
                        "file_type": doc.get("file_type"),
                        "size": doc.get("size"),
                        "created_at": doc.get("created_at"),
                        "created_by": doc.get("created_by", ""),
                        "metadata": doc.get("metadata", {}),
                    }
                    entries.append(entry)
            return entries
        except Exception as e:
            logger.error(f"Error fetching entries: {e}")
            return []

    async def get_entry_by_id(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """Get a single entry by its ID"""
        try:
            doc = await self.entries_collection.get(entry_id)
            if doc:
                return {
                    "_key": doc.get("_key"),
                    "id": doc.get("_key"),
                    "name": doc.get("name"),
                    "source": doc.get("source"),
                    "type": doc.get("type"),
                    "file_type": doc.get("file_type"),
                    "size": doc.get("size"),
                    "created_at": doc.get("created_at"),
                    "created_by": doc.get("created_by", ""),
                    "metadata": doc.get("metadata", {}),
                    "corrupt": doc.get("corrupt", False),
                    "md5_hash": doc.get("md5_hash"),
                    "sha256_hash": doc.get("sha256_hash"),
                    "file_created_at": doc.get("file_created_at"),
                    "file_modified_at": doc.get("file_modified_at"),
                }
            return None
        except Exception as e:
            logger.error(f"Error fetching entry by ID: {e}")
            return None

    async def add_entry(self, entry_data: Dict[str, Any]) -> Optional[str]:
        """Add a new entry to the database"""
        try:
            # Add timestamp if not provided
            if "created_at" not in entry_data:
                entry_data["created_at"] = datetime.utcnow().isoformat()

            result = await self.entries_collection.insert(entry_data)
            logger.info(f"Added entry with key: {result['_key']}")
            return result["_key"]
        except Exception as e:
            logger.error(f"Error adding entry: {e}")
            return None

    async def delete_entry(self, entry_id: str) -> bool:
        """Delete an entry from the database"""
        try:
            await self.entries_collection.delete(entry_id)
            logger.info(f"Deleted entry: {entry_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting entry: {e}")
            return False

    async def mark_entry_corrupt(self, entry_id: str, corrupt: bool = True) -> bool:
        """Mark an entry as corrupt or not corrupt"""
        try:
            await self.entries_collection.update({"_key": entry_id, "corrupt": corrupt})
            logger.info(f"Updated entry {entry_id} corrupt status to {corrupt}")
            return True
        except Exception as e:
            logger.error(f"Error updating entry corrupt status: {e}")
            return False

    async def update_entry_hashes(
        self,
        entry_id: str,
        md5_hash: Optional[str] = None,
        sha256_hash: Optional[str] = None,
    ) -> bool:
        """Update MD5 and/or SHA256 hashes for an entry"""
        try:
            update_data = {"_key": entry_id}
            if md5_hash:
                update_data["md5_hash"] = md5_hash
            if sha256_hash:
                update_data["sha256_hash"] = sha256_hash

            if len(update_data) > 1:  # More than just _key
                await self.entries_collection.update(update_data)
                logger.info(f"Updated hashes for entry {entry_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error updating entry hashes: {e}")
            return False

    async def get_corrupt_entries(self) -> List[Dict[str, Any]]:
        """Get all entries marked as corrupt with their report information"""
        try:
            query = """
            FOR entry IN entries
            FILTER entry.corrupt == true
            LET open_reports = (
                FOR report IN reports
                FILTER report.entry_id == entry._key AND report.status == 'open'
                SORT report.created_at DESC
                RETURN report
            )
            LET report_count = LENGTH(open_reports)
            SORT entry.name ASC
            RETURN MERGE(entry, {
                open_reports: open_reports,
                report_count: report_count
            })
            """
            cursor = await self.db.aql.execute(query)
            entries = []
            async with cursor:
                async for entry in cursor:
                    entries.append(entry)
            return entries
        except Exception as e:
            logger.error(f"Error fetching corrupt entries: {e}")
            return []

    async def clear_all_corrupt_flags(self) -> int:
        """Clear corrupt flag from all entries, move reports to oldReports, and clear reports collection"""
        try:
            # Step 1: Update all corrupt entries - set corrupt to false and move reports to oldReports
            query = """
            LET updated = (
                FOR entry IN entries
                FILTER entry.corrupt == true
                LET current_reports = entry.reports || []
                LET current_old_reports = entry.oldReports || []
                UPDATE entry WITH {
                    corrupt: false,
                    oldReports: APPEND(current_old_reports, current_reports),
                    reports: []
                } IN entries
                RETURN NEW
            )
            RETURN LENGTH(updated)
            """
            cursor = await self.db.aql.execute(query)
            count = 0
            async with cursor:
                async for result in cursor:
                    count = result
                    break

            # Step 2: Clear the entire reports collection
            delete_query = """
            FOR doc IN reports
            REMOVE doc IN reports
            """
            await self.db.aql.execute(delete_query)

            logger.info(
                f"Cleared corrupt flag from {count} entries, moved reports to oldReports, and cleared reports collection"
            )
            return count
        except Exception as e:
            logger.error(f"Error clearing all corrupt flags: {e}")
            return 0

    # User management methods
    async def create_user(self, user_data: Dict[str, Any]) -> Optional[str]:
        """Create a new user"""
        try:
            # Add timestamp if not provided
            if "created_at" not in user_data:
                user_data["created_at"] = datetime.utcnow().isoformat()

            result = await self.users_collection.insert(user_data)
            logger.info(f"Created user: {user_data['username']}")
            return result["_key"]
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None

    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get a user by username"""
        try:
            cursor = await self.db.aql.execute(
                "FOR doc IN users FILTER doc.username == @username LIMIT 1 RETURN doc",
                bind_vars={"username": username},
            )
            async with cursor:
                async for doc in cursor:
                    return doc
            return None
        except Exception as e:
            logger.error(f"Error fetching user: {e}")
            return None

    async def user_exists(self, username: str) -> bool:
        """Check if a user exists"""
        user = await self.get_user_by_username(username)
        return user is not None

    # Directory management methods
    async def add_directory(self, path: str) -> Optional[str]:
        """Add a new directory to scan"""
        try:
            # Check if directory already exists
            existing = await self.get_directory_by_path(path)
            if existing:
                logger.warning(f"Directory already exists: {path}")
                return existing.get("_key")

            directory_data = {
                "path": path,
                "added_at": datetime.utcnow().isoformat(),
            }
            result = await self.directories_collection.insert(directory_data)
            logger.info(f"Added directory: {path}")
            return result["_key"]
        except Exception as e:
            logger.error(f"Error adding directory: {e}")
            return None

    async def get_directory_by_path(self, path: str) -> Optional[Dict[str, Any]]:
        """Get a directory by path"""
        try:
            cursor = await self.db.aql.execute(
                "FOR doc IN directories FILTER doc.path == @path LIMIT 1 RETURN doc",
                bind_vars={"path": path},
            )
            async with cursor:
                async for doc in cursor:
                    return doc
            return None
        except Exception as e:
            logger.error(f"Error fetching directory: {e}")
            return None

    async def get_directory_by_id(self, directory_id: str) -> Optional[Dict[str, Any]]:
        """Get a directory by ID"""
        try:
            doc = await self.directories_collection.get(directory_id)
            return doc
        except Exception as e:
            logger.error(f"Error fetching directory by ID: {e}")
            return None

    async def get_all_directories(self) -> List[Dict[str, Any]]:
        """Get all directories"""
        try:
            cursor = await self.db.aql.execute(
                "FOR doc IN directories SORT doc.added_at DESC RETURN doc"
            )
            directories = []
            async with cursor:
                async for doc in cursor:
                    directories.append(doc)
            return directories
        except Exception as e:
            logger.error(f"Error fetching directories: {e}")
            return []

    async def get_directories_with_storage_info(self) -> List[Dict[str, Any]]:
        """Get all directories with storage information"""
        try:
            directories = await self.get_all_directories()
            result = []

            for directory in directories:
                path = directory.get("path")
                if not path or not os.path.exists(path):
                    continue

                try:
                    # Get disk usage
                    usage = shutil.disk_usage(path)
                    total_gb = usage.total / BYTES_PER_GB
                    used_gb = usage.used / BYTES_PER_GB
                    free_gb = usage.free / BYTES_PER_GB

                    result.append(
                        {
                            "_key": directory.get("_key"),
                            "path": path,
                            "total_gb": round(total_gb, 2),
                            "used_gb": round(used_gb, 2),
                            "free_gb": round(free_gb, 2),
                            "added_at": directory.get("added_at"),
                        }
                    )
                except Exception as e:
                    logger.warning(f"Could not get storage info for {path}: {e}")

            return result
        except Exception as e:
            logger.error(f"Error fetching directories with storage info: {e}")
            return []

    async def delete_directory(self, directory_id: str) -> bool:
        """Delete a directory"""
        try:
            await self.directories_collection.delete(directory_id)
            logger.info(f"Deleted directory: {directory_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting directory: {e}")
            return False

    async def clear_all_entries(self) -> bool:
        """Clear all entries from the database"""
        try:
            await self.db.aql.execute("FOR doc IN entries REMOVE doc IN entries")
            logger.info("Cleared all entries")
            return True
        except Exception as e:
            logger.error(f"Error clearing entries: {e}")
            return False

    async def entry_exists(self, source: str) -> bool:
        """Check if an entry with this source already exists"""
        try:
            cursor = await self.db.aql.execute(
                "FOR doc IN entries FILTER doc.source == @source LIMIT 1 RETURN doc",
                bind_vars={"source": source},
            )
            async with cursor:
                async for doc in cursor:
                    return True
            return False
        except Exception as e:
            logger.error(f"Error checking entry existence: {e}")
            return False

    # User settings methods
    async def update_user_password(self, user_id: str, new_password_hash: str) -> bool:
        """Update a user's password"""
        try:
            await self.users_collection.update(
                {"_key": user_id, "password_hash": new_password_hash}
            )
            logger.info(f"Updated password for user: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating password: {e}")
            return False

    async def update_user_totp(
        self, user_id: str, totp_secret: Optional[str], totp_enabled: bool
    ) -> bool:
        """Update a user's TOTP settings"""
        try:
            await self.users_collection.update(
                {
                    "_key": user_id,
                    "totp_secret": totp_secret,
                    "totp_enabled": totp_enabled,
                }
            )
            logger.info(f"Updated TOTP settings for user: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating TOTP settings: {e}")
            return False

    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get a user by ID"""
        try:
            doc = await self.users_collection.get(user_id)
            return doc
        except Exception as e:
            logger.error(f"Error fetching user by ID: {e}")
            return None

    # Download history methods
    async def add_download_history(
        self, user_id: str, entry_id: str, entry_name: str, size_bytes: int = 0
    ) -> Optional[str]:
        """Add a download history record"""
        try:
            download_data = {
                "user_id": user_id,
                "entry_id": entry_id,
                "entry_name": entry_name,
                "size_bytes": size_bytes,
                "downloaded_at": datetime.utcnow().isoformat(),
            }
            result = await self.download_history_collection.insert(download_data)
            logger.info(f"Added download history for user {user_id}, entry {entry_id}")
            return result["_key"]
        except Exception as e:
            logger.error(f"Error adding download history: {e}")
            return None

    async def get_user_download_history(
        self, user_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get download history for a user"""
        try:
            cursor = await self.db.aql.execute(
                "FOR doc IN download_history FILTER doc.user_id == @user_id SORT doc.downloaded_at DESC LIMIT @limit RETURN doc",
                bind_vars={"user_id": user_id, "limit": limit},
            )
            history = []
            async with cursor:
                async for doc in cursor:
                    history.append(
                        {
                            "id": doc.get("_key"),
                            "entry_id": doc.get("entry_id"),
                            "entry_name": doc.get("entry_name"),
                            "downloaded_at": doc.get("downloaded_at"),
                        }
                    )
            return history
        except Exception as e:
            logger.error(f"Error fetching download history: {e}")
            return []

    # Request management methods
    async def create_request(self, request_data: Dict[str, Any]) -> Optional[str]:
        """Create a new request"""
        try:
            if "created_at" not in request_data:
                request_data["created_at"] = datetime.utcnow().isoformat()

            result = await self.requests_collection.insert(request_data)
            logger.info(f"Created request with key: {result['_key']}")
            return result["_key"]
        except Exception as e:
            logger.error(f"Error creating request: {e}")
            return None

    async def get_all_requests(
        self, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all requests, optionally filtered by status"""
        try:
            if status:
                cursor = await self.db.aql.execute(
                    "FOR doc IN requests FILTER doc.status == @status SORT doc.created_at DESC RETURN doc",
                    bind_vars={"status": status},
                )
            else:
                cursor = await self.db.aql.execute(
                    "FOR doc IN requests SORT doc.created_at DESC RETURN doc"
                )

            requests = []
            async with cursor:
                async for doc in cursor:
                    requests.append(doc)
            return requests
        except Exception as e:
            logger.error(f"Error fetching requests: {e}")
            return []

    async def count_requests(self, status: Optional[str] = None) -> int:
        """Count requests, optionally filtered by status"""
        try:
            if status:
                cursor = await self.db.aql.execute(
                    "FOR doc IN requests FILTER doc.status == @status COLLECT WITH COUNT INTO length RETURN length",
                    bind_vars={"status": status},
                )
            else:
                cursor = await self.db.aql.execute(
                    "FOR doc IN requests COLLECT WITH COUNT INTO length RETURN length"
                )

            async with cursor:
                async for count in cursor:
                    return count
            return 0
        except Exception as e:
            logger.error(f"Error counting requests: {e}")
            return 0

    async def get_request_by_id(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get a single request by ID"""
        try:
            doc = await self.requests_collection.get(request_id)
            return doc
        except Exception as e:
            logger.error(f"Error fetching request by ID: {e}")
            return None

    async def update_request_status(
        self, request_id: str, status: str, reviewed_by: str
    ) -> bool:
        """Update request status"""
        try:
            await self.requests_collection.update(
                {
                    "_key": request_id,
                    "status": status,
                    "reviewed_by": reviewed_by,
                    "reviewed_at": datetime.utcnow().isoformat(),
                },
            )
            logger.info(f"Updated request {request_id} status to {status}")
            return True
        except Exception as e:
            logger.error(f"Error updating request status: {e}")
            return False

    async def get_user_requests(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all requests for a specific user"""
        try:
            cursor = await self.db.aql.execute(
                "FOR doc IN requests FILTER doc.user_id == @user_id SORT doc.created_at DESC RETURN doc",
                bind_vars={"user_id": user_id},
            )
            requests = []
            async with cursor:
                async for doc in cursor:
                    requests.append(doc)
            return requests
        except Exception as e:
            logger.error(f"Error fetching user requests: {e}")
            return []

    async def update_user_moderator_status(
        self, user_id: str, is_moderator: bool
    ) -> bool:
        """Update a user's moderator status"""
        try:
            results = await self.users_collection.update(
                {"_key": user_id, "is_moderator": is_moderator}
            )

            if not results or results.get("error"):
                logger.error(
                    f"Error updating moderator status for user {user_id}: {results.get('errorMessage', 'Unknown error')}"
                )
                return False

            logger.info(f"Updated user {user_id} moderator status to {is_moderator}")
            return True
        except Exception as e:
            logger.error(f"Error updating moderator status: {e}")
            return False

    async def update_user_admin_status(self, user_id: str, is_admin: bool) -> bool:
        """Update a user's admin status"""
        try:
            results = await self.users_collection.update(
                {"_key": user_id, "is_admin": is_admin}
            )

            if not results or results.get("error"):
                logger.error(
                    f"Error updating admin status for user {user_id}: {results.get('errorMessage', 'Unknown error')}"
                )
                return False

            logger.info(f"Updated user {user_id} admin status to {is_admin}")
            return True
        except Exception as e:
            logger.error(f"Error updating admin status: {e}")
            return False

    async def update_user_uploader_status(
        self, user_id: str, is_uploader: bool
    ) -> bool:
        """Update a user's uploader status"""
        try:
            results = await self.users_collection.update(
                {"_key": user_id, "is_uploader": is_uploader}
            )
            if not results or results.get("error"):
                logger.error(
                    f"Error updating uploader status for user {user_id}: {results.get('errorMessage', 'Unknown error')}"
                )
                return False

            logger.info(f"Updated user {user_id} uploader status to {is_uploader}")
            return True
        except Exception as e:
            logger.error(f"Error updating uploader status: {e}")
            return False

    async def get_all_users(self) -> List[Dict[str, Any]]:
        """Get all users"""
        try:
            cursor = await self.db.aql.execute(
                "FOR doc IN users SORT doc.created_at DESC RETURN doc"
            )
            users = []
            async with cursor:
                async for doc in cursor:
                    users.append(doc)
            return users
        except Exception as e:
            logger.error(f"Error fetching all users: {e}")
            return []

    # API Key management methods
    async def create_api_key(self, api_key_data: Dict[str, Any]) -> Optional[str]:
        """Create a new API key"""
        try:
            if "created_at" not in api_key_data:
                api_key_data["created_at"] = datetime.utcnow().isoformat()

            result = await self.api_keys_collection.insert(api_key_data)
            logger.info(f"Created API key with key: {result['_key']}")
            return result["_key"]
        except Exception as e:
            logger.error(f"Error creating API key: {e}")
            return None

    async def get_api_key_by_hash(self, key_hash: str) -> Optional[Dict[str, Any]]:
        """Get an API key by its hash"""
        try:
            cursor = await self.db.aql.execute(
                "FOR doc IN api_keys FILTER doc.key_hash == @key_hash AND doc.is_active == true LIMIT 1 RETURN doc",
                bind_vars={"key_hash": key_hash},
            )
            async with cursor:
                async for doc in cursor:
                    return doc
            return None
        except Exception as e:
            logger.error(f"Error fetching API key: {e}")
            return None

    async def get_user_api_keys(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all API keys for a user"""
        try:
            cursor = await self.db.aql.execute(
                "FOR doc IN api_keys FILTER doc.user_id == @user_id SORT doc.created_at DESC RETURN doc",
                bind_vars={"user_id": user_id},
            )
            api_keys = []
            async with cursor:
                async for doc in cursor:
                    api_keys.append(doc)
            return api_keys
        except Exception as e:
            logger.error(f"Error fetching user API keys: {e}")
            return []

    async def get_all_api_keys(self) -> List[Dict[str, Any]]:
        """Get all API keys (admin)"""
        try:
            cursor = await self.db.aql.execute(
                "FOR doc IN api_keys SORT doc.created_at DESC RETURN doc"
            )
            api_keys = []
            async with cursor:
                async for doc in cursor:
                    api_keys.append(doc)
            return api_keys
        except Exception as e:
            logger.error(f"Error fetching all API keys: {e}")
            return []

    async def revoke_api_key(self, key_id: str) -> bool:
        """Revoke (deactivate) an API key"""
        try:
            results = await self.api_keys_collection.update(
                {"_key": key_id, "is_active": False}
            )

            if not results or results.get("error"):
                logger.error(
                    f"Error revoking API key {key_id}: {results.get('errorMessage', 'Unknown error')}"
                )
                return False

            logger.info(f"Revoked API key: {key_id}")
            return True
        except Exception as e:
            logger.error(f"Error revoking API key: {e}")
            return False

    async def update_api_key_last_used(self, key_id: str) -> bool:
        """Update the last used timestamp for an API key"""
        try:
            results = await self.api_keys_collection.update(
                {
                    "_key": key_id,
                    "last_used_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            if not results or results.get("error"):
                logger.error(
                    f"Error updating API key last used {key_id}: {results.get('errorMessage', 'Unknown error')}"
                )
                return False
            return True
        except Exception as e:
            logger.error(f"Error updating API key last used: {e}")
            return False

    async def log_api_usage(self, usage_data: Dict[str, Any]) -> Optional[str]:
        """Log API usage"""
        try:
            if "timestamp" not in usage_data:
                usage_data["timestamp"] = datetime.now(timezone.utc).isoformat()

            result = await self.api_usage_collection.insert(usage_data)
            if not result or result.get("error"):
                logger.error(
                    f"Error logging API usage: {result.get('errorMessage', 'Unknown error')}"
                )
                return None
            return result["_key"]
        except Exception as e:
            logger.error(f"Error logging API usage: {e}")
            return None

    async def get_api_usage_by_key(
        self, key_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get API usage logs for a specific key"""
        try:
            cursor = await self.db.aql.execute(
                "FOR doc IN api_usage FILTER doc.api_key_id == @key_id SORT doc.timestamp DESC LIMIT @limit RETURN doc",
                bind_vars={"key_id": key_id, "limit": limit},
            )
            usage = []
            async with cursor:
                async for doc in cursor:
                    usage.append(doc)
            return usage
        except Exception as e:
            logger.error(f"Error fetching API usage: {e}")
            return []

    async def get_api_usage_by_user(
        self, user_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get API usage logs for a specific user"""
        try:
            cursor = await self.db.aql.execute(
                "FOR doc IN api_usage FILTER doc.user_id == @user_id SORT doc.timestamp DESC LIMIT @limit RETURN doc",
                bind_vars={"user_id": user_id, "limit": limit},
            )
            usage = []
            async with cursor:
                async for doc in cursor:
                    usage.append(doc)
            return usage
        except Exception as e:
            logger.error(f"Error fetching API usage by user: {e}")
            return []

    async def get_api_usage_stats_by_user(self, user_id: str) -> Dict[str, Any]:
        """Get API usage statistics for a user"""
        try:
            # Get total count
            cursor = await self.db.aql.execute(
                "FOR doc IN api_usage FILTER doc.user_id == @user_id COLLECT WITH COUNT INTO length RETURN length",
                bind_vars={"user_id": user_id},
            )
            total_calls = 0
            async with cursor:
                async for count in cursor:
                    total_calls = count

            # Get count by endpoint
            cursor = await self.db.aql.execute(
                "FOR doc IN api_usage FILTER doc.user_id == @user_id COLLECT endpoint = doc.endpoint WITH COUNT INTO count RETURN {endpoint, count}",
                bind_vars={"user_id": user_id},
            )
            by_endpoint = []
            async with cursor:
                async for item in cursor:
                    by_endpoint.append(item)

            return {"total_calls": total_calls, "by_endpoint": by_endpoint}
        except Exception as e:
            logger.error(f"Error fetching API usage stats: {e}")
            return {"total_calls": 0, "by_endpoint": []}

    # Audit log methods
    async def add_audit_log(self, log_data: Dict[str, Any]) -> Optional[str]:
        """Add an audit log entry"""
        try:
            if "timestamp" not in log_data:
                log_data["timestamp"] = datetime.utcnow().isoformat()

            result = await self.audit_logs_collection.insert(log_data)
            logger.info(
                f"Added audit log: {log_data['action']} by {log_data.get('actor_username', 'unknown')}"
            )
            return result["_key"]
        except Exception as e:
            logger.error(f"Error adding audit log: {e}")
            return None

    async def get_audit_logs(
        self,
        limit: int = 100,
        action_filter: Optional[str] = None,
        actor_id_filter: Optional[str] = None,
        target_id_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get audit logs with optional filtering"""
        try:
            query = "FOR doc IN audit_logs"
            filters = []
            bind_vars = {"limit": limit}

            if action_filter:
                filters.append("doc.action == @action")
                bind_vars["action"] = action_filter

            if actor_id_filter:
                filters.append("doc.actor_id == @actor_id")
                bind_vars["actor_id"] = actor_id_filter

            if target_id_filter:
                filters.append("doc.target_id == @target_id")
                bind_vars["target_id"] = target_id_filter

            if filters:
                query += " FILTER " + " AND ".join(filters)

            query += " SORT doc.timestamp DESC LIMIT @limit RETURN doc"

            cursor = await self.db.aql.execute(query, bind_vars=bind_vars)
            logs = []
            async with cursor:
                async for doc in cursor:
                    logs.append(doc)
            return logs
        except Exception as e:
            logger.error(f"Error fetching audit logs: {e}")
            return []

    async def get_audit_log_stats(self) -> Dict[str, Any]:
        """Get audit log statistics"""
        try:
            # Total count
            cursor = await self.db.aql.execute("RETURN LENGTH(audit_logs)")
            total_count = 0
            async with cursor:
                async for count in cursor:
                    total_count = count

            # Count by action
            cursor = await self.db.aql.execute(
                "FOR doc IN audit_logs COLLECT action = doc.action WITH COUNT INTO count RETURN {action, count}"
            )
            by_action = []
            async with cursor:
                async for item in cursor:
                    by_action.append(item)

            return {"total_logs": total_count, "by_action": by_action}
        except Exception as e:
            logger.error(f"Error fetching audit log stats: {e}")
            return {"total_logs": 0, "by_action": []}

    # Activity log methods
    async def add_activity_log(self, log_data: Dict[str, Any]) -> Optional[str]:
        """Add an activity log entry"""
        try:
            if "timestamp" not in log_data:
                log_data["timestamp"] = datetime.utcnow().isoformat()

            result = await self.activity_logs_collection.insert(log_data)
            return result["_key"]
        except Exception as e:
            logger.error(f"Error adding activity log: {e}")
            return None

    async def get_activity_logs(
        self,
        limit: int = 100,
        event_type_filter: Optional[str] = None,
        user_id_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get activity logs with optional filtering"""
        try:
            query = "FOR doc IN activity_logs"
            filters = []
            bind_vars = {"limit": limit}

            if event_type_filter:
                filters.append("doc.event_type == @event_type")
                bind_vars["event_type"] = event_type_filter

            if user_id_filter:
                filters.append("doc.user_id == @user_id")
                bind_vars["user_id"] = user_id_filter

            if filters:
                query += " FILTER " + " AND ".join(filters)

            query += " SORT doc.timestamp DESC LIMIT @limit RETURN doc"

            cursor = await self.db.aql.execute(query, bind_vars=bind_vars)
            logs = []
            async with cursor:
                async for doc in cursor:
                    logs.append(doc)
            return logs
        except Exception as e:
            logger.error(f"Error fetching activity logs: {e}")
            return []

    async def get_activity_log_stats(self) -> Dict[str, Any]:
        """Get activity log statistics"""
        try:
            # Total count
            cursor = await self.db.aql.execute("RETURN LENGTH(activity_logs)")
            total_count = 0
            async with cursor:
                async for count in cursor:
                    total_count = count

            # Count by event type
            cursor = await self.db.aql.execute(
                "FOR doc IN activity_logs COLLECT event_type = doc.event_type WITH COUNT INTO count RETURN {event_type, count}"
            )
            by_event_type = []
            async with cursor:
                async for item in cursor:
                    by_event_type.append(item)

            return {"total_logs": total_count, "by_event_type": by_event_type}
        except Exception as e:
            logger.error(f"Error fetching activity log stats: {e}")
            return {"total_logs": 0, "by_event_type": []}

    # Upload statistics methods
    async def record_upload(
        self, user_id: str, username: str, entry_id: str, size_bytes: int
    ) -> Optional[str]:
        """Record an upload in the statistics"""
        try:
            upload_data = {
                "user_id": user_id,
                "username": username,
                "entry_id": entry_id,
                "size_bytes": size_bytes,
                "timestamp": datetime.utcnow().isoformat(),
            }
            result = await self.upload_statistics_collection.insert(upload_data)
            logger.info(f"Recorded upload by {username}: {size_bytes} bytes")
            return result["_key"]
        except Exception as e:
            logger.error(f"Error recording upload: {e}")
            return None

    async def get_upload_statistics(
        self, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get upload statistics for a user or all users"""
        try:
            if user_id:
                # Get stats for specific user
                query = """
                FOR doc IN upload_statistics
                FILTER doc.user_id == @user_id
                COLLECT AGGREGATE
                    total_uploads = COUNT(1),
                    total_bytes = SUM(doc.size_bytes)
                RETURN {total_uploads, total_bytes}
                """
                bind_vars = {"user_id": user_id}
            else:
                # Get overall stats
                query = """
                FOR doc IN upload_statistics
                COLLECT AGGREGATE
                    total_uploads = COUNT(1),
                    total_bytes = SUM(doc.size_bytes)
                RETURN {total_uploads, total_bytes}
                """
                bind_vars = {}

            cursor = await self.db.aql.execute(query, bind_vars=bind_vars)
            async with cursor:
                async for result in cursor:
                    total_gb = (result.get("total_bytes", 0) or 0) / BYTES_PER_GB
                    return {
                        "total_uploads": result.get("total_uploads", 0) or 0,
                        "total_bytes": result.get("total_bytes", 0) or 0,
                        "total_gb": round(total_gb, 2),
                    }
            return {"total_uploads": 0, "total_bytes": 0, "total_gb": 0}
        except Exception as e:
            logger.error(f"Error fetching upload statistics: {e}")
            return {"total_uploads": 0, "total_bytes": 0, "total_gb": 0}

    async def get_all_uploader_statistics(self) -> List[Dict[str, Any]]:
        """Get upload statistics for all uploaders"""
        try:
            query = """
            FOR doc IN upload_statistics
            COLLECT user_id = doc.user_id, username = doc.username
            AGGREGATE
                total_uploads = COUNT(1),
                total_bytes = SUM(doc.size_bytes)
            SORT total_bytes DESC
            RETURN {
                user_id,
                username,
                total_uploads,
                total_bytes
            }
            """
            cursor = await self.db.aql.execute(query)
            stats = []
            async with cursor:
                async for doc in cursor:
                    # Calculate total_gb in Python instead of AQL
                    total_bytes = doc.get("total_bytes", 0) or 0
                    doc["total_gb"] = round(total_bytes / BYTES_PER_GB, 2)
                    stats.append(doc)
            return stats
        except Exception as e:
            logger.error(f"Error fetching all uploader statistics: {e}")
            return []

    async def get_download_statistics(
        self, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get download statistics for a user or all users"""
        try:
            if user_id:
                # Get stats for specific user
                query = """
                FOR doc IN download_history
                FILTER doc.user_id == @user_id
                COLLECT AGGREGATE
                    total_downloads = COUNT(1),
                    total_bytes = SUM(doc.size_bytes)
                RETURN {total_downloads, total_bytes}
                """
                bind_vars = {"user_id": user_id}
            else:
                # Get overall stats
                query = """
                FOR doc IN download_history
                COLLECT AGGREGATE
                    total_downloads = COUNT(1),
                    total_bytes = SUM(doc.size_bytes)
                RETURN {total_downloads, total_bytes}
                """
                bind_vars = {}

            cursor = await self.db.aql.execute(query, bind_vars=bind_vars)
            async with cursor:
                async for result in cursor:
                    total_gb = (result.get("total_bytes", 0) or 0) / BYTES_PER_GB
                    return {
                        "total_downloads": result.get("total_downloads", 0) or 0,
                        "total_bytes": result.get("total_bytes", 0) or 0,
                        "total_gb": round(total_gb, 2),
                    }
            return {"total_downloads": 0, "total_bytes": 0, "total_gb": 0}
        except Exception as e:
            logger.error(f"Error fetching download statistics: {e}")
            return {"total_downloads": 0, "total_bytes": 0, "total_gb": 0}

    async def get_user_statistics(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive statistics for a specific user"""
        try:
            upload_stats = await self.get_upload_statistics(user_id)
            download_stats = await self.get_download_statistics(user_id)

            # Calculate ratio (uploaded / downloaded)
            total_uploaded_bytes = upload_stats.get("total_bytes", 0)
            total_downloaded_bytes = download_stats.get("total_bytes", 0)

            if total_downloaded_bytes > 0:
                ratio = total_uploaded_bytes / total_downloaded_bytes
            else:
                ratio = 0.0 if total_uploaded_bytes == 0 else float("inf")

            return {
                "total_uploaded": upload_stats.get("total_uploads", 0),
                "total_uploaded_bytes": total_uploaded_bytes,
                "total_uploaded_gb": upload_stats.get("total_gb", 0),
                "total_downloaded": download_stats.get("total_downloads", 0),
                "total_downloaded_bytes": total_downloaded_bytes,
                "total_downloaded_gb": download_stats.get("total_gb", 0),
                "ratio": round(ratio, 2) if ratio != float("inf") else "∞",
            }
        except Exception as e:
            logger.error(f"Error fetching user statistics: {e}")
            return {
                "total_uploaded": 0,
                "total_uploaded_bytes": 0,
                "total_uploaded_gb": 0,
                "total_downloaded": 0,
                "total_downloaded_bytes": 0,
                "total_downloaded_gb": 0,
                "ratio": 0,
            }

    async def get_entry_download_count(self, entry_id: str) -> int:
        """Get the total download count for a specific entry"""
        try:
            query = """
            FOR doc IN download_history
            FILTER doc.entry_id == @entry_id
            COLLECT WITH COUNT INTO count
            RETURN count
            """
            cursor = await self.db.aql.execute(query, bind_vars={"entry_id": entry_id})
            async with cursor:
                async for count in cursor:
                    return count or 0
            return 0
        except Exception as e:
            logger.error(f"Error fetching entry download count: {e}")
            return 0

    async def get_all_entries_with_download_counts(
        self,
        search_query: Optional[str] = None,
        sort_by: str = "name",
        exclude_corrupt: bool = True,
    ) -> List[Dict[str, Any]]:
        """Get all entries with their download counts, report counts, and vote stats, optionally filtered and sorted

        Args:
            search_query: Optional search term to filter entries by name
            sort_by: Sort method - 'name', 'downloads', 'size', 'recent', 'likes', or 'dislikes' (default: 'name')
            exclude_corrupt: If True, exclude entries marked as corrupt (default: True)
        """
        try:
            # Build base query with corrupt filter
            corrupt_filter = (
                " AND (entry.corrupt == null OR entry.corrupt == false)"
                if exclude_corrupt
                else ""
            )

            if search_query:
                # Search with download counts, report counts, and vote stats
                # Normalize both entry name and search term by replacing underscores with spaces for search
                query = f"""
                FOR entry IN entries
                FILTER LOWER(SUBSTITUTE(entry.name, '_', ' ')) LIKE LOWER(SUBSTITUTE(CONCAT('%', @search, '%'), '_', ' ')){corrupt_filter}
                LET download_count = (
                    FOR doc IN download_history
                    FILTER doc.entry_id == entry._key
                    COLLECT WITH COUNT INTO count
                    RETURN count
                )[0] || 0
                LET report_count = (
                    FOR report IN reports
                    FILTER report.entry_id == entry._key AND report.status == 'open'
                    COLLECT WITH COUNT INTO count
                    RETURN count
                )[0] || 0
                LET vote_stats = (
                    FOR vote IN likes
                    FILTER vote.entry_id == entry._key
                    COLLECT vote_type = vote.vote_type WITH COUNT INTO count
                    RETURN {{vote_type: vote_type, count: count}}
                )
                LET likes_count = FIRST(FOR v IN vote_stats FILTER v.vote_type == 'like' RETURN v.count) || 0
                LET dislikes_count = FIRST(FOR v IN vote_stats FILTER v.vote_type == 'dislike' RETURN v.count) || 0
                LET comment_count = (
                    FOR comment IN comments
                    FILTER comment.entry_id == entry._key
                    COLLECT WITH COUNT INTO count
                    RETURN count
                )[0] || 0
                """
                bind_vars = {"search": search_query}
            else:
                # Get all entries with download counts, report counts, and vote stats
                query = f"""
                FOR entry IN entries
                FILTER true{corrupt_filter}
                LET download_count = (
                    FOR doc IN download_history
                    FILTER doc.entry_id == entry._key
                    COLLECT WITH COUNT INTO count
                    RETURN count
                )[0] || 0
                LET report_count = (
                    FOR report IN reports
                    FILTER report.entry_id == entry._key AND report.status == 'open'
                    COLLECT WITH COUNT INTO count
                    RETURN count
                )[0] || 0
                LET vote_stats = (
                    FOR vote IN likes
                    FILTER vote.entry_id == entry._key
                    COLLECT vote_type = vote.vote_type WITH COUNT INTO count
                    RETURN {{vote_type: vote_type, count: count}}
                )
                LET likes_count = FIRST(FOR v IN vote_stats FILTER v.vote_type == 'like' RETURN v.count) || 0
                LET dislikes_count = FIRST(FOR v IN vote_stats FILTER v.vote_type == 'dislike' RETURN v.count) || 0
                LET comment_count = (
                    FOR comment IN comments
                    FILTER comment.entry_id == entry._key
                    COLLECT WITH COUNT INTO count
                    RETURN count
                )[0] || 0
                """
                bind_vars = {}

            # Add sorting
            if sort_by == "downloads":
                query += " SORT download_count DESC"
            elif sort_by == "size":
                query += " SORT entry.size DESC"
            elif sort_by == "recent":
                query += " SORT entry.created_at DESC"
            elif sort_by == "likes":
                query += " SORT likes_count DESC"
            elif sort_by == "dislikes":
                query += " SORT dislikes_count DESC"
            elif sort_by == "comments":
                query += " SORT comment_count DESC"
            else:  # default to name
                query += " SORT entry.name ASC"

            query += " RETURN MERGE(entry, {download_count: download_count, report_count: report_count, likes_count: likes_count, dislikes_count: dislikes_count, comment_count: comment_count})"

            cursor = await self.db.aql.execute(query, bind_vars=bind_vars)
            entries = []
            async with cursor:
                async for entry in cursor:
                    entries.append(entry)
            return entries
        except Exception as e:
            logger.error(f"Error fetching entries with download counts: {e}")
            return []

    # Report management methods
    async def create_report(
        self,
        entry_id: str,
        entry_name: str,
        user_id: str,
        username: str,
        reason: str,
        description: str = "",
    ) -> Optional[str]:
        """Create a new report for a broken/corrupted file"""
        try:
            report_data = {
                "entry_id": entry_id,
                "entry_name": entry_name,
                "user_id": user_id,
                "username": username,
                "reason": reason,
                "description": description,
                "status": "open",  # open, resolved
                "created_at": datetime.utcnow().isoformat(),
                "resolved_at": None,
                "resolved_by": None,
                "resolved_by_username": None,
            }
            result = await self.reports_collection.insert(report_data)
            report_id = result["_key"]

            # Add report to entry's reports array
            report_entry_data = {
                "report_id": report_id,
                "user_id": user_id,
                "username": username,
                "reason": reason,
                "description": description,
                "created_at": report_data["created_at"],
            }

            # Add report to entry document
            query = """
            FOR entry IN entries
            FILTER entry._key == @entry_id
            UPDATE entry WITH {
                reports: APPEND(entry.reports || [], @report_data)
            } IN entries
            """
            await self.db.aql.execute(
                query,
                bind_vars={"entry_id": entry_id, "report_data": report_entry_data},
            )

            logger.info(f"Created report for entry {entry_id} by user {username}")
            return report_id
        except Exception as e:
            logger.error(f"Error creating report: {e}")
            return None

    async def get_all_reports(
        self, status: Optional[str] = None, entry_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all reports, optionally filtered by status or entry_id"""
        try:
            if status and entry_id:
                query = """
                FOR doc IN reports
                FILTER doc.status == @status AND doc.entry_id == @entry_id
                SORT doc.created_at DESC
                RETURN doc
                """
                bind_vars = {"status": status, "entry_id": entry_id}
            elif status:
                query = """
                FOR doc IN reports
                FILTER doc.status == @status
                SORT doc.created_at DESC
                RETURN doc
                """
                bind_vars = {"status": status}
            elif entry_id:
                query = """
                FOR doc IN reports
                FILTER doc.entry_id == @entry_id
                SORT doc.created_at DESC
                RETURN doc
                """
                bind_vars = {"entry_id": entry_id}
            else:
                query = """
                FOR doc IN reports
                SORT doc.created_at DESC
                RETURN doc
                """
                bind_vars = {}

            cursor = await self.db.aql.execute(query, bind_vars=bind_vars)
            reports = []
            async with cursor:
                async for doc in cursor:
                    reports.append(doc)
            return reports
        except Exception as e:
            logger.error(f"Error fetching reports: {e}")
            return []

    async def get_report_count_for_entry(self, entry_id: str) -> int:
        """Get the count of open reports for a specific entry"""
        try:
            query = """
            FOR doc IN reports
            FILTER doc.entry_id == @entry_id AND doc.status == 'open'
            COLLECT WITH COUNT INTO count
            RETURN count
            """
            cursor = await self.db.aql.execute(query, bind_vars={"entry_id": entry_id})
            async with cursor:
                async for count in cursor:
                    return count or 0
            return 0
        except Exception as e:
            logger.error(f"Error fetching report count: {e}")
            return 0

    async def resolve_report(
        self, report_id: str, resolved_by_id: str, resolved_by_username: str
    ) -> bool:
        """Mark a report as resolved"""
        try:
            await self.reports_collection.update(
                {
                    "_key": report_id,
                    "status": "resolved",
                    "resolved_at": datetime.utcnow().isoformat(),
                    "resolved_by": resolved_by_id,
                    "resolved_by_username": resolved_by_username,
                }
            )
            logger.info(f"Resolved report {report_id} by {resolved_by_username}")
            return True
        except Exception as e:
            logger.error(f"Error resolving report: {e}")
            return False

    async def count_reports(self, status: Optional[str] = None) -> int:
        """Count reports, optionally filtered by status"""
        try:
            if status:
                query = """
                FOR doc IN reports
                FILTER doc.status == @status
                COLLECT WITH COUNT INTO count
                RETURN count
                """
                bind_vars = {"status": status}
            else:
                query = """
                FOR doc IN reports
                COLLECT WITH COUNT INTO count
                RETURN count
                """
                bind_vars = {}

            cursor = await self.db.aql.execute(query, bind_vars=bind_vars)
            async with cursor:
                async for count in cursor:
                    return count or 0
            return 0
        except Exception as e:
            logger.error(f"Error counting reports: {e}")
            return 0

    async def get_system_statistics(self) -> Dict[str, Any]:
        """Get system-wide statistics including directories, storage, and game count"""
        try:
            # Get total game count
            query = "RETURN LENGTH(entries)"
            cursor = await self.db.aql.execute(query)
            total_games = 0
            async with cursor:
                async for count in cursor:
                    total_games = count

            # Get all directories
            directories = await self.get_all_directories()

            # Fetch game counts and sizes for all directories at once
            # This avoids N+1 query pattern
            dir_paths = [d.get("path", "") for d in directories]
            games_by_dir = {}

            if dir_paths:
                # Single aggregation query to get counts and sizes per directory
                query = """
                FOR doc IN entries
                FILTER doc.type == 'filepath'
                LET matching_dir = (
                    FOR path IN @paths
                    FILTER STARTS_WITH(doc.source, path)
                    LIMIT 1
                    RETURN path
                )[0]
                FILTER matching_dir != null
                COLLECT dir_path = matching_dir
                AGGREGATE
                    game_count = LENGTH(1),
                    total_size = SUM(doc.size)
                RETURN {
                    dir_path,
                    game_count,
                    total_size
                }
                """
                cursor = await self.db.aql.execute(
                    query, bind_vars={"paths": dir_paths}
                )
                async with cursor:
                    async for result in cursor:
                        games_by_dir[result["dir_path"]] = {
                            "game_count": result["game_count"] or 0,
                            "total_size": result["total_size"] or 0,
                        }

            # Calculate storage info for each directory
            directory_stats = []
            total_size_bytes = 0
            total_available_bytes = 0
            total_capacity_bytes = 0

            for directory in directories:
                dir_path = directory.get("path", "")
                dir_info = games_by_dir.get(
                    dir_path, {"game_count": 0, "total_size": 0}
                )

                dir_stat = {
                    "path": dir_path,
                    "exists": False,
                    "game_count": dir_info["game_count"],
                    "size_gb": round(dir_info["total_size"] / BYTES_PER_GB, 2),
                    "available_gb": 0,
                    "capacity_gb": 0,
                }

                if os.path.exists(dir_path):
                    try:
                        # Get disk usage
                        disk_usage = shutil.disk_usage(dir_path)
                        dir_stat["exists"] = True
                        dir_stat["available_gb"] = round(
                            disk_usage.free / BYTES_PER_GB, 2
                        )
                        dir_stat["capacity_gb"] = round(
                            disk_usage.total / BYTES_PER_GB, 2
                        )

                        total_available_bytes += disk_usage.free
                        total_capacity_bytes += disk_usage.total
                        total_size_bytes += dir_info["total_size"]

                    except Exception as e:
                        logger.error(
                            f"Error getting stats for directory {dir_path}: {e}"
                        )

                directory_stats.append(dir_stat)

            return {
                "total_games": total_games,
                "total_size_gb": round(total_size_bytes / BYTES_PER_GB, 2),
                "total_available_gb": round(total_available_bytes / BYTES_PER_GB, 2),
                "total_capacity_gb": round(total_capacity_bytes / BYTES_PER_GB, 2),
                "directories": directory_stats,
            }
        except Exception as e:
            logger.error(f"Error fetching system statistics: {e}")
            return {
                "total_games": 0,
                "total_size_gb": 0,
                "total_available_gb": 0,
                "total_capacity_gb": 0,
                "directories": [],
            }

    # Comment management methods
    async def create_comment(
        self,
        entry_id: str,
        user_id: str,
        username: str,
        text: str,
        parent_comment_id: Optional[str] = None,
    ) -> Optional[str]:
        """Create a new comment on an entry"""
        try:
            comment_data = {
                "entry_id": entry_id,
                "user_id": user_id,
                "username": username,
                "text": text,
                "parent_comment_id": parent_comment_id,
                "created_at": datetime.utcnow().isoformat(),
            }
            result = await self.comments_collection.insert(comment_data)
            return result["_key"]
        except Exception as e:
            logger.error(f"Error creating comment: {e}")
            return None

    async def get_comments_for_entry(
        self, entry_id: str, user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all comments for an entry with user role information and vote stats"""
        try:
            query = """
            FOR comment IN comments
            FILTER comment.entry_id == @entry_id
            LET user = FIRST(
                FOR u IN users
                FILTER u._key == comment.user_id
                RETURN {
                    is_admin: u.is_admin,
                    is_moderator: u.is_moderator,
                    is_uploader: u.is_uploader
                }
            )
            LET vote_stats = (
                FOR vote IN comment_likes
                FILTER vote.comment_id == comment._key
                COLLECT vote_type = vote.vote_type WITH COUNT INTO count
                RETURN {vote_type: vote_type, count: count}
            )
            LET likes_count = FIRST(
                FOR stat IN vote_stats
                FILTER stat.vote_type == "like"
                RETURN stat.count
            ) || 0
            LET dislikes_count = FIRST(
                FOR stat IN vote_stats
                FILTER stat.vote_type == "dislike"
                RETURN stat.count
            ) || 0
            LET user_vote = @user_id ? FIRST(
                FOR vote IN comment_likes
                FILTER vote.comment_id == comment._key AND vote.user_id == @user_id
                RETURN vote.vote_type
            ) : null
            SORT comment.created_at ASC
            RETURN MERGE(comment, {
                id: comment._key,
                user_is_admin: user.is_admin || false,
                user_is_moderator: user.is_moderator || false,
                user_is_uploader: user.is_uploader || false,
                likes_count: likes_count,
                dislikes_count: dislikes_count,
                user_vote: user_vote
            })
            """
            cursor = await self.db.aql.execute(
                query, bind_vars={"entry_id": entry_id, "user_id": user_id}
            )
            comments = []
            async with cursor:
                async for comment in cursor:
                    comments.append(comment)
            return comments
        except Exception as e:
            logger.error(f"Error fetching comments: {e}")
            return []

    async def delete_comment(self, comment_id: str) -> bool:
        """Delete a comment by ID"""
        try:
            await self.comments_collection.delete(comment_id)
            return True
        except Exception as e:
            logger.error(f"Error deleting comment: {e}")
            return False

    # Like/Dislike management methods
    async def add_or_update_vote(
        self, entry_id: str, user_id: str, vote_type: str
    ) -> bool:
        """Add or update a user's vote on an entry"""
        try:
            # Check if user already voted
            query = """
            FOR vote IN likes
            FILTER vote.entry_id == @entry_id AND vote.user_id == @user_id
            RETURN vote
            """
            cursor = await self.db.aql.execute(
                query, bind_vars={"entry_id": entry_id, "user_id": user_id}
            )
            existing_vote = None
            async with cursor:
                async for vote in cursor:
                    existing_vote = vote
                    break

            if existing_vote:
                # Update existing vote
                if existing_vote.get("vote_type") == vote_type:
                    # Same vote, remove it (toggle off)
                    await self.likes_collection.delete(existing_vote["_key"])
                else:
                    # Different vote, update it
                    await self.likes_collection.update(
                        existing_vote["_key"],
                        {
                            "vote_type": vote_type,
                            "updated_at": datetime.utcnow().isoformat(),
                        },
                    )
            else:
                # Create new vote
                vote_data = {
                    "entry_id": entry_id,
                    "user_id": user_id,
                    "vote_type": vote_type,
                    "created_at": datetime.utcnow().isoformat(),
                }
                await self.likes_collection.insert(vote_data)

            return True
        except Exception as e:
            logger.error(f"Error adding/updating vote: {e}")
            return False

    async def get_vote_stats_for_entry(self, entry_id: str) -> Dict[str, int]:
        """Get like and dislike counts for an entry"""
        try:
            query = """
            FOR vote IN likes
            FILTER vote.entry_id == @entry_id
            COLLECT vote_type = vote.vote_type WITH COUNT INTO count
            RETURN {vote_type: vote_type, count: count}
            """
            cursor = await self.db.aql.execute(query, bind_vars={"entry_id": entry_id})
            stats = {"likes": 0, "dislikes": 0}
            async with cursor:
                async for stat in cursor:
                    if stat["vote_type"] == "like":
                        stats["likes"] = stat["count"]
                    elif stat["vote_type"] == "dislike":
                        stats["dislikes"] = stat["count"]
            return stats
        except Exception as e:
            logger.error(f"Error fetching vote stats: {e}")
            return {"likes": 0, "dislikes": 0}

    async def get_user_vote_for_entry(
        self, entry_id: str, user_id: str
    ) -> Optional[str]:
        """Get a user's vote on an entry (like, dislike, or None)"""
        try:
            query = """
            FOR vote IN likes
            FILTER vote.entry_id == @entry_id AND vote.user_id == @user_id
            RETURN vote.vote_type
            """
            cursor = await self.db.aql.execute(
                query, bind_vars={"entry_id": entry_id, "user_id": user_id}
            )
            async with cursor:
                async for vote_type in cursor:
                    return vote_type
            return None
        except Exception as e:
            logger.error(f"Error fetching user vote: {e}")
            return None

    async def add_or_update_comment_vote(
        self, comment_id: str, user_id: str, vote_type: str
    ) -> bool:
        """Add or update a user's vote on a comment"""
        try:
            # Check if user already voted
            query = """
            FOR vote IN comment_likes
            FILTER vote.comment_id == @comment_id AND vote.user_id == @user_id
            RETURN vote
            """
            cursor = await self.db.aql.execute(
                query, bind_vars={"comment_id": comment_id, "user_id": user_id}
            )
            existing_vote = None
            async with cursor:
                async for vote in cursor:
                    existing_vote = vote
                    break

            if existing_vote:
                # Update existing vote
                if existing_vote.get("vote_type") == vote_type:
                    # Same vote, remove it (toggle off)
                    await self.comment_likes_collection.delete(existing_vote["_key"])
                else:
                    # Different vote, update it
                    await self.comment_likes_collection.update(
                        existing_vote["_key"],
                        {
                            "vote_type": vote_type,
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        },
                    )
            else:
                # Create new vote
                vote_data = {
                    "comment_id": comment_id,
                    "user_id": user_id,
                    "vote_type": vote_type,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                await self.comment_likes_collection.insert(vote_data)

            return True
        except Exception as e:
            logger.error(f"Error adding/updating comment vote: {e}")
            return False

    async def get_comment_vote_stats(self, comment_id: str) -> Dict[str, int]:
        """Get like and dislike counts for a comment"""
        try:
            query = """
            FOR vote IN comment_likes
            FILTER vote.comment_id == @comment_id
            COLLECT vote_type = vote.vote_type WITH COUNT INTO count
            RETURN {vote_type: vote_type, count: count}
            """
            cursor = await self.db.aql.execute(query, bind_vars={"comment_id": comment_id})
            stats = {"likes": 0, "dislikes": 0}
            async with cursor:
                async for stat in cursor:
                    if stat["vote_type"] == "like":
                        stats["likes"] = stat["count"]
                    elif stat["vote_type"] == "dislike":
                        stats["dislikes"] = stat["count"]
            return stats
        except Exception as e:
            logger.error(f"Error fetching comment vote stats: {e}")
            return {"likes": 0, "dislikes": 0}

    async def get_user_vote_for_comment(
        self, comment_id: str, user_id: str
    ) -> Optional[str]:
        """Get a user's vote on a comment (like, dislike, or None)"""
        try:
            query = """
            FOR vote IN comment_likes
            FILTER vote.comment_id == @comment_id AND vote.user_id == @user_id
            RETURN vote.vote_type
            """
            cursor = await self.db.aql.execute(
                query, bind_vars={"comment_id": comment_id, "user_id": user_id}
            )
            async with cursor:
                async for vote_type in cursor:
                    return vote_type
            return None
        except Exception as e:
            logger.error(f"Error fetching user comment vote: {e}")
            return None

    async def add_to_send_queue(self, user_id: str, entry_id: str) -> bool:
        """Add an entry to user's send queue"""
        try:
            # Check if entry is already in queue
            cursor = await self.db.aql.execute(
                """
                FOR item IN send_queue
                FILTER item.user_id == @user_id AND item.entry_id == @entry_id AND item.status IN ['pending', 'processing']
                RETURN item
                """,
                bind_vars={"user_id": user_id, "entry_id": entry_id}
            )

            exists = False
            async with cursor:
                async for _ in cursor:
                    exists = True
                    break

            if exists:
                logger.info(f"Entry {entry_id} already in queue for user {user_id}")
                return True  # Already in queue, return success

            # Add to queue
            queue_item = {
                "user_id": user_id,
                "entry_id": entry_id,
                "status": "pending",  # pending, processing, completed, failed
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

            result = await self.send_queue_collection.insert(queue_item)
            logger.info(f"Added entry {entry_id} to send queue for user {user_id}: {result['_key']}")
            return True

        except Exception as e:
            logger.error(f"Error adding to send queue: {e}")
            return False

    async def get_send_queue(self, user_id: str) -> List[Dict[str, Any]]:
        """Get user's send queue items with entry details"""
        try:
            cursor = await self.db.aql.execute(
                """
                FOR item IN send_queue
                FILTER item.user_id == @user_id AND item.status IN ['pending', 'processing']
                SORT item.created_at ASC
                LET entry = DOCUMENT('entries', item.entry_id)
                FILTER entry != null
                RETURN {
                    queue_item_id: item._key,
                    entry_id: item.entry_id,
                    entry_name: CONCAT(entry.name, '.', entry.file_type),
                    entry_source: entry.source,
                    entry_size: entry.size,
                    status: item.status,
                    created_at: item.created_at,
                    updated_at: item.updated_at,
                    progress_percent: item.progress_percent,
                    bytes_transferred: item.bytes_transferred,
                    transfer_speed: item.transfer_speed,
                    error_message: item.error_message
                }
                """,
                bind_vars={"user_id": user_id}
            )

            items = []
            async with cursor:
                async for item in cursor:
                    items.append(item)

            return items

        except Exception as e:
            logger.error(f"Error fetching send queue: {e}")
            return []

    async def get_all_send_queue_items(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all send queue items for a user (including completed/failed)"""
        try:
            cursor = await self.db.aql.execute(
                """
                FOR item IN send_queue
                FILTER item.user_id == @user_id
                SORT item.created_at DESC
                LET entry = DOCUMENT('entries', item.entry_id)
                RETURN {
                    queue_item_id: item._key,
                    entry_id: item.entry_id,
                    entry_name: CONCAT(entry.name, '.', entry.file_type),
                    entry_source: entry.source,
                    entry_size: entry.size,
                    status: item.status,
                    created_at: item.created_at,
                    updated_at: item.updated_at,
                    progress_percent: item.progress_percent,
                    bytes_transferred: item.bytes_transferred,
                    transfer_speed: item.transfer_speed,
                    error_message: item.error_message
                }
                """,
                bind_vars={"user_id": user_id}
            )

            items = []
            async with cursor:
                async for item in cursor:
                    items.append(item)

            return items

        except Exception as e:
            logger.error(f"Error fetching all send queue items: {e}")
            return []

    async def update_send_queue_item(self, user_id: str, queue_item_id: str, status: str) -> bool:
        """Update status of a send queue item"""
        try:
            # First verify the item belongs to the user
            cursor = await self.db.aql.execute(
                """
                FOR item IN send_queue
                FILTER item._key == @queue_item_id AND item.user_id == @user_id
                RETURN item
                """,
                bind_vars={"queue_item_id": queue_item_id, "user_id": user_id}
            )

            exists = False
            async with cursor:
                async for _ in cursor:
                    exists = True
                    break

            if not exists:
                logger.warning(f"Queue item {queue_item_id} not found for user {user_id}")
                return False

            # Update the status
            result = await self.send_queue_collection.update({
                "_key": queue_item_id,
                "status": status,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })

            if result and not result.get("error"):
                logger.info(f"Updated queue item {queue_item_id} to status {status}")

                # If completed or failed, we could optionally delete it after some time
                # For now, we'll keep it for history

                return True
            else:
                logger.error(f"Error updating queue item: {result.get('errorMessage', 'Unknown error')}")
                return False

        except Exception as e:
            logger.error(f"Error updating send queue item: {e}")
            return False

    async def update_send_queue_progress(
        self,
        user_id: str,
        queue_item_id: str,
        progress_percent: Optional[int] = None,
        bytes_transferred: Optional[int] = None,
        transfer_speed: Optional[float] = None,
        status: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """Update progress information for a send queue item"""
        try:
            # First verify the item belongs to the user
            cursor = await self.db.aql.execute(
                """
                FOR item IN send_queue
                FILTER item._key == @queue_item_id AND item.user_id == @user_id
                RETURN item
                """,
                bind_vars={"queue_item_id": queue_item_id, "user_id": user_id}
            )

            exists = False
            async with cursor:
                async for _ in cursor:
                    exists = True
                    break

            if not exists:
                logger.warning(f"Queue item {queue_item_id} not found for user {user_id}")
                return False

            # Build update document
            update_doc = {
                "_key": queue_item_id,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

            if progress_percent is not None:
                update_doc["progress_percent"] = progress_percent
            if bytes_transferred is not None:
                update_doc["bytes_transferred"] = bytes_transferred
            if transfer_speed is not None:
                update_doc["transfer_speed"] = transfer_speed
            if status is not None:
                update_doc["status"] = status
            if error_message is not None:
                update_doc["error_message"] = error_message

            # Update the item
            result = await self.send_queue_collection.update(update_doc)

            if result and not result.get("error"):
                return True
            else:
                logger.error(f"Error updating queue progress: {result.get('errorMessage', 'Unknown error')}")
                return False

        except Exception as e:
            logger.error(f"Error updating send queue progress: {e}")
            return False

    async def delete_send_queue_item(self, user_id: str, queue_item_id: str) -> bool:
        """Delete a send queue item"""
        try:
            # First verify the item belongs to the user
            cursor = await self.db.aql.execute(
                """
                FOR item IN send_queue
                FILTER item._key == @queue_item_id AND item.user_id == @user_id
                RETURN item
                """,
                bind_vars={"queue_item_id": queue_item_id, "user_id": user_id}
            )

            exists = False
            async with cursor:
                async for _ in cursor:
                    exists = True
                    break

            if not exists:
                logger.warning(f"Queue item {queue_item_id} not found for user {user_id}")
                return False

            # Delete the item
            await self.send_queue_collection.delete(queue_item_id)
            logger.info(f"Deleted queue item {queue_item_id} for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting send queue item: {e}")
            return False

    async def clear_send_queue(self, user_id: str) -> bool:
        """Clear all items from user's send queue"""
        try:
            # Delete all queue items for the user
            cursor = await self.db.aql.execute(
                """
                FOR item IN send_queue
                FILTER item.user_id == @user_id
                REMOVE item IN send_queue
                RETURN OLD
                """,
                bind_vars={"user_id": user_id}
            )

            count = 0
            async with cursor:
                async for _ in cursor:
                    count += 1

            logger.info(f"Cleared {count} queue items for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error clearing send queue: {e}")
            return False


# Global database instance
db = Database()
