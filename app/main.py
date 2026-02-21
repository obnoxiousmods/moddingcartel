import asyncio
import logging
import os
import sys

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from app.config import Config
from app.database import db
from app.middleware.api_auth import APIAuthMiddleware
from app.routes.admin import (
    admin_activity_logs,
    admin_add_directory,
    admin_api_keys,
    admin_audit_logs,
    admin_clear_entries,
    admin_dashboard,
    admin_delete_directory,
    admin_directories,
    admin_force_password_change,
    admin_init_page,
    admin_init_submit,
    admin_migrate_passwords,
    admin_password_migration_status,
    admin_reports,
    admin_rescan_all,
    admin_resolve_report,
    admin_revoke_api_key,
    admin_scan_directory,
    admin_storage_info,
    admin_update_user_role,
    admin_upload_statistics,
    admin_user_api_usage,
    admin_users,
)
from app.routes.api import (
    api_login,
    clear_send_queue,
    compute_file_hashes,
    create_entry_comment,
    delete_entry,
    delete_send_queue_item,
    download_entry,
    get_comment_vote_stats,
    get_entry_comments,
    get_entry_info,
    get_entry_vote_stats,
    get_send_queue,
    get_user_stats,
    list_entries,
    send_to_switch,
    submit_report,
    update_send_queue_item,
    update_send_queue_progress,
    vote_comment,
    vote_entry,
)
from app.routes.api_keys import (
    api_keys_page,
    api_usage_page,
    generate_api_key,
    revoke_api_key,
)
from app.routes.auth import (
    login_page,
    login_submit,
    logout,
    register_page,
    register_submit,
)
from app.routes.mod import (
    mod_approve_request,
    mod_clear_all_corrupt_flags,
    mod_corrupt_games,
    mod_dashboard,
    mod_force_password_change,
    mod_mark_entry_valid,
    mod_reject_request,
    mod_requests,
    user_requests_page,
    user_submit_request,
)
from app.routes.pages import api_docs_page, index, search_page
from app.routes.queue import game_queue_page, get_queue_status
from app.routes.settings import (
    change_password,
    download_history_page,
    settings_page,
    totp_disable,
    totp_enable,
    totp_setup_page,
    totp_verify_and_enable,
)
from app.routes.uploader import (
    uploader_approve_request,
    uploader_dashboard,
    uploader_game_requests,
    uploader_get_directories,
    uploader_reject_request,
    uploader_upload_page,
    uploader_upload_submit,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Background task control
background_hash_task = None
background_db_health_task = None


async def check_db_health():
    """Background service that checks ArangoDB connection every 15 seconds and exits if invalid"""
    while True:
        try:
            if not await db.ping():
                logger.error("→ ArangoDB connection lost. Exiting so systemd can restart.")
                sys.exit(1)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"→ ArangoDB health check failed: {e}. Exiting so systemd can restart.")
            sys.exit(1)
        await asyncio.sleep(15)


# Background hash computation service
async def compute_hashes_for_unhashed_entries():
    """Background service to compute hashes for entries without hashes"""
    while True:
        try:
            # Wait 10 minutes between runs
            await asyncio.sleep(600)  # 600 seconds = 10 minutes

            if not Config.is_initialized():
                continue

            logger.info("→ Starting background hash computation cycle...")

            # Query for entries without hashes or stuck in processing
            cursor = await db.db.aql.execute("""
                FOR doc IN entries
                FILTER doc.type == 'filepath' AND (
                    doc.md5_hash == null OR
                    doc.sha256_hash == null OR
                    doc.md5_hash == 'processing' OR
                    doc.sha256_hash == 'processing'
                )
                RETURN {
                    _key: doc._key,
                    source: doc.source,
                    name: doc.name,
                    size: doc.size,
                    md5_hash: doc.md5_hash,
                    sha256_hash: doc.sha256_hash
                }
            """)

            entries_to_process = []
            async with cursor:
                async for doc in cursor:
                    entries_to_process.append(doc)

            if not entries_to_process:
                logger.info("→ No entries need hash computation")
                continue

            logger.info(
                f"→ Found {len(entries_to_process)} entries needing hash computation"
            )

            # Sort entries by file size (smallest first) for faster processing
            # Get actual file sizes for entries without size in DB
            for entry in entries_to_process:
                if not entry.get("size"):
                    filepath = entry.get("source")
                    if filepath and os.path.exists(filepath) and os.path.isfile(filepath):
                        try:
                            entry["size"] = os.path.getsize(filepath)
                        except Exception:
                            entry["size"] = 0
                    else:
                        entry["size"] = 0

            # Sort by size (smallest first)
            entries_to_process.sort(key=lambda x: x.get("size", 0))

            logger.info(
                "→ Processing entries in order from smallest to largest file"
            )

            # Build a dictionary to track hashes and detect duplicates
            hash_dict = {}  # key: sha256_hash, value: list of (entry_id, entry_name, filepath)

            # Process each entry
            for entry in entries_to_process:
                try:
                    entry_id = entry.get("_key")
                    filepath = entry.get("source")
                    entry_name = entry.get("name", "Unknown")

                    # Verify file exists
                    if (
                        not filepath
                        or not os.path.exists(filepath)
                        or not os.path.isfile(filepath)
                    ):
                        logger.warning(
                            f"→ Skipping {entry_name} ({entry_id}): File not found at {filepath}"
                        )
                        # Clear processing markers for missing files
                        if (
                            entry.get("md5_hash") == "processing"
                            or entry.get("sha256_hash") == "processing"
                        ):
                            await db.update_entry_hashes(entry_id, None, None)
                        continue

                    logger.info(f"→ Computing hashes for: {entry_name} ({entry_id})")

                    # Import here to avoid circular import
                    from app.routes.api import _compute_hashes_sync

                    # Mark as processing
                    await db.update_entry_hashes(entry_id, "processing", "processing")

                    # Compute hashes in thread pool
                    md5_result, sha256_result = await asyncio.to_thread(
                        _compute_hashes_sync, filepath
                    )

                    # Store results
                    await db.update_entry_hashes(entry_id, md5_result, sha256_result)

                    logger.info(f"→ Successfully computed hashes for: {entry_name}")

                    # Track hash for duplicate detection
                    if sha256_result and sha256_result != "processing":
                        if sha256_result not in hash_dict:
                            hash_dict[sha256_result] = []
                        hash_dict[sha256_result].append((entry_id, entry_name, filepath))

                except Exception as e:
                    logger.error(
                        f"→ Error computing hashes for entry {entry.get('_key')}: {e}",
                        exc_info=True,
                    )
                    # Clear processing markers on error
                    try:
                        await db.update_entry_hashes(entry.get("_key"), None, None)
                    except Exception:
                        pass

            # Now check for duplicates and delete them
            logger.info("→ Checking for duplicate hashes...")
            duplicates_found = 0
            for sha256_hash, entries_list in hash_dict.items():
                if len(entries_list) > 1:
                    # Found duplicate! Keep the first one, delete the rest
                    logger.warning(f"→ Found {len(entries_list)} entries with same hash {sha256_hash}")
                    for i, (entry_id, entry_name, filepath) in enumerate(entries_list):
                        if i == 0:
                            logger.info(f"→ Keeping: {entry_name} ({entry_id})")
                        else:
                            logger.info(f"→ Deleting duplicate: {entry_name} ({entry_id})")
                            try:
                                # Delete the file from disk
                                if os.path.exists(filepath):
                                    os.remove(filepath)
                                    logger.info(f"→ Deleted file: {filepath}")
                                
                                # Delete the entry from database
                                await db.delete_entry(entry_id)
                                logger.info(f"→ Deleted database entry: {entry_id}")
                                duplicates_found += 1
                            except Exception as e:
                                logger.error(f"→ Error deleting duplicate {entry_id}: {e}")

            if duplicates_found > 0:
                logger.info(f"→ Deleted {duplicates_found} duplicate entries")
            else:
                logger.info("→ No duplicate hashes found")

            logger.info("→ Background hash computation cycle completed")

        except asyncio.CancelledError:
            logger.info("→ Background hash computation service cancelled")
            break
        except Exception as e:
            logger.error(f"→ Error in background hash computation: {e}", exc_info=True)
            # Continue running even if there's an error


# Templates
templates = Jinja2Templates(directory="app/templates")

# Routes
routes = [
    Route("/", index),
    Route("/search", search_page),
    Route("/api-docs", api_docs_page),
    Route("/api/list", list_entries),
    Route("/api/download/{entry_id}", download_entry),
    Route("/api/reports/submit", submit_report, methods=["POST"]),
    Route("/api/entries/{entry_id}/hashes", compute_file_hashes, methods=["GET"]),
    Route("/api/entries/{entry_id}/info", get_entry_info, methods=["GET"]),
    Route("/api/entries/{entry_id}/delete", delete_entry, methods=["POST"]),
    Route("/api/entries/{entry_id}/comments", get_entry_comments, methods=["GET"]),
    Route("/api/entries/{entry_id}/comments", create_entry_comment, methods=["POST"]),
    Route("/api/entries/{entry_id}/vote", vote_entry, methods=["POST"]),
    Route("/api/entries/{entry_id}/votes", get_entry_vote_stats, methods=["GET"]),
    Route("/api/comments/{comment_id}/vote", vote_comment, methods=["POST"]),
    Route("/api/comments/{comment_id}/votes", get_comment_vote_stats, methods=["GET"]),
    Route("/api/user/stats", get_user_stats, methods=["GET"]),
    Route("/api/auth/login", api_login, methods=["POST"]),
    Route("/api/send-to-switch", send_to_switch, methods=["POST"]),
    Route("/api/send-queue", get_send_queue, methods=["GET"]),
    Route("/api/send-queue/update", update_send_queue_item, methods=["POST"]),
    Route("/api/send-queue/progress", update_send_queue_progress, methods=["POST"]),
    Route("/api/send-queue/delete", delete_send_queue_item, methods=["POST"]),
    Route("/api/send-queue/clear", clear_send_queue, methods=["POST"]),
    Route("/api/queue/status", get_queue_status, methods=["GET"]),
    Route("/game-queue", game_queue_page, methods=["GET"]),
    Route("/login", login_page, methods=["GET"]),
    Route("/login", login_submit, methods=["POST"]),
    Route("/register", register_page, methods=["GET"]),
    Route("/register", register_submit, methods=["POST"]),
    Route("/logout", logout, methods=["GET"]),
    Route("/settings", settings_page, methods=["GET"]),
    Route("/settings/change-password", change_password, methods=["POST"]),
    Route("/settings/download-history", download_history_page, methods=["GET"]),
    Route("/settings/totp", totp_setup_page, methods=["GET"]),
    Route("/settings/totp/enable", totp_enable, methods=["POST"]),
    Route("/settings/totp/verify", totp_verify_and_enable, methods=["POST"]),
    Route("/settings/totp/disable", totp_disable, methods=["POST"]),
    Route("/settings/api-keys", api_keys_page, methods=["GET"]),
    Route("/settings/api-keys/generate", generate_api_key, methods=["POST"]),
    Route("/settings/api-keys/revoke", revoke_api_key, methods=["POST"]),
    Route("/settings/api-usage", api_usage_page, methods=["GET"]),
    Route("/requests", user_requests_page, methods=["GET"]),
    Route("/requests/submit", user_submit_request, methods=["POST"]),
    Route("/modcp", mod_dashboard),
    Route("/modcp/requests", mod_requests, methods=["GET"]),
    Route("/modcp/requests/approve", mod_approve_request, methods=["POST"]),
    Route("/modcp/requests/reject", mod_reject_request, methods=["POST"]),
    Route(
        "/modcp/users/force-change-password",
        mod_force_password_change,
        methods=["POST"],
    ),
    Route("/modcp/corrupt-games", mod_corrupt_games, methods=["GET"]),
    Route("/modcp/corrupt-games/mark-valid", mod_mark_entry_valid, methods=["POST"]),
    Route(
        "/modcp/corrupt-games/clear-all", mod_clear_all_corrupt_flags, methods=["POST"]
    ),
    Route("/uploadercp", uploader_dashboard),
    Route("/uploadercp/game-requests", uploader_game_requests, methods=["GET"]),
    Route(
        "/uploadercp/game-requests/approve", uploader_approve_request, methods=["POST"]
    ),
    Route(
        "/uploadercp/game-requests/reject", uploader_reject_request, methods=["POST"]
    ),
    Route("/uploadercp/upload", uploader_upload_page, methods=["GET"]),
    Route("/uploadercp/upload", uploader_upload_submit, methods=["POST"]),
    Route("/uploadercp/directories", uploader_get_directories, methods=["GET"]),
    Route("/admincp/init", admin_init_page, methods=["GET"]),
    Route("/admincp/init", admin_init_submit, methods=["POST"]),
    Route("/admincp", admin_dashboard),
    Route("/admincp/directories", admin_directories, methods=["GET"]),
    Route("/admincp/directories/add", admin_add_directory, methods=["POST"]),
    Route("/admincp/directories/delete", admin_delete_directory, methods=["POST"]),
    Route("/admincp/directories/scan", admin_scan_directory, methods=["POST"]),
    Route("/admincp/directories/clear", admin_clear_entries, methods=["POST"]),
    Route("/admincp/directories/rescan", admin_rescan_all, methods=["POST"]),
    Route("/admincp/users", admin_users, methods=["GET"]),
    Route("/admincp/users/update-role", admin_update_user_role, methods=["POST"]),
    Route(
        "/admincp/users/force-change-password",
        admin_force_password_change,
        methods=["POST"],
    ),
    Route("/admincp/api-keys", admin_api_keys, methods=["GET"]),
    Route("/admincp/api-keys/revoke", admin_revoke_api_key, methods=["POST"]),
    Route("/admincp/api-usage", admin_user_api_usage, methods=["GET"]),
    Route("/admincp/audit-logs", admin_audit_logs, methods=["GET"]),
    Route("/admincp/activity-logs", admin_activity_logs, methods=["GET"]),
    Route("/admincp/storage-info", admin_storage_info, methods=["GET"]),
    Route("/admincp/upload-statistics", admin_upload_statistics, methods=["GET"]),
    Route("/admincp/reports", admin_reports, methods=["GET"]),
    Route("/admincp/reports/resolve", admin_resolve_report, methods=["POST"]),
    Route(
        "/admincp/password-migration/status",
        admin_password_migration_status,
        methods=["GET"],
    ),
    Route(
        "/admincp/password-migration/migrate", admin_migrate_passwords, methods=["POST"]
    ),
    Mount("/static", StaticFiles(directory="static"), name="static"),
]

# Middleware
middleware = [
    Middleware(SessionMiddleware, secret_key=Config.SECRET_KEY()),
    Middleware(APIAuthMiddleware),
]

# Create Starlette application
app = Starlette(
    debug=True,
    routes=routes,
    middleware=middleware,
)


# Startup event
@app.on_event("startup")
async def startup():
    global background_hash_task, background_db_health_task
    logger.info("→ App starting...")

    # Only try to connect to database if initialized
    if Config.is_initialized():
        try:
            await db.connect()
            logger.info("→ Database connected successfully")

            # Validate the connection is working on startup
            if not await db.ping():
                logger.error("→ ArangoDB connection invalid on startup. Exiting so systemd can restart.")
                sys.exit(1)

            # Start background DB health check service
            background_db_health_task = asyncio.create_task(check_db_health())
            logger.info("→ ArangoDB health check service started (every 15 seconds)")

            # Start background hash computation service
            background_hash_task = asyncio.create_task(
                compute_hashes_for_unhashed_entries()
            )
            logger.info("→ Background hash computation service started")

            # Run initial hash computation immediately (in background, don't wait)
            asyncio.create_task(run_initial_hash_computation())

        except SystemExit:
            raise
        except Exception as e:
            logger.error(f"→ Failed to connect to database: {e}")
            logger.error("→ Exiting so systemd can restart.")
            sys.exit(1)
    else:
        logger.info("→ System not initialized. Please visit /admincp/init to set up.")


async def run_initial_hash_computation():
    """Run hash computation immediately on startup"""
    try:
        await asyncio.sleep(5)  # Wait 5 seconds after startup to let things settle
        logger.info("→ Running initial hash computation...")

        # Query for entries without hashes or stuck in processing
        cursor = await db.db.aql.execute("""
            FOR doc IN entries
            FILTER doc.type == 'filepath' AND (
                doc.md5_hash == null OR
                doc.sha256_hash == null OR
                doc.md5_hash == 'processing' OR
                doc.sha256_hash == 'processing'
            )
            RETURN {
                _key: doc._key,
                source: doc.source,
                name: doc.name,
                size: doc.size,
                md5_hash: doc.md5_hash,
                sha256_hash: doc.sha256_hash
            }
        """)

        entries_to_process = []
        async with cursor:
            async for doc in cursor:
                entries_to_process.append(doc)

        if not entries_to_process:
            logger.info("→ No entries need initial hash computation")
            return

        logger.info(
            f"→ Found {len(entries_to_process)} entries needing initial hash computation"
        )

        # Sort entries by file size (smallest first) for faster processing
        # Get actual file sizes for entries without size in DB
        for entry in entries_to_process:
            if not entry.get("size"):
                filepath = entry.get("source")
                if filepath and os.path.exists(filepath) and os.path.isfile(filepath):
                    try:
                        entry["size"] = os.path.getsize(filepath)
                    except Exception:
                        entry["size"] = 0
                else:
                    entry["size"] = 0

        # Sort by size (smallest first)
        entries_to_process.sort(key=lambda x: x.get("size", 0))

        logger.info(
            "→ Processing entries in order from smallest to largest file"
        )

        # Process each entry
        for entry in entries_to_process:
            try:
                entry_id = entry.get("_key")
                filepath = entry.get("source")
                entry_name = entry.get("name", "Unknown")

                # Verify file exists
                if (
                    not filepath
                    or not os.path.exists(filepath)
                    or not os.path.isfile(filepath)
                ):
                    logger.warning(
                        f"→ Skipping {entry_name} ({entry_id}): File not found at {filepath}"
                    )
                    # Clear processing markers for missing files
                    if (
                        entry.get("md5_hash") == "processing"
                        or entry.get("sha256_hash") == "processing"
                    ):
                        await db.update_entry_hashes(entry_id, None, None)
                    continue

                logger.info(f"→ Computing hashes for: {entry_name} ({entry_id})")

                # Import here to avoid circular import
                from app.routes.api import _compute_hashes_sync

                # Mark as processing
                await db.update_entry_hashes(entry_id, "processing", "processing")

                # Compute hashes in thread pool
                md5_result, sha256_result = await asyncio.to_thread(
                    _compute_hashes_sync, filepath
                )

                # Store results
                await db.update_entry_hashes(entry_id, md5_result, sha256_result)

                logger.info(f"→ Successfully computed hashes for: {entry_name}")
            except Exception as e:
                logger.error(
                    f"→ Error computing hashes for entry {entry.get('_key')}: {e}",
                    exc_info=True,
                )
                # Clear processing markers on error
                try:
                    await db.update_entry_hashes(entry.get("_key"), None, None)
                except Exception:
                    pass

        logger.info("→ Initial hash computation completed")

    except Exception as e:
        logger.error(f"→ Error in initial hash computation: {e}", exc_info=True)


# Shutdown event
@app.on_event("shutdown")
async def shutdown():
    global background_hash_task, background_db_health_task
    logger.info("→ App shutting down...")

    # Cancel background DB health check task
    if background_db_health_task:
        background_db_health_task.cancel()
        try:
            await background_db_health_task
        except asyncio.CancelledError:
            pass
        logger.info("→ ArangoDB health check service stopped")

    # Cancel background hash task
    if background_hash_task:
        background_hash_task.cancel()
        try:
            await background_hash_task
        except asyncio.CancelledError:
            pass
        logger.info("→ Background hash computation service stopped")

    if Config.is_initialized():
        try:
            await db.disconnect()
            logger.info("→ Database disconnected")
        except Exception as e:
            logger.error(f"→ Error disconnecting from database: {e}")
