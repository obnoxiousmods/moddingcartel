import asyncio
import hashlib
import logging
import os

from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, RedirectResponse

from app.config import Config
from app.database import db
from app.utils.ip_utils import format_ip_for_log, get_ip_info

logger = logging.getLogger(__name__)


async def list_entries(request: Request):
    """API endpoint to list all entries"""
    # Require authentication - either session or API key
    has_session = request.session.get("user_id") is not None
    has_api_auth = getattr(request.state, "authenticated", False)

    if not has_session and not has_api_auth:
        return JSONResponse(
            {"error": "Authentication required. Please log in or use an API key."},
            status_code=401,
        )

    try:
        # Get query parameters
        search_query = request.query_params.get("search")
        sort_by = request.query_params.get("sort_by", "name")

        # Validate sort_by parameter (name, downloads, size, recent, likes, dislikes, or comments)
        if sort_by not in ["name", "downloads", "size", "recent", "likes", "dislikes", "comments"]:
            sort_by = "name"

        # Get entries with download counts
        entries = await db.get_all_entries_with_download_counts(
            search_query=search_query, sort_by=sort_by
        )

        return JSONResponse({"entries": entries})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def download_entry(request: Request):
    """API endpoint to download an entry"""
    # Require authentication - either session or API key
    has_session = request.session.get("user_id") is not None
    has_api_auth = getattr(request.state, "authenticated", False)

    if not has_session and not has_api_auth:
        return JSONResponse(
            {"error": "Authentication required. Please log in or use an API key."},
            status_code=401,
        )

    try:
        entry_id = request.path_params.get("entry_id")

        # Get the entry from the database
        entry = await db.get_entry_by_id(entry_id)

        if not entry:
            return JSONResponse({"error": "Entry not found"}, status_code=404)

        # Track download if user is logged in (session-based)
        user_id = request.session.get("user_id")
        username = request.session.get("username")
        ip_info = get_ip_info(request)

        # For API key authentication, use the authenticated user_id
        if not user_id and has_api_auth:
            user_id = request.state.user_id
            # Get username from database for API key users
            user_doc = await db.get_user_by_id(user_id)
            if user_doc:
                username = user_doc.get("username", "api_user")

        if user_id:
            await db.add_download_history(
                user_id=user_id,
                entry_id=entry_id,
                entry_name=entry.get("name", "Unknown"),
                size_bytes=entry.get("size", 0),
            )

            # Log the download activity with IP information
            activity_data = {
                "event_type": "download",
                "user_id": user_id,
                "username": username,
                "details": {
                    "entry_id": entry_id,
                    "entry_name": entry.get("name", "Unknown"),
                    "file_type": entry.get("file_type", "unknown"),
                    "source_type": entry.get("type", "unknown"),
                },
                "ip_address": ip_info["ip_address"],
                "client_ip": ip_info["client_ip"],
            }
            if "forwarded_ip" in ip_info:
                activity_data["forwarded_ip"] = ip_info["forwarded_ip"]

            await db.add_activity_log(activity_data)

        # If it's a URL, redirect to it
        if entry.get("type") == "url":
            return RedirectResponse(url=entry.get("source"))

        # If it's a filepath, serve the file with security validation
        filepath = entry.get("source")

        # Validate the filepath is within allowed directories
        try:
            filepath_resolved = os.path.abspath(filepath)

            # Get list of allowed directories from config or use defaults
            # These should be directories where game files are stored
            allowed_dirs = []

            # Add configured upload directory
            upload_dir = Config.get("upload.directory", "/app/uploads")
            if upload_dir:
                allowed_dirs.append(os.path.abspath(upload_dir))

            # Add any scan directories from the database
            scan_dirs = await db.get_all_directories()
            for dir_entry in scan_dirs:
                dir_path = dir_entry.get("path")
                if dir_path:
                    allowed_dirs.append(os.path.abspath(dir_path))

            # Check if filepath is within any allowed directory
            is_allowed = False
            for allowed_dir in allowed_dirs:
                # Ensure the file is within the allowed directory (not the directory itself)
                if filepath_resolved.startswith(allowed_dir + os.sep):
                    is_allowed = True
                    break

            if not is_allowed:
                logger.warning(
                    f"Attempted unauthorized file access: {filepath} (resolved: {filepath_resolved})"
                )
                return JSONResponse({"error": "Access denied"}, status_code=403)

            # Additional security check - ensure it's actually a file and not a directory
            if not os.path.isfile(filepath_resolved):
                return JSONResponse(
                    {"error": "File not found on server"}, status_code=404
                )

        except Exception as e:
            logger.error(f"Error validating file path: {e}")
            return JSONResponse({"error": "Invalid file path"}, status_code=400)

        if not os.path.exists(filepath):
            return JSONResponse({"error": "File not found on server"}, status_code=404)

        # Get the filename from the path
        filename = os.path.basename(filepath)

        # Return the file as a download
        return FileResponse(
            filepath, filename=filename, media_type="application/octet-stream"
        )

    except Exception as e:
        logger.error(f"Download error: {e}", exc_info=True)
        return JSONResponse(
            {"error": "An error occurred while processing your request"},
            status_code=500,
        )


async def submit_report(request: Request):
    """API endpoint to submit a report for a file"""
    # Require authentication - either session or API key
    has_session = request.session.get("user_id") is not None
    has_api_auth = getattr(request.state, "authenticated", False)

    if not has_session and not has_api_auth:
        return JSONResponse(
            {
                "success": False,
                "error": "Authentication required. Please log in or use an API key.",
            },
            status_code=401,
        )

    try:
        # Get user info
        user_id = request.session.get("user_id")
        username = request.session.get("username")

        # For API key authentication, use the authenticated user_id
        if not user_id and has_api_auth:
            user_id = request.state.user_id
            # Get username from database for API key users
            user_doc = await db.get_user_by_id(user_id)
            if user_doc:
                username = user_doc.get("username", "api_user")

        if not user_id or not username:
            return JSONResponse(
                {"success": False, "error": "User information not found"},
                status_code=401,
            )

        # Get form data
        form_data = await request.form()
        entry_id = form_data.get("entry_id", "").strip()
        entry_name = form_data.get("entry_name", "").strip()
        reason = form_data.get("reason", "").strip()

        if not entry_id or not reason:
            return JSONResponse(
                {"success": False, "error": "Missing required fields"}, status_code=400
            )

        # Verify entry exists
        entry = await db.get_entry_by_id(entry_id)
        if not entry:
            return JSONResponse(
                {"success": False, "error": "Entry not found"}, status_code=404
            )

        # Create the report | OLD NOT WORKING REPORT SYSTEM
        # report_id = await db.create_report(
        #    entry_id=entry_id,
        #    entry_name=entry_name or entry.get('name', 'Unknown'),
        #    user_id=user_id,
        #    username=username,
        #    reason=reason,
        #    description=description
        # )
        # if not report_id:
        #    return JSONResponse({
        #        "success": False,
        #        "error": "Failed to create report"
        #    }, status_code=500)

        # Always mark the entry as corrupt when any report is submitted
        await db.mark_entry_corrupt(entry_id, True)
        logger.info(f"Entry {entry_id} marked as corrupt due to report submission")

        # Log the report activity
        ip_info = get_ip_info(request)
        activity_data = {
            "event_type": "report_submitted",
            "user_id": user_id,
            "username": username,
            "details": {
                #'report_id': report_id,
                "entry_id": entry_id,
                "entry_name": entry_name or entry.get("name", "Unknown"),
                "reason": reason,
            },
            "ip_address": ip_info["ip_address"],
            "client_ip": ip_info["client_ip"],
        }
        if "forwarded_ip" in ip_info:
            activity_data["forwarded_ip"] = ip_info["forwarded_ip"]

        await db.add_activity_log(activity_data)

        logger.info(
            f"Report submitted for entry {entry_id} by user {username} from {format_ip_for_log(request)}"
        )

        return JSONResponse(
            {"success": True, "message": "Report submitted successfully"}
        )

    except Exception as e:
        logger.error(f"Report submission error: {e}", exc_info=True)
        return JSONResponse(
            {
                "success": False,
                "error": "An error occurred while submitting the report",
            },
            status_code=500,
        )


def _compute_hashes_sync(filepath: str) -> tuple:
    """Synchronous hash computation to run in a separate thread"""
    md5_hash = hashlib.md5()
    sha256_hash = hashlib.sha256()

    # Read file in chunks to handle large files
    chunk_size = 8192
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            md5_hash.update(chunk)
            sha256_hash.update(chunk)

    return md5_hash.hexdigest(), sha256_hash.hexdigest()


async def _compute_and_store_hashes(entry_id: str, filepath: str):
    """Background task to compute and store file hashes in a separate thread"""
    try:
        logger.info(f"Computing hashes for entry {entry_id}: {filepath}")

        # Mark entry as processing by setting temporary values
        await db.update_entry_hashes(entry_id, "processing", "processing")

        # Run the blocking hash computation in a separate thread
        md5_result, sha256_result = await asyncio.to_thread(
            _compute_hashes_sync, filepath
        )

        # Store hashes in database
        await db.update_entry_hashes(entry_id, md5_result, sha256_result)

        logger.info(f"Computed and stored hashes for entry {entry_id}")
    except Exception as e:
        logger.error(f"Error computing hashes in background: {e}", exc_info=True)
        # Clear processing markers on error
        try:
            await db.update_entry_hashes(entry_id, None, None)
        except Exception:
            pass


async def compute_file_hashes(request: Request):
    """API endpoint to compute MD5 and SHA256 hashes for a file entry"""
    # Require authentication - either session or API key
    has_session = request.session.get("user_id") is not None
    has_api_auth = getattr(request.state, "authenticated", False)

    if not has_session and not has_api_auth:
        return JSONResponse(
            {
                "success": False,
                "error": "Authentication required. Please log in or use an API key.",
            },
            status_code=401,
        )

    try:
        entry_id = request.path_params.get("entry_id")

        # Check for force_recheck parameter
        force_recheck = request.query_params.get("force_recheck", "").lower() == "true"

        # Get the entry from the database
        entry = await db.get_entry_by_id(entry_id)

        if not entry:
            return JSONResponse(
                {"success": False, "error": "Entry not found"}, status_code=404
            )

        # Check if hashes already exist (skip cache if force_recheck)
        if not force_recheck and entry.get("md5_hash") and entry.get("sha256_hash"):
            return JSONResponse(
                {
                    "success": True,
                    "md5": entry.get("md5_hash"),
                    "sha256": entry.get("sha256_hash"),
                    "cached": True,
                }
            )

        # Only compute hashes for filepath type entries
        if entry.get("type") != "filepath":
            return JSONResponse(
                {
                    "success": False,
                    "error": "Hash computation is only available for uploaded files",
                },
                status_code=400,
            )

        filepath = entry.get("source")

        # Validate the filepath exists and is accessible
        if not filepath or not os.path.exists(filepath) or not os.path.isfile(filepath):
            return JSONResponse(
                {"success": False, "error": "File not found on server"}, status_code=404
            )

        # Return immediately and compute hashes in the background
        background_task = BackgroundTask(_compute_and_store_hashes, entry_id, filepath)

        message = "Hash computation started in background. Results will appear automatically when ready."
        if force_recheck:
            message = "Force recheck: Bypassing cache and recomputing hashes in background. Results will appear automatically when ready."

        return JSONResponse(
            {
                "success": True,
                "processing": True,
                "force_recheck": force_recheck,
                "message": message,
            },
            background=background_task,
        )

    except Exception as e:
        logger.error(f"Hash computation error: {e}", exc_info=True)
        return JSONResponse(
            {"success": False, "error": "An error occurred while computing hashes"},
            status_code=500,
        )


async def get_entry_info(request: Request):
    """API endpoint to get entry information (for dynamic updates)"""
    # Require authentication - either session or API key
    has_session = request.session.get("user_id") is not None
    has_api_auth = getattr(request.state, "authenticated", False)

    if not has_session and not has_api_auth:
        return JSONResponse(
            {
                "success": False,
                "error": "Authentication required. Please log in or use an API key.",
            },
            status_code=401,
        )

    try:
        entry_id = request.path_params.get("entry_id")

        # Get the entry from the database
        entry = await db.get_entry_by_id(entry_id)

        if not entry:
            return JSONResponse(
                {"success": False, "error": "Entry not found"}, status_code=404
            )

        # Return entry information
        return JSONResponse(
            {
                "success": True,
                "entry": {
                    "_key": entry.get("_key"),
                    "name": entry.get("name"),
                    "file_type": entry.get("file_type"),
                    "size": entry.get("size"),
                    "created_by": entry.get("created_by"),
                    "created_at": entry.get("created_at"),
                    "file_created_at": entry.get("file_created_at"),
                    "file_modified_at": entry.get("file_modified_at"),
                    "corrupt": entry.get("corrupt", False),
                    "md5_hash": entry.get("md5_hash"),
                    "sha256_hash": entry.get("sha256_hash"),
                    "type": entry.get("type"),
                    "downloads": entry.get("downloads", 0),
                },
            }
        )

    except Exception as e:
        logger.error(f"Error fetching entry info: {e}", exc_info=True)
        return JSONResponse(
            {
                "success": False,
                "error": "An error occurred while fetching entry information",
            },
            status_code=500,
        )


async def delete_entry(request: Request):
    """API endpoint to delete an entry (moderator or admin only)

    Route: POST /api/entries/{entry_id}/delete
    """
    # Check if user is logged in and is moderator or admin
    user_id = request.session.get("user_id")
    username = request.session.get("username")
    is_mod = request.session.get("is_moderator", False)
    is_admin = request.session.get("is_admin", False)

    if not user_id or not (is_mod or is_admin):
        return JSONResponse(
            {
                "success": False,
                "error": "Unauthorized. Moderator or admin access required.",
            },
            status_code=403,
        )

    try:
        entry_id = request.path_params.get("entry_id")

        # Get the entry from the database
        entry = await db.get_entry_by_id(entry_id)

        if not entry:
            return JSONResponse(
                {"success": False, "error": "Entry not found"}, status_code=404
            )

        entry_name = entry.get("name", "Unknown")
        entry_type = entry.get("type")

        # If entry is a filepath, delete the file from disk
        if entry_type == "filepath":
            filepath = entry.get("source")
            if filepath and os.path.exists(filepath):
                try:
                    # Validate that filepath is an absolute path and exists
                    abs_filepath = os.path.abspath(filepath)

                    # Additional security: Ensure file is not a symlink to prevent directory traversal
                    if os.path.islink(abs_filepath):
                        logger.warning(f"Attempted to delete symlink: {abs_filepath}")
                        return JSONResponse(
                            {
                                "success": False,
                                "error": "Cannot delete symbolic links for security reasons",
                            },
                            status_code=400,
                        )

                    # Delete the file
                    os.remove(abs_filepath)
                    logger.info(f"Deleted file from disk: {abs_filepath}")
                except PermissionError:
                    logger.error(f"Permission denied when deleting file: {filepath}")
                    return JSONResponse(
                        {
                            "success": False,
                            "error": "Permission denied when deleting file",
                        },
                        status_code=500,
                    )
                except Exception as e:
                    logger.error(f"Error deleting file from disk: {e}")
                    return JSONResponse(
                        {"success": False, "error": "Failed to delete file from disk"},
                        status_code=500,
                    )
            elif filepath:
                logger.warning(f"File not found on disk: {filepath}")

        # Delete the entry from the database
        success = await db.delete_entry(entry_id)

        if not success:
            return JSONResponse(
                {"success": False, "error": "Failed to delete entry from database"},
                status_code=500,
            )

        # Log the action
        ip_info = get_ip_info(request)
        activity_data = {
            "event_type": "entry_deleted",
            "user_id": user_id,
            "username": username,
            "details": {
                "entry_id": entry_id,
                "entry_name": entry_name,
                "entry_type": entry_type,
            },
            "ip_address": ip_info["ip_address"],
            "client_ip": ip_info["client_ip"],
        }
        if "forwarded_ip" in ip_info:
            activity_data["forwarded_ip"] = ip_info["forwarded_ip"]

        await db.add_activity_log(activity_data)

        logger.info(
            f"{'Admin' if is_admin else 'Moderator'} {username} deleted entry {entry_id} ({entry_name}) from {format_ip_for_log(request)}"
        )

        return JSONResponse(
            {"success": True, "message": f"Entry '{entry_name}' deleted successfully"}
        )

    except Exception as e:
        logger.error(f"Error deleting entry: {e}", exc_info=True)
        return JSONResponse(
            {"success": False, "error": "An error occurred while deleting the entry"},
            status_code=500,
        )


async def get_user_stats(request: Request):
    """API endpoint to get user statistics

    Route: GET /api/user/stats
    """
    # Check if user is logged in
    user_id = request.session.get("user_id")

    if not user_id:
        return JSONResponse(
            {"success": False, "error": "Authentication required"},
            status_code=401,
        )

    try:
        # Get user statistics from database
        stats = await db.get_user_statistics(user_id)

        return JSONResponse({"success": True, "stats": stats})

    except Exception as e:
        logger.error(f"Error fetching user statistics: {e}", exc_info=True)
        return JSONResponse(
            {"success": False, "error": "Failed to fetch user statistics"},
            status_code=500,
        )


async def get_entry_comments(request: Request):
    """API endpoint to get comments for an entry

    Route: GET /api/entries/{entry_id}/comments
    """
    try:
        entry_id = request.path_params.get("entry_id")
        user_id = request.session.get("user_id")

        # Get comments for the entry with vote stats
        comments = await db.get_comments_for_entry(entry_id, user_id)

        return JSONResponse({"success": True, "comments": comments})

    except Exception as e:
        logger.error(f"Error fetching comments: {e}", exc_info=True)
        return JSONResponse(
            {"success": False, "error": "Failed to fetch comments"},
            status_code=500,
        )


async def create_entry_comment(request: Request):
    """API endpoint to create a comment on an entry

    Route: POST /api/entries/{entry_id}/comments
    """
    # Check if user is logged in
    user_id = request.session.get("user_id")
    username = request.session.get("username")

    if not user_id:
        return JSONResponse(
            {"success": False, "error": "Authentication required"},
            status_code=401,
        )

    try:
        entry_id = request.path_params.get("entry_id")

        # Get form data
        form_data = await request.form()
        text = form_data.get("text", "").strip()
        parent_comment_id = form_data.get("parent_comment_id")

        # Validate input
        if not text:
            return JSONResponse(
                {"success": False, "error": "Comment text is required"},
                status_code=400,
            )

        if len(text) > 5000:
            return JSONResponse(
                {"success": False, "error": "Comment text is too long (max 5000 characters)"},
                status_code=400,
            )

        # Verify entry exists
        entry = await db.get_entry_by_id(entry_id)
        if not entry:
            return JSONResponse(
                {"success": False, "error": "Entry not found"},
                status_code=404,
            )

        # Create comment
        comment_id = await db.create_comment(
            entry_id=entry_id,
            user_id=user_id,
            username=username,
            text=text,
            parent_comment_id=parent_comment_id if parent_comment_id else None,
        )

        if comment_id:
            return JSONResponse(
                {"success": True, "comment_id": comment_id, "message": "Comment created successfully"}
            )
        else:
            return JSONResponse(
                {"success": False, "error": "Failed to create comment"},
                status_code=500,
            )

    except Exception as e:
        logger.error(f"Error creating comment: {e}", exc_info=True)
        return JSONResponse(
            {"success": False, "error": "Failed to create comment"},
            status_code=500,
        )


async def vote_entry(request: Request):
    """API endpoint to vote (like/dislike) on an entry

    Route: POST /api/entries/{entry_id}/vote
    """
    # Check if user is logged in
    user_id = request.session.get("user_id")

    if not user_id:
        return JSONResponse(
            {"success": False, "error": "Authentication required"},
            status_code=401,
        )

    try:
        entry_id = request.path_params.get("entry_id")

        # Get form data
        form_data = await request.form()
        vote_type = form_data.get("vote_type", "").strip().lower()

        # Validate vote type
        if vote_type not in ["like", "dislike"]:
            return JSONResponse(
                {"success": False, "error": "Invalid vote type. Must be 'like' or 'dislike'"},
                status_code=400,
            )

        # Verify entry exists
        entry = await db.get_entry_by_id(entry_id)
        if not entry:
            return JSONResponse(
                {"success": False, "error": "Entry not found"},
                status_code=404,
            )

        # Add or update vote
        success = await db.add_or_update_vote(
            entry_id=entry_id,
            user_id=user_id,
            vote_type=vote_type,
        )

        if success:
            # Get updated vote stats
            vote_stats = await db.get_vote_stats_for_entry(entry_id)
            user_vote = await db.get_user_vote_for_entry(entry_id, user_id)

            return JSONResponse(
                {
                    "success": True,
                    "message": "Vote recorded successfully",
                    "vote_stats": vote_stats,
                    "user_vote": user_vote,
                }
            )
        else:
            return JSONResponse(
                {"success": False, "error": "Failed to record vote"},
                status_code=500,
            )

    except Exception as e:
        logger.error(f"Error recording vote: {e}", exc_info=True)
        return JSONResponse(
            {"success": False, "error": "Failed to record vote"},
            status_code=500,
        )


async def get_entry_vote_stats(request: Request):
    """API endpoint to get vote statistics for an entry

    Route: GET /api/entries/{entry_id}/votes
    """
    try:
        entry_id = request.path_params.get("entry_id")
        user_id = request.session.get("user_id")

        # Get vote stats
        vote_stats = await db.get_vote_stats_for_entry(entry_id)

        # Get user's vote if logged in
        user_vote = None
        if user_id:
            user_vote = await db.get_user_vote_for_entry(entry_id, user_id)

        return JSONResponse(
            {
                "success": True,
                "vote_stats": vote_stats,
                "user_vote": user_vote,
            }
        )

    except Exception as e:
        logger.error(f"Error fetching vote stats: {e}", exc_info=True)
        return JSONResponse(
            {"success": False, "error": "Failed to fetch vote stats"},
            status_code=500,
        )


async def vote_comment(request: Request):
    """API endpoint to vote (like/dislike) on a comment

    Route: POST /api/comments/{comment_id}/vote
    """
    # Check if user is logged in
    user_id = request.session.get("user_id")

    if not user_id:
        return JSONResponse(
            {"success": False, "error": "Authentication required"},
            status_code=401,
        )

    try:
        comment_id = request.path_params.get("comment_id")

        # Get form data
        form_data = await request.form()
        vote_type = form_data.get("vote_type", "").strip().lower()

        # Validate vote type
        if vote_type not in ["like", "dislike"]:
            return JSONResponse(
                {"success": False, "error": "Invalid vote type. Must be 'like' or 'dislike'"},
                status_code=400,
            )

        # Verify comment exists
        query = "FOR comment IN comments FILTER comment._key == @comment_id RETURN comment"
        cursor = await db.db.aql.execute(query, bind_vars={"comment_id": comment_id})
        comment = None
        async with cursor:
            async for c in cursor:
                comment = c
                break

        if not comment:
            return JSONResponse(
                {"success": False, "error": "Comment not found"},
                status_code=404,
            )

        # Add or update vote
        success = await db.add_or_update_comment_vote(
            comment_id=comment_id,
            user_id=user_id,
            vote_type=vote_type,
        )

        if success:
            # Get updated vote stats
            vote_stats = await db.get_comment_vote_stats(comment_id)
            user_vote = await db.get_user_vote_for_comment(comment_id, user_id)

            return JSONResponse(
                {
                    "success": True,
                    "message": "Vote recorded successfully",
                    "vote_stats": vote_stats,
                    "user_vote": user_vote,
                }
            )
        else:
            return JSONResponse(
                {"success": False, "error": "Failed to record vote"},
                status_code=500,
            )

    except Exception as e:
        logger.error(f"Error recording comment vote: {e}", exc_info=True)
        return JSONResponse(
            {"success": False, "error": "Failed to record vote"},
            status_code=500,
        )


async def get_comment_vote_stats(request: Request):
    """API endpoint to get vote statistics for a comment

    Route: GET /api/comments/{comment_id}/votes
    """
    try:
        comment_id = request.path_params.get("comment_id")
        user_id = request.session.get("user_id")

        # Get vote stats
        vote_stats = await db.get_comment_vote_stats(comment_id)

        # Get user's vote if logged in
        user_vote = None
        if user_id:
            user_vote = await db.get_user_vote_for_comment(comment_id, user_id)

        return JSONResponse(
            {
                "success": True,
                "vote_stats": vote_stats,
                "user_vote": user_vote,
            }
        )

    except Exception as e:
        logger.error(f"Error fetching comment vote stats: {e}", exc_info=True)
        return JSONResponse(
            {"success": False, "error": "Failed to fetch vote stats"},
            status_code=500,
        )


async def api_login(request: Request):
    """JSON API endpoint for login - returns or creates API key"""
    try:
        # Parse JSON body
        body = await request.json()
        username = body.get("username", "").strip()
        password = body.get("password", "")

        if not username or not password:
            return JSONResponse(
                {"success": False, "error": "Username and password are required"},
                status_code=400,
            )

        # Get user from database
        from app.models.user import User
        user_data = await db.get_user_by_username(username)
        if not user_data:
            return JSONResponse(
                {"success": False, "error": "Invalid username or password"},
                status_code=401,
            )

        # Verify password
        user = User.from_dict(user_data)
        if not User.verify_password(password, user.password_hash):
            return JSONResponse(
                {"success": False, "error": "Invalid username or password"},
                status_code=401,
            )

        # Check if user has an API key for "Send to Switch"
        from app.models.api_key import ApiKey
        user_api_keys = await db.get_user_api_keys(user._key)
        
        # Look for existing "Send to Switch" API key
        send_to_switch_key = None
        for key_data in user_api_keys:
            if key_data.get("key_name") == "Send to Switch" and key_data.get("is_active"):
                send_to_switch_key = key_data
                break

        # If no key exists, create one
        if not send_to_switch_key:
            api_key_plain = ApiKey.generate_key()
            api_key_hash = ApiKey.hash_key(api_key_plain)
            
            api_key_data = {
                "user_id": user._key,
                "key_name": "Send to Switch",
                "key_hash": api_key_hash,
                "is_active": True,
            }
            
            key_id = await db.create_api_key(api_key_data)
            
            if not key_id:
                return JSONResponse(
                    {"success": False, "error": "Failed to create API key"},
                    status_code=500,
                )

            logger.info(f"Created new 'Send to Switch' API key for user: {username}")
            return JSONResponse({
                "success": True,
                "api_key": api_key_plain,
                "message": "New API key created",
            })
        else:
            # Key exists, but we can't return it (it's hashed)
            # Return error indicating they already have a key
            return JSONResponse(
                {"success": False, "error": "API key already exists. Please use your existing key or regenerate from settings."},
                status_code=400,
            )

    except Exception as e:
        logger.error(f"API login error: {e}", exc_info=True)
        return JSONResponse(
            {"success": False, "error": "An error occurred during login"},
            status_code=500,
        )


async def send_to_switch(request: Request):
    """API endpoint to add a game to the user's send queue"""
    # Require API authentication
    if not getattr(request.state, "authenticated", False):
        return JSONResponse(
            {"error": "API authentication required"},
            status_code=401,
        )

    try:
        user_id = request.state.user_id
        body = await request.json()
        entry_id = body.get("entry_id")

        if not entry_id:
            return JSONResponse(
                {"success": False, "error": "entry_id is required"},
                status_code=400,
            )

        # Verify entry exists
        entry = await db.get_entry_by_id(entry_id)
        if not entry:
            return JSONResponse(
                {"success": False, "error": "Entry not found"},
                status_code=404,
            )

        # Add to user's send queue
        success = await db.add_to_send_queue(user_id, entry_id)
        
        if success:
            logger.info(f"Added entry {entry_id} to send queue for user {user_id}")
            return JSONResponse({
                "success": True,
                "message": "Game added to send queue",
            })
        else:
            return JSONResponse(
                {"success": False, "error": "Failed to add to queue"},
                status_code=500,
            )

    except Exception as e:
        logger.error(f"Send to switch error: {e}", exc_info=True)
        return JSONResponse(
            {"success": False, "error": "An error occurred"},
            status_code=500,
        )


async def get_send_queue(request: Request):
    """API endpoint to get pending items from user's send queue"""
    # Require API authentication
    if not getattr(request.state, "authenticated", False):
        return JSONResponse(
            {"error": "API authentication required"},
            status_code=401,
        )

    try:
        user_id = request.state.user_id
        
        # Get user's send queue
        queue_items = await db.get_send_queue(user_id)
        
        return JSONResponse({
            "success": True,
            "queue": queue_items,
        })

    except Exception as e:
        logger.error(f"Get send queue error: {e}", exc_info=True)
        return JSONResponse(
            {"success": False, "error": "An error occurred"},
            status_code=500,
        )


async def update_send_queue_item(request: Request):
    """API endpoint to update status of a send queue item"""
    # Require API authentication
    if not getattr(request.state, "authenticated", False):
        return JSONResponse(
            {"error": "API authentication required"},
            status_code=401,
        )

    try:
        user_id = request.state.user_id
        body = await request.json()
        queue_item_id = body.get("queue_item_id")
        status = body.get("status")  # 'processing', 'completed', 'failed'

        if not queue_item_id or not status:
            return JSONResponse(
                {"success": False, "error": "queue_item_id and status are required"},
                status_code=400,
            )

        if status not in ["processing", "completed", "failed"]:
            return JSONResponse(
                {"success": False, "error": "Invalid status. Must be 'processing', 'completed', or 'failed'"},
                status_code=400,
            )

        # Update queue item status
        success = await db.update_send_queue_item(user_id, queue_item_id, status)
        
        if success:
            logger.info(f"Updated queue item {queue_item_id} to status {status} for user {user_id}")
            return JSONResponse({
                "success": True,
                "message": f"Queue item updated to {status}",
            })
        else:
            return JSONResponse(
                {"success": False, "error": "Failed to update queue item"},
                status_code=500,
            )

    except Exception as e:
        logger.error(f"Update send queue item error: {e}", exc_info=True)
        return JSONResponse(
            {"success": False, "error": "An error occurred"},
            status_code=500,
        )
