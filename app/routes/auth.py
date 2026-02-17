import logging

from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.templating import Jinja2Templates

from app.config import Config
from app.database import db
from app.models.user import User
from app.utils.ip_utils import format_ip_for_log, get_ip_info
from app.utils.validation import validate_password, validate_username

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="app/templates")


async def login_page(request: Request) -> Response:
    """Show login form"""
    # If already logged in, redirect to homepage
    if request.session.get("user_id"):
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {
            "title": "Login",
            "app_name": Config.get("app.name", "moddingcartel"),
        },
    )


async def login_submit(request: Request) -> Response:
    """Handle login form submission"""
    try:
        form_data = await request.form()
        username = form_data.get("username", "").strip()
        password = form_data.get("password", "")
        totp_code = form_data.get("totp_code", "").strip()

        if not username or not password:
            return JSONResponse(
                {"success": False, "error": "Username and password are required"},
                status_code=400,
            )

        # Get user from database
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

        # Check if TOTP is enabled for this user
        if user.totp_enabled and user.totp_secret:
            if not totp_code:
                # Password is correct but TOTP is required
                return JSONResponse(
                    {
                        "success": False,
                        "requires_totp": True,
                        "message": "Two-factor authentication code required",
                    }
                )

            # Verify TOTP code
            import pyotp

            totp = pyotp.TOTP(user.totp_secret)
            if not totp.verify(totp_code, valid_window=1):
                return JSONResponse(
                    {
                        "success": False,
                        "error": "Invalid two-factor authentication code",
                    },
                    status_code=401,
                )

        # If password is verified and needs rehashing, upgrade it to Argon2
        if User.needs_rehash(user.password_hash):
            new_hash = User.hash_password(password)
            await db.update_user_password(user._key, new_hash)
            logger.info(f"Upgraded password hash for user: {username}")

        # Set session
        request.session["user_id"] = user._key
        request.session["username"] = user.username
        request.session["is_admin"] = user.is_admin
        request.session["is_moderator"] = user.is_moderator
        request.session["is_uploader"] = user.is_uploader

        # Log the login activity with IP information
        ip_info = get_ip_info(request)
        activity_data = {
            "event_type": "login",
            "user_id": user._key,
            "username": user.username,
            "details": {"success": True, "totp_used": user.totp_enabled},
            "ip_address": ip_info["ip_address"],
            "client_ip": ip_info["client_ip"],
        }
        if "forwarded_ip" in ip_info:
            activity_data["forwarded_ip"] = ip_info["forwarded_ip"]

        await db.add_activity_log(activity_data)

        logger.info(f"User logged in: {username} from {format_ip_for_log(request)}")
        return JSONResponse({"success": True, "redirect": "/"})

    except Exception as e:
        logger.error(f"Login error: {e}")
        return JSONResponse(
            {"success": False, "error": "An error occurred during login"},
            status_code=500,
        )


async def register_page(request: Request) -> Response:
    """Show registration form"""
    # If already logged in, redirect to homepage
    if request.session.get("user_id"):
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse(
        request,
        "auth/register.html",
        {
            "title": "Register",
            "app_name": Config.get("app.name", "moddingcartel"),
        },
    )


async def register_submit(request: Request) -> Response:
    """Handle registration form submission"""
    try:
        form_data = await request.form()
        username = form_data.get("username", "").strip()
        password = form_data.get("password", "")
        confirm_password = form_data.get("confirm_password", "")

        # Validate input
        if not username or not password or not confirm_password:
            return JSONResponse(
                {"success": False, "error": "All fields are required"}, status_code=400
            )

        # Validate username format
        is_valid, error_msg = validate_username(username)
        if not is_valid:
            return JSONResponse({"success": False, "error": error_msg}, status_code=400)

        # Validate password format
        is_valid, error_msg = validate_password(password)
        if not is_valid:
            return JSONResponse({"success": False, "error": error_msg}, status_code=400)

        if password != confirm_password:
            return JSONResponse(
                {"success": False, "error": "Passwords do not match"}, status_code=400
            )

        # Check if username already exists
        if await db.user_exists(username):
            return JSONResponse(
                {"success": False, "error": "Username already exists"}, status_code=400
            )

        # Create user
        user = User(
            username=username,
            password_hash=User.hash_password(password),
            is_admin=False,
        )
        user_id = await db.create_user(user.to_dict())

        if not user_id:
            return JSONResponse(
                {"success": False, "error": "Failed to create user"}, status_code=500
            )

        # Auto-login after registration
        request.session["user_id"] = user_id
        request.session["username"] = username
        request.session["is_admin"] = False
        request.session["is_moderator"] = False
        request.session["is_uploader"] = False

        # Log the registration activity with IP information
        ip_info = get_ip_info(request)
        activity_data = {
            "event_type": "registration",
            "user_id": user_id,
            "username": username,
            "details": {"success": True},
            "ip_address": ip_info["ip_address"],
            "client_ip": ip_info["client_ip"],
        }
        if "forwarded_ip" in ip_info:
            activity_data["forwarded_ip"] = ip_info["forwarded_ip"]

        await db.add_activity_log(activity_data)

        logger.info(
            f"New user registered: {username} from {format_ip_for_log(request)}"
        )
        return JSONResponse({"success": True, "redirect": "/"})

    except Exception as e:
        logger.error(f"Registration error: {e}")
        return JSONResponse(
            {"success": False, "error": "An error occurred during registration"},
            status_code=500,
        )


async def logout(request: Request) -> Response:
    """Handle logout"""
    username = request.session.get("username", "Unknown")
    request.session.clear()
    logger.info(f"User logged out: {username}")
    return RedirectResponse(url="/login", status_code=303)
