import logging

from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.templating import Jinja2Templates

from app.config import Config
from app.database import db
from app.models.user import User
from app.utils.ip_utils import format_ip_for_log, get_ip_info

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="app/templates")


async def settings_page(request: Request) -> Response:
    """Show user settings page"""
    # Check if user is logged in
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login", status_code=303)

    # Get user statistics
    user_id = request.session.get("user_id")
    user_stats = await db.get_user_statistics(user_id)

    return templates.TemplateResponse(
        request,
        "settings/settings.html",
        {
            "title": "Settings",
            "app_name": Config.get("app.name", "moddingcartel"),
            "user_stats": user_stats,
        },
    )


async def change_password(request: Request) -> Response:
    """Handle password change"""
    # Check if user is logged in
    if not request.session.get("user_id"):
        return JSONResponse(
            {"success": False, "error": "Not authenticated"}, status_code=401
        )

    try:
        form_data = await request.form()
        current_password = form_data.get("current_password", "")
        new_password = form_data.get("new_password", "")
        confirm_password = form_data.get("confirm_password", "")

        # Validate input
        if not current_password or not new_password or not confirm_password:
            return JSONResponse(
                {"success": False, "error": "All fields are required"}, status_code=400
            )

        if len(new_password) < 6:
            return JSONResponse(
                {
                    "success": False,
                    "error": "New password must be at least 6 characters",
                },
                status_code=400,
            )

        if new_password != confirm_password:
            return JSONResponse(
                {"success": False, "error": "New passwords do not match"},
                status_code=400,
            )

        # Get user from database
        user_id = request.session.get("user_id")
        user_data = await db.get_user_by_id(user_id)

        if not user_data:
            return JSONResponse(
                {"success": False, "error": "User not found"}, status_code=404
            )

        # Verify current password
        user = User.from_dict(user_data)
        if not User.verify_password(current_password, user.password_hash):
            return JSONResponse(
                {"success": False, "error": "Current password is incorrect"},
                status_code=401,
            )

        # Update password
        new_password_hash = User.hash_password(new_password)
        success = await db.update_user_password(user_id, new_password_hash)

        if not success:
            return JSONResponse(
                {"success": False, "error": "Failed to update password"},
                status_code=500,
            )

        # Log the password change to audit log with IP information
        username = request.session.get("username", user.username)
        ip_info = get_ip_info(request)

        audit_data = {
            "action": "password_changed",
            "actor_id": user_id,
            "actor_username": username,
            "target_id": user_id,
            "target_username": username,
            "details": {"changed_by": "self", "reason": "User changed own password"},
            "ip_address": ip_info["ip_address"],
            "client_ip": ip_info["client_ip"],
        }
        if "forwarded_ip" in ip_info:
            audit_data["forwarded_ip"] = ip_info["forwarded_ip"]

        await db.add_audit_log(audit_data)

        logger.info(
            f"Password changed for user: {user.username} from {format_ip_for_log(request)}"
        )
        return JSONResponse(
            {"success": True, "message": "Password changed successfully"}
        )

    except Exception as e:
        logger.error(f"Password change error: {e}")
        return JSONResponse(
            {"success": False, "error": "An error occurred while changing password"},
            status_code=500,
        )


async def download_history_page(request: Request) -> Response:
    """Show user's download history"""
    # Check if user is logged in
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login", status_code=303)

    try:
        user_id = request.session.get("user_id")
        history = await db.get_user_download_history(user_id)

        return templates.TemplateResponse(
            request,
            "settings/download_history.html",
            {
                "title": "Download History",
                "app_name": Config.get("app.name", "moddingcartel"),
                "history": history,
            },
        )
    except Exception as e:
        logger.error(f"Error loading download history: {e}")
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "title": "Error",
                "app_name": Config.get("app.name", "moddingcartel"),
                "error": "Failed to load download history",
            },
            status_code=500,
        )


async def totp_setup_page(request: Request) -> Response:
    """Show TOTP setup page"""
    # Check if user is logged in
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login", status_code=303)

    try:
        user_id = request.session.get("user_id")
        user_data = await db.get_user_by_id(user_id)

        if not user_data:
            return RedirectResponse(url="/login", status_code=303)

        user = User.from_dict(user_data)

        return templates.TemplateResponse(
            request,
            "settings/totp_setup.html",
            {
                "title": "Two-Factor Authentication",
                "app_name": Config.get("app.name", "moddingcartel"),
                "totp_enabled": user.totp_enabled,
            },
        )
    except Exception as e:
        logger.error(f"Error loading TOTP setup page: {e}")
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "title": "Error",
                "app_name": Config.get("app.name", "moddingcartel"),
                "error": "Failed to load TOTP setup page",
            },
            status_code=500,
        )


async def totp_enable(request: Request) -> Response:
    """Generate TOTP secret and enable 2FA"""
    # Check if user is logged in
    if not request.session.get("user_id"):
        return JSONResponse(
            {"success": False, "error": "Not authenticated"}, status_code=401
        )

    try:
        import base64
        import io

        import pyotp
        import qrcode

        user_id = request.session.get("user_id")
        user_data = await db.get_user_by_id(user_id)

        if not user_data:
            return JSONResponse(
                {"success": False, "error": "User not found"}, status_code=404
            )

        user = User.from_dict(user_data)

        # Generate new TOTP secret
        secret = pyotp.random_base32()

        # Generate provisioning URI for QR code
        app_name = Config.get("app.name", "moddingcartel")
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=user.username, issuer_name=app_name
        )

        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        # Convert QR code to base64 for embedding in HTML
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()

        # Store the secret temporarily (will be confirmed on verification)
        # Update user with TOTP secret but don't enable it yet
        await db.update_user_totp(user_id, secret, False)

        return JSONResponse(
            {
                "success": True,
                "secret": secret,
                "qr_code": f"data:image/png;base64,{qr_code_base64}",
                "provisioning_uri": provisioning_uri,
            }
        )

    except Exception as e:
        logger.error(f"TOTP enable error: {e}")
        return JSONResponse(
            {"success": False, "error": "An error occurred while setting up 2FA"},
            status_code=500,
        )


async def totp_verify_and_enable(request: Request) -> Response:
    """Verify TOTP code and enable 2FA"""
    # Check if user is logged in
    if not request.session.get("user_id"):
        return JSONResponse(
            {"success": False, "error": "Not authenticated"}, status_code=401
        )

    try:
        import pyotp

        form_data = await request.form()
        totp_code = form_data.get("totp_code", "").strip()

        if not totp_code:
            return JSONResponse(
                {"success": False, "error": "TOTP code is required"}, status_code=400
            )

        user_id = request.session.get("user_id")
        user_data = await db.get_user_by_id(user_id)

        if not user_data:
            return JSONResponse(
                {"success": False, "error": "User not found"}, status_code=404
            )

        user = User.from_dict(user_data)

        if not user.totp_secret:
            return JSONResponse(
                {"success": False, "error": "TOTP not initialized"}, status_code=400
            )

        # Verify the TOTP code
        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(totp_code, valid_window=1):
            return JSONResponse(
                {"success": False, "error": "Invalid TOTP code"}, status_code=401
            )

        # Enable TOTP for the user
        await db.update_user_totp(user_id, user.totp_secret, True)

        # Log the TOTP enablement with IP information
        username = request.session.get("username", user.username)
        ip_info = get_ip_info(request)

        audit_data = {
            "action": "totp_enabled",
            "actor_id": user_id,
            "actor_username": username,
            "target_id": user_id,
            "target_username": username,
            "details": {"message": "Two-factor authentication enabled"},
            "ip_address": ip_info["ip_address"],
            "client_ip": ip_info["client_ip"],
        }
        if "forwarded_ip" in ip_info:
            audit_data["forwarded_ip"] = ip_info["forwarded_ip"]

        await db.add_audit_log(audit_data)

        logger.info(
            f"TOTP enabled for user: {user.username} from {format_ip_for_log(request)}"
        )
        return JSONResponse(
            {
                "success": True,
                "message": "Two-factor authentication enabled successfully",
            }
        )

    except Exception as e:
        logger.error(f"TOTP verification error: {e}")
        return JSONResponse(
            {"success": False, "error": "An error occurred while verifying 2FA"},
            status_code=500,
        )


async def totp_disable(request: Request) -> Response:
    """Disable TOTP/2FA"""
    # Check if user is logged in
    if not request.session.get("user_id"):
        return JSONResponse(
            {"success": False, "error": "Not authenticated"}, status_code=401
        )

    try:
        import pyotp

        form_data = await request.form()
        password = form_data.get("password", "")
        totp_code = form_data.get("totp_code", "").strip()

        if not password or not totp_code:
            return JSONResponse(
                {"success": False, "error": "Password and TOTP code are required"},
                status_code=400,
            )

        user_id = request.session.get("user_id")
        user_data = await db.get_user_by_id(user_id)

        if not user_data:
            return JSONResponse(
                {"success": False, "error": "User not found"}, status_code=404
            )

        user = User.from_dict(user_data)

        # Verify password
        if not User.verify_password(password, user.password_hash):
            return JSONResponse(
                {"success": False, "error": "Incorrect password"}, status_code=401
            )

        # Verify TOTP code
        if user.totp_enabled and user.totp_secret:
            totp = pyotp.TOTP(user.totp_secret)
            if not totp.verify(totp_code, valid_window=1):
                return JSONResponse(
                    {"success": False, "error": "Invalid TOTP code"}, status_code=401
                )

        # Disable TOTP
        await db.update_user_totp(user_id, None, False)

        # Log the TOTP disablement with IP information
        username = request.session.get("username", user.username)
        ip_info = get_ip_info(request)

        audit_data = {
            "action": "totp_disabled",
            "actor_id": user_id,
            "actor_username": username,
            "target_id": user_id,
            "target_username": username,
            "details": {"message": "Two-factor authentication disabled"},
            "ip_address": ip_info["ip_address"],
            "client_ip": ip_info["client_ip"],
        }
        if "forwarded_ip" in ip_info:
            audit_data["forwarded_ip"] = ip_info["forwarded_ip"]

        await db.add_audit_log(audit_data)

        logger.info(
            f"TOTP disabled for user: {user.username} from {format_ip_for_log(request)}"
        )
        return JSONResponse(
            {
                "success": True,
                "message": "Two-factor authentication disabled successfully",
            }
        )

    except Exception as e:
        logger.error(f"TOTP disable error: {e}")
        return JSONResponse(
            {"success": False, "error": "An error occurred while disabling 2FA"},
            status_code=500,
        )
