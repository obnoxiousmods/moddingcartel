import logging

from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.templating import Jinja2Templates

from app.config import Config
from app.database import db
from app.models.request import Request as UserRequest
from app.models.request import RequestStatus, RequestType
from app.models.user import User
from app.utils.ip_utils import format_ip_for_log, get_ip_info

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="app/templates")


async def mod_dashboard(request: Request) -> Response:
    """Moderator control panel dashboard"""
    if not Config.is_initialized():
        return RedirectResponse(url="/admincp/init", status_code=303)

    # Check if user is logged in
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login", status_code=303)

    # Check if user is moderator or admin
    is_mod = request.session.get("is_moderator", False)
    is_admin = request.session.get("is_admin", False)

    if not (is_mod or is_admin):
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "title": "Access Denied",
                "error_message": "You do not have permission to access the moderator dashboard.",
                "app_name": Config.get("app.name", "moddingcartel"),
            },
            status_code=403,
        )

    # Get pending requests count
    pending_requests = await db.get_all_requests(status="pending")

    return templates.TemplateResponse(
        request,
        "mod/dashboard.html",
        {
            "title": "Moderator Dashboard",
            "app_name": Config.get("app.name", "moddingcartel"),
            "pending_count": len(pending_requests),
            "is_admin": is_admin,
        },
    )


async def mod_requests(request: Request) -> Response:
    """View all requests"""
    if not Config.is_initialized():
        return RedirectResponse(url="/admincp/init", status_code=303)

    # Check if user is logged in
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login", status_code=303)

    # Check if user is moderator or admin
    is_mod = request.session.get("is_moderator", False)
    is_admin = request.session.get("is_admin", False)

    if not (is_mod or is_admin):
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

    # Get requests based on filter
    if status_filter == "all":
        requests = await db.get_all_requests()
    else:
        requests = await db.get_all_requests(status=status_filter)

    return templates.TemplateResponse(
        request,
        "mod/requests.html",
        {
            "title": "Manage Requests",
            "app_name": Config.get("app.name", "moddingcartel"),
            "requests": requests,
            "status_filter": status_filter,
            "is_admin": is_admin,
        },
    )


async def mod_approve_request(request: Request) -> Response:
    """Approve a request"""
    if not Config.is_initialized():
        return JSONResponse(
            {"success": False, "error": "System not initialized"}, status_code=400
        )

    # Check if user is logged in and is moderator or admin
    user_id = request.session.get("user_id")
    username = request.session.get("username")
    is_mod = request.session.get("is_moderator", False)
    is_admin = request.session.get("is_admin", False)

    if not user_id or not (is_mod or is_admin):
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

        # Update request status
        success = await db.update_request_status(request_id, "approved", username)
        if not success:
            return JSONResponse(
                {"success": False, "error": "Failed to update request"}, status_code=500
            )

        # If request is for moderator access, grant it
        if user_request.get("request_type") == "moderator_access":
            await db.update_user_moderator_status(user_request.get("user_id"), True)
            logger.info(
                f"Granted moderator status to user {user_request.get('username')}"
            )

        return JSONResponse(
            {"success": True, "message": "Request approved successfully"}
        )

    except Exception as e:
        logger.error(f"Error approving request: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def mod_reject_request(request: Request) -> Response:
    """Reject a request"""
    if not Config.is_initialized():
        return JSONResponse(
            {"success": False, "error": "System not initialized"}, status_code=400
        )

    # Check if user is logged in and is moderator or admin
    user_id = request.session.get("user_id")
    username = request.session.get("username")
    is_mod = request.session.get("is_moderator", False)
    is_admin = request.session.get("is_admin", False)

    if not user_id or not (is_mod or is_admin):
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

        # Update request status
        success = await db.update_request_status(request_id, "rejected", username)
        if not success:
            return JSONResponse(
                {"success": False, "error": "Failed to update request"}, status_code=500
            )

        return JSONResponse(
            {"success": True, "message": "Request rejected successfully"}
        )

    except Exception as e:
        logger.error(f"Error rejecting request: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def mod_force_password_change(request: Request) -> Response:
    """Force change a user's password (moderator version)"""
    if not Config.is_initialized():
        return JSONResponse(
            {"success": False, "error": "System not initialized"}, status_code=400
        )

    # Check if user is logged in and is moderator or admin
    user_id = request.session.get("user_id")
    username = request.session.get("username")
    is_mod = request.session.get("is_moderator", False)
    is_admin = request.session.get("is_admin", False)

    if not user_id or not (is_mod or is_admin):
        return JSONResponse(
            {"success": False, "error": "Unauthorized"}, status_code=403
        )

    try:
        form_data = await request.form()
        target_user_id = form_data.get("user_id", "").strip()
        new_password = form_data.get("new_password", "").strip()

        if not target_user_id or not new_password:
            return JSONResponse(
                {"success": False, "error": "Missing required fields"}, status_code=400
            )

        # Validate password length (minimum 6 characters to match registration)
        if len(new_password) < 6:
            return JSONResponse(
                {"success": False, "error": "Password must be at least 6 characters"},
                status_code=400,
            )

        # Get target user info for logging
        target_user = await db.get_user_by_id(target_user_id)
        if not target_user:
            return JSONResponse(
                {"success": False, "error": "User not found"}, status_code=404
            )

        # Moderators cannot change admin passwords
        if not is_admin and target_user.get("is_admin", False):
            return JSONResponse(
                {"success": False, "error": "Moderators cannot change admin passwords"},
                status_code=403,
            )

        # Update the password
        new_password_hash = User.hash_password(new_password)
        success = await db.update_user_password(target_user_id, new_password_hash)

        if not success:
            return JSONResponse(
                {"success": False, "error": "Failed to update password"},
                status_code=500,
            )

        # Log the action to audit log with IP information
        target_username = target_user.get("username", "unknown")
        ip_info = get_ip_info(request)

        audit_data = {
            "action": "password_force_changed",
            "actor_id": user_id,
            "actor_username": username,
            "target_id": target_user_id,
            "target_username": target_username,
            "details": {
                "changed_by": "admin" if is_admin else "moderator",
                "reason": "Force password change from moderator panel",
            },
            "ip_address": ip_info["ip_address"],
            "client_ip": ip_info["client_ip"],
        }
        if "forwarded_ip" in ip_info:
            audit_data["forwarded_ip"] = ip_info["forwarded_ip"]

        await db.add_audit_log(audit_data)

        logger.info(
            f"{'Admin' if is_admin else 'Moderator'} {username} force-changed password for user {target_username} from {format_ip_for_log(request)}"
        )

        return JSONResponse(
            {
                "success": True,
                "message": f"Successfully changed password for user {target_username}",
            }
        )

    except Exception as e:
        logger.error(f"Error force-changing password: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def user_submit_request(request: Request) -> Response:
    """Submit a new request"""
    if not Config.is_initialized():
        return JSONResponse(
            {"success": False, "error": "System not initialized"}, status_code=400
        )

    # Check if user is logged in
    user_id = request.session.get("user_id")
    username = request.session.get("username")

    if not user_id:
        return JSONResponse(
            {"success": False, "error": "You must be logged in to submit a request"},
            status_code=403,
        )

    try:
        form_data = await request.form()
        request_type = form_data.get("request_type", "").strip()
        message = form_data.get("message", "").strip()
        game_name = (
            form_data.get("game_name", "").strip()
            if request_type == "game_request"
            else None
        )

        if not request_type or not message:
            return JSONResponse(
                {"success": False, "error": "All fields are required"}, status_code=400
            )

        # Validate request type
        valid_types = ["upload_access", "moderator_access", "game_request", "other"]
        if request_type not in valid_types:
            return JSONResponse(
                {"success": False, "error": "Invalid request type"}, status_code=400
            )

        # Validate game_name for game_request type
        if request_type == "game_request" and not game_name:
            return JSONResponse(
                {"success": False, "error": "Game name is required for game requests"},
                status_code=400,
            )

        # Create the request
        user_request = UserRequest(
            user_id=user_id,
            username=username,
            request_type=RequestType(request_type),
            message=message,
            status=RequestStatus.PENDING,
            game_name=game_name,
        )

        request_id = await db.create_request(user_request.to_dict())
        if not request_id:
            return JSONResponse(
                {"success": False, "error": "Failed to create request"}, status_code=500
            )

        logger.info(f"User {username} submitted a {request_type} request")
        return JSONResponse(
            {
                "success": True,
                "message": "Request submitted successfully. A moderator will review it soon.",
            }
        )

    except Exception as e:
        logger.error(f"Error submitting request: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def user_requests_page(request: Request) -> Response:
    """View user's own requests"""
    if not Config.is_initialized():
        return RedirectResponse(url="/admincp/init", status_code=303)

    # Check if user is logged in
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)

    # Get user's requests
    user_requests = await db.get_user_requests(user_id)

    return templates.TemplateResponse(
        request,
        "user/requests.html",
        {
            "title": "My Requests",
            "app_name": Config.get("app.name", "moddingcartel"),
            "requests": user_requests,
        },
    )


async def mod_corrupt_games(request: Request) -> Response:
    """View corrupt games that need attention"""
    if not Config.is_initialized():
        return RedirectResponse(url="/admincp/init", status_code=303)

    # Check if user is logged in
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login", status_code=303)

    # Check if user is moderator or admin
    is_mod = request.session.get("is_moderator", False)
    is_admin = request.session.get("is_admin", False)

    if not (is_mod or is_admin):
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

    # Get corrupt entries with their reports
    corrupt_entries = await db.get_corrupt_entries()

    return templates.TemplateResponse(
        request,
        "mod/corrupt_games.html",
        {
            "title": "Corrupt Games",
            "app_name": Config.get("app.name", "moddingcartel"),
            "entries": corrupt_entries,
            "is_admin": is_admin,
        },
    )


async def mod_mark_entry_valid(request: Request) -> Response:
    """Mark an entry as valid (not corrupt) after replacement"""
    if not Config.is_initialized():
        return JSONResponse(
            {"success": False, "error": "System not initialized"}, status_code=400
        )

    # Check if user is logged in and is moderator or admin
    user_id = request.session.get("user_id")
    username = request.session.get("username")
    is_mod = request.session.get("is_moderator", False)
    is_admin = request.session.get("is_admin", False)

    if not user_id or not (is_mod or is_admin):
        return JSONResponse(
            {"success": False, "error": "Unauthorized"}, status_code=403
        )

    try:
        form_data = await request.form()
        entry_id = form_data.get("entry_id", "").strip()

        if not entry_id:
            return JSONResponse(
                {"success": False, "error": "Entry ID is required"}, status_code=400
            )

        # Get the entry
        entry = await db.get_entry_by_id(entry_id)
        if not entry:
            return JSONResponse(
                {"success": False, "error": "Entry not found"}, status_code=404
            )

        # Mark entry as not corrupt
        success = await db.mark_entry_corrupt(entry_id, False)
        if not success:
            return JSONResponse(
                {"success": False, "error": "Failed to update entry"}, status_code=500
            )

        # Log the action
        ip_info = get_ip_info(request)
        activity_data = {
            "event_type": "entry_marked_valid",
            "user_id": user_id,
            "username": username,
            "details": {
                "entry_id": entry_id,
                "entry_name": entry.get("name", "Unknown"),
            },
            "ip_address": ip_info["ip_address"],
            "client_ip": ip_info["client_ip"],
        }
        if "forwarded_ip" in ip_info:
            activity_data["forwarded_ip"] = ip_info["forwarded_ip"]

        await db.add_activity_log(activity_data)

        logger.info(
            f"{'Admin' if is_admin else 'Moderator'} {username} marked entry {entry_id} as valid from {format_ip_for_log(request)}"
        )

        return JSONResponse(
            {"success": True, "message": "Entry marked as valid successfully"}
        )

    except Exception as e:
        logger.error(f"Error marking entry as valid: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def mod_clear_all_corrupt_flags(request: Request) -> Response:
    """Clear corrupt flag from all entries"""
    if not Config.is_initialized():
        return JSONResponse(
            {"success": False, "error": "System not initialized"}, status_code=400
        )

    # Check if user is logged in and is moderator or admin
    user_id = request.session.get("user_id")
    username = request.session.get("username")
    is_mod = request.session.get("is_moderator", False)
    is_admin = request.session.get("is_admin", False)

    if not user_id or not (is_mod or is_admin):
        return JSONResponse(
            {"success": False, "error": "Unauthorized"}, status_code=403
        )

    try:
        # Clear all corrupt flags
        count = await db.clear_all_corrupt_flags()

        # Log the action
        ip_info = get_ip_info(request)
        activity_data = {
            "event_type": "clear_all_corrupt_flags",
            "user_id": user_id,
            "username": username,
            "details": {"entries_cleared": count},
            "ip_address": ip_info["ip_address"],
            "client_ip": ip_info["client_ip"],
        }
        if "forwarded_ip" in ip_info:
            activity_data["forwarded_ip"] = ip_info["forwarded_ip"]

        await db.add_activity_log(activity_data)

        logger.info(
            f"{'Admin' if is_admin else 'Moderator'} {username} cleared corrupt flags from {count} entries from {format_ip_for_log(request)}"
        )

        return JSONResponse(
            {"success": True, "message": f"Cleared corrupt flag from {count} entries"}
        )

    except Exception as e:
        logger.error(f"Error clearing all corrupt flags: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)
