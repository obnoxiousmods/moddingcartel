import asyncio
import hashlib
import logging
import os
import re
import secrets
import shutil

from starlette.datastructures import UploadFile
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.templating import Jinja2Templates

from app.config import Config
from app.database import db
from app.models.entry import Entry, EntryType, FileType
from app.utils.ip_utils import format_ip_for_log, get_ip_info

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="app/templates")

# Upload configuration
UPLOAD_CHUNK_SIZE = 1024 * 1024  # 1MB chunks for streaming uploads


def _compute_sha256_sync(filepath: str) -> str:
    """Synchronous SHA256 hash computation to run in a separate thread"""
    sha256_hash = hashlib.sha256()

    # Read file in chunks to handle large files
    chunk_size = 8192
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            sha256_hash.update(chunk)

    return sha256_hash.hexdigest()


async def uploader_dashboard(request: Request) -> Response:
    """Uploader control panel dashboard"""
    if not Config.is_initialized():
        return RedirectResponse(url="/admincp/init", status_code=303)

    # Check if user is logged in
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login", status_code=303)

    # Check if user is uploader, moderator, or admin
    is_uploader = request.session.get("is_uploader", False)
    is_mod = request.session.get("is_moderator", False)
    is_admin = request.session.get("is_admin", False)

    if not (is_uploader or is_mod or is_admin):
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "title": "Access Denied",
                "error_message": "You do not have permission to access the uploader dashboard.",
                "app_name": Config.get("app.name", "moddingcartel"),
            },
            status_code=403,
        )

    # Get pending game requests count
    game_requests = await db.get_all_requests(status="pending")
    game_requests = [
        r for r in game_requests if r.get("request_type") == "game_request"
    ]

    # Get user's upload statistics
    user_id = request.session.get("user_id")
    upload_stats = await db.get_upload_statistics(user_id)

    return templates.TemplateResponse(
        request,
        "uploader/dashboard.html",
        {
            "title": "Uploader Dashboard",
            "app_name": Config.get("app.name", "moddingcartel"),
            "pending_game_requests": len(game_requests),
            "upload_stats": upload_stats,
            "is_admin": is_admin,
            "is_moderator": is_mod,
        },
    )


async def uploader_game_requests(request: Request) -> Response:
    """View game requests"""
    if not Config.is_initialized():
        return RedirectResponse(url="/admincp/init", status_code=303)

    # Check if user is logged in
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login", status_code=303)

    # Check if user is uploader, moderator, or admin
    is_uploader = request.session.get("is_uploader", False)
    is_mod = request.session.get("is_moderator", False)
    is_admin = request.session.get("is_admin", False)

    if not (is_uploader or is_mod or is_admin):
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "title": "Access Denied",
                "error_message": "You do not have permission to access this page.",
                "app_name": Config.get("app.name", "moddingcartel"),
            },
            status_code=403,
        )

    # Get filter from query params
    status_filter = request.query_params.get("status", "pending")

    # Get game requests based on filter
    if status_filter == "all":
        requests = await db.get_all_requests()
    else:
        requests = await db.get_all_requests(status=status_filter)

    # Filter only game requests
    game_requests = [r for r in requests if r.get("request_type") == "game_request"]

    return templates.TemplateResponse(
        request,
        "uploader/game_requests.html",
        {
            "title": "Game Requests",
            "app_name": Config.get("app.name", "moddingcartel"),
            "requests": game_requests,
            "status_filter": status_filter,
            "is_admin": is_admin,
            "is_moderator": is_mod,
        },
    )


async def uploader_approve_request(request: Request) -> Response:
    """Approve a game request"""
    if not Config.is_initialized():
        return JSONResponse(
            {"success": False, "error": "System not initialized"}, status_code=400
        )

    # Check if user is logged in and is uploader, moderator or admin
    user_id = request.session.get("user_id")
    username = request.session.get("username")
    is_uploader = request.session.get("is_uploader", False)
    is_mod = request.session.get("is_moderator", False)
    is_admin = request.session.get("is_admin", False)

    if not user_id or not (is_uploader or is_mod or is_admin):
        return JSONResponse(
            {"success": False, "error": "Unauthorized"}, status_code=403
        )

    try:
        form_data = await request.form()
        request_id = form_data.get("request_id", "").strip()

        if not request_id:
            return JSONResponse(
                {"success": False, "error": "Request ID is required"}, status_code=400
            )

        # Get the request
        user_request = await db.get_request_by_id(request_id)
        if not user_request:
            return JSONResponse(
                {"success": False, "error": "Request not found"}, status_code=404
            )

        # Check if it's a game request
        if user_request.get("request_type") != "game_request":
            return JSONResponse(
                {"success": False, "error": "This is not a game request"},
                status_code=400,
            )

        # Update request status
        success = await db.update_request_status(request_id, "approved", username)
        if not success:
            return JSONResponse(
                {"success": False, "error": "Failed to update request"}, status_code=500
            )

        return JSONResponse(
            {"success": True, "message": "Game request approved successfully"}
        )

    except Exception as e:
        logger.error(f"Error approving game request: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def uploader_reject_request(request: Request) -> Response:
    """Reject a game request"""
    if not Config.is_initialized():
        return JSONResponse(
            {"success": False, "error": "System not initialized"}, status_code=400
        )

    # Check if user is logged in and is uploader, moderator or admin
    user_id = request.session.get("user_id")
    username = request.session.get("username")
    is_uploader = request.session.get("is_uploader", False)
    is_mod = request.session.get("is_moderator", False)
    is_admin = request.session.get("is_admin", False)

    if not user_id or not (is_uploader or is_mod or is_admin):
        return JSONResponse(
            {"success": False, "error": "Unauthorized"}, status_code=403
        )

    try:
        form_data = await request.form()
        request_id = form_data.get("request_id", "").strip()

        if not request_id:
            return JSONResponse(
                {"success": False, "error": "Request ID is required"}, status_code=400
            )

        # Get the request
        user_request = await db.get_request_by_id(request_id)
        if not user_request:
            return JSONResponse(
                {"success": False, "error": "Request not found"}, status_code=404
            )

        # Check if it's a game request
        if user_request.get("request_type") != "game_request":
            return JSONResponse(
                {"success": False, "error": "This is not a game request"},
                status_code=400,
            )

        # Update request status
        success = await db.update_request_status(request_id, "rejected", username)
        if not success:
            return JSONResponse(
                {"success": False, "error": "Failed to update request"}, status_code=500
            )

        return JSONResponse(
            {"success": True, "message": "Game request rejected successfully"}
        )

    except Exception as e:
        logger.error(f"Error rejecting game request: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def uploader_upload_page(request: Request) -> Response:
    """Upload game page"""
    if not Config.is_initialized():
        return RedirectResponse(url="/admincp/init", status_code=303)

    # Check if user is logged in
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login", status_code=303)

    # Check if user is uploader, moderator, or admin
    is_uploader = request.session.get("is_uploader", False)
    is_mod = request.session.get("is_moderator", False)
    is_admin = request.session.get("is_admin", False)

    if not (is_uploader or is_mod or is_admin):
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "title": "Access Denied",
                "error_message": "You do not have permission to upload games.",
                "app_name": Config.get("app.name", "moddingcartel"),
            },
            status_code=403,
        )

    return templates.TemplateResponse(
        request,
        "uploader/upload.html",
        {
            "title": "Upload Game",
            "app_name": Config.get("app.name", "moddingcartel"),
            "is_admin": is_admin,
            "is_moderator": is_mod,
            "upload_endpoint": Config.UPLOAD_ENDPOINT(),
        },
    )


async def uploader_upload_submit(request: Request) -> Response:
    """Handle game upload submission"""
    if not Config.is_initialized():
        return JSONResponse(
            {"success": False, "error": "System not initialized"}, status_code=400
        )

    # Check if user is logged in and is uploader, moderator or admin
    user_id = request.session.get("user_id")
    username = request.session.get("username")
    is_uploader = request.session.get("is_uploader", False)
    is_mod = request.session.get("is_moderator", False)
    is_admin = request.session.get("is_admin", False)

    if not user_id or not (is_uploader or is_mod or is_admin):
        return JSONResponse(
            {"success": False, "error": "Unauthorized"}, status_code=403
        )

    try:
        form_data = await request.form()

        # Get form fields
        entry_type = form_data.get("type", "").strip()
        directory_id = form_data.get("directory_id", "").strip()

        # Validate required fields
        if not entry_type or entry_type != "filepath":
            return JSONResponse(
                {"success": False, "error": "Only file upload is supported"},
                status_code=400,
            )

        # File upload
        file = form_data.get("file")
        if not file or not isinstance(file, UploadFile):
            return JSONResponse(
                {"success": False, "error": "File is required"}, status_code=400
            )

        # Get filename and sanitize it
        filename = file.filename
        if not filename:
            return JSONResponse(
                {"success": False, "error": "Invalid filename"}, status_code=400
            )

        # Sanitize filename to prevent path traversal
        # Get extension first
        name_part, ext_part = os.path.splitext(filename)
        if not ext_part:
            return JSONResponse(
                {"success": False, "error": "File must have an extension"},
                status_code=400,
            )

        # Validate file extension using splitext (secure method)
        file_ext = ext_part.lower().lstrip(".")
        if file_ext not in ["nsp", "nsz", "xci"]:
            return JSONResponse(
                {
                    "success": False,
                    "error": "Invalid file type. Supported: NSP, NSZ, XCI",
                },
                status_code=400,
            )

        file_type = file_ext

        # Sanitize the base filename - remove path separators and dangerous chars
        safe_basename = re.sub(r'[/\\:\*\?"<>|]', "", name_part)
        safe_basename = safe_basename.strip(
            ". "
        )  # Remove leading/trailing dots and spaces

        if not safe_basename or len(safe_basename) > 200:
            # If filename is invalid or too long, generate a random one
            safe_basename = f"upload_{secrets.token_hex(8)}"

        # Reconstruct safe filename
        safe_filename = f"{safe_basename}.{file_ext}"
        name = safe_basename  # Use sanitized name for entry

        # Determine upload directory
        if directory_id:
            # Get the selected directory from database
            directory = await db.get_directory_by_id(directory_id)
            if not directory:
                return JSONResponse(
                    {"success": False, "error": "Selected directory not found"},
                    status_code=400,
                )

            upload_dir = directory.get("path")
            if not upload_dir or not os.path.exists(upload_dir):
                return JSONResponse(
                    {"success": False, "error": "Selected directory does not exist"},
                    status_code=400,
                )
        else:
            # Use default upload directory
            upload_dir = Config.get("upload.directory", "/app/uploads")

        os.makedirs(upload_dir, exist_ok=True)

        # Construct file path safely
        file_path = os.path.join(upload_dir, safe_filename)

        # Verify the final path is actually within the upload directory (prevent traversal)
        file_path_resolved = os.path.abspath(file_path)
        upload_dir_resolved = os.path.abspath(upload_dir)

        # Ensure file is within directory (not equal to directory or outside it)
        if not file_path_resolved.startswith(upload_dir_resolved + os.sep):
            logger.error(
                f"Path traversal attempt detected: {filename} -> {file_path_resolved}"
            )
            return JSONResponse(
                {"success": False, "error": "Invalid file path"}, status_code=400
            )

        # Check if file already exists and make unique if needed
        counter = 1
        while os.path.exists(file_path):
            file_path = os.path.join(
                upload_dir, f"{safe_basename}_{counter}.{file_ext}"
            )
            # Re-validate the new path
            file_path_resolved = os.path.abspath(file_path)
            if not file_path_resolved.startswith(upload_dir_resolved + os.sep):
                logger.error(f"Path traversal in unique filename: {file_path_resolved}")
                return JSONResponse(
                    {"success": False, "error": "Invalid file path"}, status_code=400
                )
            counter += 1

        # Stream file in chunks to avoid reading entire file into memory
        # This prevents "Read-only file system" errors with large files
        size = 0

        with open(file_path, "wb") as f:
            while True:
                chunk = await file.read(UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                f.write(chunk)
                size += len(chunk)

        source = file_path
        logger.info(f"File saved to {file_path}, size: {size} bytes")

        # Check for duplicate filename in database
        duplicate_by_name = await db.db.aql.execute(
            """
            FOR doc IN entries
            FILTER doc.name == @name
            LIMIT 1
            RETURN doc
        """,
            bind_vars={"name": name},
        )

        has_duplicate_name = False
        async with duplicate_by_name:
            async for _ in duplicate_by_name:
                has_duplicate_name = True
                break

        if has_duplicate_name:
            # Delete the uploaded file
            try:
                os.remove(file_path)
            except OSError:
                pass
            return JSONResponse(
                {
                    "success": False,
                    "error": f"A file with the name '{name}' already exists in the database",
                },
                status_code=400,
            )

        # Compute SHA256 hash of uploaded file (but don't check for duplicates)
        logger.info(f"Computing SHA256 hash for {safe_filename}...")
        sha256_hash = await asyncio.to_thread(_compute_sha256_sync, file_path)
        logger.info(f"SHA256 computed: {sha256_hash}")

        # Create entry with directory metadata
        entry_metadata = {}
        if directory_id:
            entry_metadata["directory_id"] = directory_id

        entry = Entry(
            name=name,
            source=source,
            type=EntryType(entry_type),
            file_type=FileType(file_type),
            size=size,
            created_by=username,
            metadata=entry_metadata,
        )

        # Add to database
        entry_id = await db.add_entry(entry.to_dict())
        if not entry_id:
            # Delete the uploaded file if database entry creation failed
            try:
                os.remove(file_path)
            except OSError:
                pass
            return JSONResponse(
                {"success": False, "error": "Failed to create entry"}, status_code=500
            )

        # Store the SHA256 hash in the database
        await db.update_entry_hashes(entry_id, None, sha256_hash)

        # Record upload statistics
        await db.record_upload(user_id, username, entry_id, size)

        # Log activity with IP information
        ip_info = get_ip_info(request)
        activity_data = {
            "event_type": "upload",
            "user_id": user_id,
            "username": username,
            "entry_id": entry_id,
            "entry_name": name,
            "size_bytes": size,
            "ip_address": ip_info["ip_address"],
            "client_ip": ip_info["client_ip"],
        }
        if "forwarded_ip" in ip_info:
            activity_data["forwarded_ip"] = ip_info["forwarded_ip"]

        await db.add_activity_log(activity_data)

        logger.info(
            f"User {username} uploaded game '{name}' ({size} bytes) from {format_ip_for_log(request)}"
        )
        return JSONResponse(
            {
                "success": True,
                "message": f"Game '{name}' uploaded successfully!",
                "entry_id": entry_id,
            }
        )

    except Exception as e:
        logger.error(f"Error uploading game: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def uploader_get_directories(request: Request) -> Response:
    """Get available directories with storage information"""
    if not Config.is_initialized():
        return JSONResponse(
            {"success": False, "error": "System not initialized"}, status_code=400
        )

    # Check if user is logged in and is uploader, moderator or admin
    user_id = request.session.get("user_id")
    is_uploader = request.session.get("is_uploader", False)
    is_mod = request.session.get("is_moderator", False)
    is_admin = request.session.get("is_admin", False)

    if not user_id or not (is_uploader or is_mod or is_admin):
        return JSONResponse(
            {"success": False, "error": "Unauthorized"}, status_code=403
        )

    try:
        # Get directories with storage info
        directories = await db.get_directories_with_storage_info()

        # Also include the default upload directory with storage info
        upload_dir = Config.get("upload.directory", "/app/uploads")
        default_dir_info = None
        
        try:
            if os.path.exists(upload_dir):
                usage = shutil.disk_usage(upload_dir)
                bytes_per_gb = 1024 ** 3
                default_dir_info = {
                    "path": upload_dir,
                    "total_gb": round(usage.total / bytes_per_gb, 2),
                    "used_gb": round(usage.used / bytes_per_gb, 2),
                    "free_gb": round(usage.free / bytes_per_gb, 2),
                }
        except Exception as e:
            logger.warning(f"Could not get storage info for default directory {upload_dir}: {e}")

        return JSONResponse(
            {
                "success": True,
                "directories": directories,
                "default_upload_dir": upload_dir,
                "default_dir_info": default_dir_info,
            }
        )

    except Exception as e:
        logger.error(f"Error fetching directories: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)
