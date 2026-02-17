import logging
import os
import shutil
from datetime import datetime, timedelta, timezone

from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.templating import Jinja2Templates

from app.config import Config
from app.database import db
from app.models.entry import FileType
from app.models.user import User
from app.utils.ip_utils import format_ip_for_log, get_ip_info

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="app/templates")

# Sample game data to populate during initialization
SAMPLE_GAMES = [
    {
        "name": "Super Mario Odyssey",
        "source": "/games/super_mario_odyssey.nsp",
        "type": "filepath",
        "file_type": "nsp",
        "size": 5606900000,
        "created_by": "admin",
        "metadata": {
            "description": "A 3D platform game where Mario explores various kingdoms",
            "version": "1.3.0",
            "publisher": "Nintendo",
            "release_date": "2017-10-27",
        },
    },
    {
        "name": "The Legend of Zelda: Breath of the Wild",
        "source": "https://example.com/zelda_botw.nsz",
        "type": "url",
        "file_type": "nsz",
        "size": 13400000000,
        "created_by": "admin",
        "metadata": {
            "description": "Open-world action-adventure game",
            "version": "1.6.0",
            "publisher": "Nintendo",
            "release_date": "2017-03-03",
        },
    },
    {
        "name": "Mario Kart 8 Deluxe",
        "source": "/games/mario_kart_8_deluxe.nsp",
        "type": "filepath",
        "file_type": "nsp",
        "size": 6900000000,
        "created_by": "admin",
        "metadata": {
            "description": "Racing game featuring Nintendo characters",
            "version": "2.3.0",
            "publisher": "Nintendo",
            "release_date": "2017-04-28",
        },
    },
    {
        "name": "Animal Crossing: New Horizons",
        "source": "/games/animal_crossing_new_horizons.xci",
        "type": "filepath",
        "file_type": "xci",
        "size": 7100000000,
        "created_by": "admin",
        "metadata": {
            "description": "Life simulation game set on a deserted island",
            "version": "2.0.6",
            "publisher": "Nintendo",
            "release_date": "2020-03-20",
        },
    },
    {
        "name": "Splatoon 3",
        "source": "https://example.com/splatoon_3.nsz",
        "type": "url",
        "file_type": "nsz",
        "size": 6200000000,
        "created_by": "admin",
        "metadata": {
            "description": "Third-person shooter game with ink-based gameplay",
            "version": "4.1.0",
            "publisher": "Nintendo",
            "release_date": "2022-09-09",
        },
    },
    {
        "name": "Pokemon Scarlet",
        "source": "/games/pokemon_scarlet.nsp",
        "type": "filepath",
        "file_type": "nsp",
        "size": 7500000000,
        "created_by": "admin",
        "metadata": {
            "description": "Open-world Pokemon adventure game",
            "version": "3.0.1",
            "publisher": "The Pokemon Company",
            "release_date": "2022-11-18",
        },
    },
    {
        "name": "Metroid Dread",
        "source": "/games/metroid_dread.nsp",
        "type": "filepath",
        "file_type": "nsp",
        "size": 4100000000,
        "created_by": "admin",
        "metadata": {
            "description": "Action-adventure side-scrolling game",
            "version": "1.0.4",
            "publisher": "Nintendo",
            "release_date": "2021-10-08",
        },
    },
    {
        "name": "Kirby and the Forgotten Land",
        "source": "https://example.com/kirby_forgotten_land.nsz",
        "type": "url",
        "file_type": "nsz",
        "size": 5900000000,
        "created_by": "admin",
        "metadata": {
            "description": "3D platform adventure starring Kirby",
            "version": "1.1.0",
            "publisher": "Nintendo",
            "release_date": "2022-03-25",
        },
    },
    {
        "name": "Xenoblade Chronicles 3",
        "source": "/games/xenoblade_chronicles_3.xci",
        "type": "filepath",
        "file_type": "xci",
        "size": 15600000000,
        "created_by": "admin",
        "metadata": {
            "description": "Action role-playing game",
            "version": "2.2.0",
            "publisher": "Nintendo",
            "release_date": "2022-07-29",
        },
    },
    {
        "name": "Fire Emblem Engage",
        "source": "/games/fire_emblem_engage.nsp",
        "type": "filepath",
        "file_type": "nsp",
        "size": 11300000000,
        "created_by": "admin",
        "metadata": {
            "description": "Tactical role-playing game",
            "version": "2.0.0",
            "publisher": "Nintendo",
            "release_date": "2023-01-20",
        },
    },
]


async def admin_init_page(request: Request) -> Response:
    """Show initialization form"""
    # If already initialized, redirect to admin dashboard
    if Config.is_initialized():
        return RedirectResponse(url="/admincp", status_code=303)

    return templates.TemplateResponse(
        request, "admin/init.html", {"title": "Initialize System"}
    )


async def admin_init_submit(request: Request) -> Response:
    """Handle initialization form submission"""
    # If already initialized, return error
    if Config.is_initialized():
        return JSONResponse(
            {"success": False, "error": "System already initialized"}, status_code=400
        )

    try:
        # Parse form data
        form_data = await request.form()
        validated_data = {}

        # Validate required fields
        required_fields = [
            "website_name",
            "admin_username",
            "admin_password",
            "db_host",
            "db_port",
            "db_username",
            "db_password",
            "db_name",
        ]
        for field in required_fields:
            if not form_data.get(field):
                return JSONResponse(
                    {"success": False, "error": f"Missing required field: {field}"},
                    status_code=400,
                )
            validated_data[field] = form_data.get(field)

        # Validate port number
        try:
            validated_data["db_port"] = int(validated_data["db_port"])
            if not (0 < validated_data["db_port"] < 65536):
                raise ValueError
        except ValueError:
            return JSONResponse(
                {"success": False, "error": "Invalid port number"}, status_code=400
            )

        # Initialize configuration
        Config.initialize(
            {
                "website_name": validated_data["website_name"],
                "db_host": validated_data["db_host"],
                "db_port": validated_data["db_port"],
                "db_username": validated_data["db_username"],
                "db_password": validated_data["db_password"],
                "db_name": validated_data["db_name"],
            }
        )

        # Connect to database and create dummy entries
        try:
            await db.connect()

            # Create admin user
            admin_user = User(
                username=validated_data["admin_username"],
                password_hash=User.hash_password(validated_data["admin_password"]),
                is_admin=True,
            )
            await db.create_user(admin_user.to_dict())
            logger.info(f"Created admin user: {validated_data['admin_username']}")

            # Add sample games
            base_time = datetime.now(timezone.utc)
            for i, game in enumerate(SAMPLE_GAMES):
                game["created_at"] = (base_time - timedelta(hours=i * 2)).isoformat()
                await db.add_entry(game)

            logger.info(f"Created {len(SAMPLE_GAMES)} sample entries")

        except Exception as e:
            logger.error(f"Database initialization error: {e}")
            # Rollback config
            Config.set("initialized", False)
            Config.save()
            return JSONResponse(
                {"success": False, "error": f"Database error: {str(e)}"},
                status_code=500,
            )

        return JSONResponse({"success": True, "redirect": "/"})

    except Exception as e:
        logger.error(f"Initialization error: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def admin_dashboard(request: Request) -> Response:
    """Admin control panel dashboard"""
    if not Config.is_initialized():
        return RedirectResponse(url="/admincp/init", status_code=303)

    # Check if user is logged in and is admin
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login", status_code=303)

    if not request.session.get("is_admin"):
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "title": "Access Denied",
                "error_message": "You do not have permission to access the admin dashboard.",
                "app_name": Config.get("app.name", "moddingcartel"),
            },
            status_code=403,
        )

    return templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        {
            "title": "Admin Dashboard",
            "app_name": Config.get("app.name", "moddingcartel"),
            "db_host": Config.get("database.host", "127.0.0.1"),
            "db_name": Config.get("database.database", "switch_db"),
        },
    )


async def admin_directories(request: Request) -> Response:
    """Directory management page"""
    if not Config.is_initialized():
        return RedirectResponse(url="/admincp/init", status_code=303)

    # Check if user is logged in and is admin
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login", status_code=303)

    if not request.session.get("is_admin"):
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "title": "Access Denied",
                "error_message": "You do not have permission to access the admin dashboard.",
                "app_name": Config.get("app.name", "moddingcartel"),
            },
            status_code=403,
        )

    # Get all directories
    directories = await db.get_all_directories()

    # Check space available for each directory
    for directory in directories:
        dir_path = directory.get("path", "")
        if os.path.exists(dir_path):
            try:
                stat = shutil.disk_usage(dir_path)
                directory["total_space"] = stat.total
                directory["used_space"] = stat.used
                directory["free_space"] = stat.free
                directory["exists"] = True
            except Exception as e:
                logger.error(f"Error getting disk usage for {dir_path}: {e}")
                directory["exists"] = False
        else:
            directory["exists"] = False

    return templates.TemplateResponse(
        request,
        "admin/directories.html",
        {
            "title": "Directory Management",
            "app_name": Config.get("app.name", "moddingcartel"),
            "directories": directories,
        },
    )


async def admin_add_directory(request: Request) -> Response:
    """Add a new directory to scan"""
    if not Config.is_initialized():
        return JSONResponse(
            {"success": False, "error": "System not initialized"}, status_code=400
        )

    # Check if user is logged in and is admin
    if not request.session.get("user_id") or not request.session.get("is_admin"):
        return JSONResponse(
            {"success": False, "error": "Unauthorized"}, status_code=403
        )

    try:
        form_data = await request.form()
        directory_path = form_data.get("path", "").strip()

        if not directory_path:
            return JSONResponse(
                {"success": False, "error": "Directory path is required"},
                status_code=400,
            )

        # Check if directory exists
        if not os.path.exists(directory_path):
            return JSONResponse(
                {"success": False, "error": "Directory does not exist"}, status_code=400
            )

        if not os.path.isdir(directory_path):
            return JSONResponse(
                {"success": False, "error": "Path is not a directory"}, status_code=400
            )

        # Add directory to database
        result = await db.add_directory(directory_path)
        if result:
            return JSONResponse(
                {"success": True, "message": "Directory added successfully"}
            )
        else:
            return JSONResponse(
                {
                    "success": False,
                    "error": "Directory already exists or could not be added",
                },
                status_code=400,
            )

    except Exception as e:
        logger.error(f"Error adding directory: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def admin_delete_directory(request: Request) -> Response:
    """Delete a directory"""
    if not Config.is_initialized():
        return JSONResponse(
            {"success": False, "error": "System not initialized"}, status_code=400
        )

    # Check if user is logged in and is admin
    if not request.session.get("user_id") or not request.session.get("is_admin"):
        return JSONResponse(
            {"success": False, "error": "Unauthorized"}, status_code=403
        )

    try:
        form_data = await request.form()
        directory_id = form_data.get("id", "").strip()

        if not directory_id:
            return JSONResponse(
                {"success": False, "error": "Directory ID is required"}, status_code=400
            )

        result = await db.delete_directory(directory_id)
        if result:
            return JSONResponse(
                {"success": True, "message": "Directory deleted successfully"}
            )
        else:
            return JSONResponse(
                {"success": False, "error": "Could not delete directory"},
                status_code=400,
            )

    except Exception as e:
        logger.error(f"Error deleting directory: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def admin_scan_directory(request: Request) -> Response:
    """Scan a directory for game files"""
    if not Config.is_initialized():
        return JSONResponse(
            {"success": False, "error": "System not initialized"}, status_code=400
        )

    # Check if user is logged in and is admin
    if not request.session.get("user_id") or not request.session.get("is_admin"):
        return JSONResponse(
            {"success": False, "error": "Unauthorized"}, status_code=403
        )

    try:
        form_data = await request.form()
        directory_id = form_data.get("id", "").strip()

        if not directory_id:
            return JSONResponse(
                {"success": False, "error": "Directory ID is required"}, status_code=400
            )

        # Get directory from database
        directories = await db.get_all_directories()
        directory = None
        for d in directories:
            if d.get("_key") == directory_id:
                directory = d
                break

        if not directory:
            return JSONResponse(
                {"success": False, "error": "Directory not found"}, status_code=404
            )

        directory_path = directory.get("path")
        if not os.path.exists(directory_path):
            return JSONResponse(
                {"success": False, "error": "Directory does not exist on disk"},
                status_code=400,
            )

        # Scan the directory
        username = request.session.get("username", "admin")
        added_count, skipped_count = await scan_directory_for_files(
            directory_path, username
        )

        return JSONResponse(
            {
                "success": True,
                "message": f"Scan complete. Added {added_count} files, skipped {skipped_count} duplicates",
            }
        )

    except Exception as e:
        logger.error(f"Error scanning directory: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def admin_clear_entries(request: Request) -> Response:
    """Clear all entries from the database"""
    if not Config.is_initialized():
        return JSONResponse(
            {"success": False, "error": "System not initialized"}, status_code=400
        )

    # Check if user is logged in and is admin
    if not request.session.get("user_id") or not request.session.get("is_admin"):
        return JSONResponse(
            {"success": False, "error": "Unauthorized"}, status_code=403
        )

    try:
        result = await db.clear_all_entries()
        if result:
            return JSONResponse(
                {"success": True, "message": "All entries cleared successfully"}
            )
        else:
            return JSONResponse(
                {"success": False, "error": "Could not clear entries"}, status_code=400
            )

    except Exception as e:
        logger.error(f"Error clearing entries: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def admin_rescan_all(request: Request) -> Response:
    """Rescan all directories"""
    if not Config.is_initialized():
        return JSONResponse(
            {"success": False, "error": "System not initialized"}, status_code=400
        )

    # Check if user is logged in and is admin
    if not request.session.get("user_id") or not request.session.get("is_admin"):
        return JSONResponse(
            {"success": False, "error": "Unauthorized"}, status_code=403
        )

    try:
        directories = await db.get_all_directories()
        username = request.session.get("username", "admin")

        total_added = 0
        total_skipped = 0

        for directory in directories:
            directory_path = directory.get("path")
            if os.path.exists(directory_path):
                added, skipped = await scan_directory_for_files(
                    directory_path, username
                )
                total_added += added
                total_skipped += skipped

        return JSONResponse(
            {
                "success": True,
                "message": f"Rescan complete. Added {total_added} files, skipped {total_skipped} duplicates",
            }
        )

    except Exception as e:
        logger.error(f"Error rescanning directories: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def scan_directory_for_files(
    directory_path: str, username: str, max_depth: int = 3
) -> tuple:
    """
    Scan a directory recursively for game files (.nsz, .nsp, .xci)
    Returns tuple of (added_count, skipped_count)
    """
    added_count = 0
    skipped_count = 0

    def should_process_file(file_path: str) -> bool:
        """Check if file has valid extension"""
        return file_path.lower().endswith((".nsz", ".nsp", ".xci"))

    def get_file_type(file_path: str) -> str:
        """Get file type from extension"""
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".nsz":
            return FileType.NSZ.value
        elif ext == ".nsp":
            return FileType.NSP.value
        elif ext == ".xci":
            return FileType.XCI.value
        return "nsp"  # default

    def walk_directory(path: str, current_depth: int = 0):
        """Recursively walk directory up to max_depth"""
        if current_depth > max_depth:
            return

        try:
            for entry in os.scandir(path):
                if entry.is_file() and should_process_file(entry.path):
                    yield entry.path
                elif entry.is_dir() and current_depth < max_depth:
                    yield from walk_directory(entry.path, current_depth + 1)
        except PermissionError:
            logger.warning(f"Permission denied: {path}")
        except Exception as e:
            logger.error(f"Error scanning {path}: {e}")

    # Scan directory
    for file_path in walk_directory(directory_path):
        try:
            # Check if entry already exists
            if await db.entry_exists(file_path):
                skipped_count += 1
                continue

            # Get file stats
            file_stat = os.stat(file_path)
            file_size = file_stat.st_size

            # Get file timestamps
            file_created = datetime.fromtimestamp(file_stat.st_ctime).isoformat()
            file_modified = datetime.fromtimestamp(file_stat.st_mtime).isoformat()

            # Get file name without extension
            file_name = os.path.splitext(os.path.basename(file_path))[0]

            # Get file extension
            file_extension = os.path.splitext(file_path)[1].lower()

            # Create entry with enhanced metadata
            entry_data = {
                "name": file_name,
                "source": file_path,
                "type": "filepath",
                "file_type": get_file_type(file_path),
                "size": file_size,
                "created_by": username,
                "created_at": datetime.utcnow().isoformat(),
                "file_created_at": file_created,
                "file_modified_at": file_modified,
                "metadata": {
                    "extension": file_extension,
                    "directory": os.path.dirname(file_path),
                    "original_filename": os.path.basename(file_path),
                },
            }

            result = await db.add_entry(entry_data)
            if result:
                added_count += 1

        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")

    return added_count, skipped_count


async def admin_users(request: Request) -> Response:
    """User management page"""
    if not Config.is_initialized():
        return RedirectResponse(url="/admincp/init", status_code=303)

    # Check if user is logged in and is admin
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login", status_code=303)

    if not request.session.get("is_admin"):
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "title": "Access Denied",
                "error_message": "You do not have permission to access the admin dashboard.",
                "app_name": Config.get("app.name", "moddingcartel"),
            },
            status_code=403,
        )

    # Get all users
    users = await db.get_all_users()

    # Get statistics for each user
    for user in users:
        user_id = user.get("_key")
        if user_id:
            user_stats = await db.get_user_statistics(user_id)
            user["statistics"] = user_stats

        # Don't show password hashes in the template
        user.pop("password_hash", None)

    return templates.TemplateResponse(
        request,
        "admin/users.html",
        {
            "title": "User Management",
            "app_name": Config.get("app.name", "moddingcartel"),
            "users": users,
        },
    )


async def admin_update_user_role(request: Request) -> Response:
    """Update a user's role (admin, moderator, or uploader status)"""
    if not Config.is_initialized():
        return JSONResponse(
            {"success": False, "error": "System not initialized"}, status_code=400
        )

    # Check if user is logged in and is admin
    if not request.session.get("user_id") or not request.session.get("is_admin"):
        return JSONResponse(
            {"success": False, "error": "Unauthorized"}, status_code=403
        )

    try:
        form_data = await request.form()
        user_id = form_data.get("user_id", "").strip()
        role = form_data.get("role", "").strip()
        action = form_data.get("action", "").strip()  # 'grant' or 'revoke'

        if not user_id or not role or not action:
            return JSONResponse(
                {"success": False, "error": "Missing required fields"}, status_code=400
            )

        if role not in ["admin", "moderator", "uploader"]:
            return JSONResponse(
                {"success": False, "error": "Invalid role"}, status_code=400
            )

        if action not in ["grant", "revoke"]:
            return JSONResponse(
                {"success": False, "error": "Invalid action"}, status_code=400
            )

        # Don't allow admin to remove their own admin status
        current_user_id = request.session.get("user_id")
        if user_id == current_user_id and role == "admin" and action == "revoke":
            return JSONResponse(
                {"success": False, "error": "You cannot revoke your own admin status"},
                status_code=400,
            )

        # Update the user's status
        new_status = action == "grant"
        if role == "admin":
            success = await db.update_user_admin_status(user_id, new_status)
        elif role == "moderator":
            success = await db.update_user_moderator_status(user_id, new_status)
        else:  # uploader
            success = await db.update_user_uploader_status(user_id, new_status)

        if not success:
            return JSONResponse(
                {"success": False, "error": "Failed to update user role"},
                status_code=500,
            )

        # Get target user info for logging
        target_user = await db.get_user_by_id(user_id)
        target_username = (
            target_user.get("username", "unknown") if target_user else "unknown"
        )

        # Log the action to audit log with IP information
        actor_id = request.session.get("user_id")
        actor_username = request.session.get("username", "unknown")
        ip_info = get_ip_info(request)

        audit_data = {
            "action": f"role_{action}ed",
            "actor_id": actor_id,
            "actor_username": actor_username,
            "target_id": user_id,
            "target_username": target_username,
            "details": {"role": role, "action": action, "new_status": new_status},
            "ip_address": ip_info["ip_address"],
            "client_ip": ip_info["client_ip"],
        }
        if "forwarded_ip" in ip_info:
            audit_data["forwarded_ip"] = ip_info["forwarded_ip"]

        await db.add_audit_log(audit_data)

        logger.info(
            f"Role {action}ed for user {target_username}: {role} from {format_ip_for_log(request)}"
        )

        return JSONResponse(
            {"success": True, "message": f"Successfully {action}ed {role} status"}
        )

    except Exception as e:
        logger.error(f"Error updating user role: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def admin_force_password_change(request: Request) -> Response:
    """Force change a user's password"""
    if not Config.is_initialized():
        return JSONResponse(
            {"success": False, "error": "System not initialized"}, status_code=400
        )

    # Check if user is logged in and is admin
    if not request.session.get("user_id") or not request.session.get("is_admin"):
        return JSONResponse(
            {"success": False, "error": "Unauthorized"}, status_code=403
        )

    try:
        form_data = await request.form()
        user_id = form_data.get("user_id", "").strip()
        new_password = form_data.get("new_password", "").strip()

        if not user_id or not new_password:
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
        target_user = await db.get_user_by_id(user_id)
        if not target_user:
            return JSONResponse(
                {"success": False, "error": "User not found"}, status_code=404
            )

        # Update the password
        new_password_hash = User.hash_password(new_password)
        success = await db.update_user_password(user_id, new_password_hash)

        if not success:
            return JSONResponse(
                {"success": False, "error": "Failed to update password"},
                status_code=500,
            )

        # Log the action to audit log with IP information
        actor_id = request.session.get("user_id")
        actor_username = request.session.get("username", "unknown")
        target_username = target_user.get("username", "unknown")
        ip_info = get_ip_info(request)

        audit_data = {
            "action": "password_force_changed",
            "actor_id": actor_id,
            "actor_username": actor_username,
            "target_id": user_id,
            "target_username": target_username,
            "details": {
                "changed_by": "admin",
                "reason": "Force password change from admin panel",
            },
            "ip_address": ip_info["ip_address"],
            "client_ip": ip_info["client_ip"],
        }
        if "forwarded_ip" in ip_info:
            audit_data["forwarded_ip"] = ip_info["forwarded_ip"]

        await db.add_audit_log(audit_data)

        logger.info(
            f"Password force changed for user: {target_username} by {actor_username} from {format_ip_for_log(request)}"
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


async def admin_api_keys(request: Request) -> Response:
    """Admin page for managing all API keys"""
    if not Config.is_initialized():
        return RedirectResponse(url="/admincp/init", status_code=303)

    # Check if user is logged in and is admin
    if not request.session.get("user_id") or not request.session.get("is_admin"):
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "title": "Unauthorized",
                "error": "You must be an administrator to access this page",
                "app_name": Config.get("app.name", "moddingcartel"),
            },
            status_code=403,
        )

    # Get all API keys with user information
    all_api_keys = await db.get_all_api_keys()

    # Enhance API keys with user information
    for key in all_api_keys:
        user = await db.get_user_by_id(key.get("user_id", ""))
        if user:
            key["username"] = user.get("username", "Unknown")
        else:
            key["username"] = "Unknown"

    return templates.TemplateResponse(
        request,
        "admin/api_keys.html",
        {
            "title": "API Key Management",
            "app_name": Config.get("app.name", "moddingcartel"),
            "api_keys": all_api_keys,
        },
    )


async def admin_revoke_api_key(request: Request) -> Response:
    """Admin endpoint to revoke any API key"""
    if not Config.is_initialized():
        return JSONResponse(
            {"success": False, "error": "System not initialized"}, status_code=400
        )

    # Check if user is logged in and is admin
    if not request.session.get("user_id") or not request.session.get("is_admin"):
        return JSONResponse(
            {"success": False, "error": "Unauthorized"}, status_code=403
        )

    try:
        form = await request.form()
        key_id = form.get("key_id", "").strip()

        if not key_id:
            return JSONResponse(
                {"success": False, "error": "Key ID is required"}, status_code=400
            )

        # Revoke the key
        success = await db.revoke_api_key(key_id)

        if success:
            return JSONResponse(
                {"success": True, "message": "API key revoked successfully"}
            )
        else:
            return JSONResponse(
                {"success": False, "error": "Failed to revoke API key"}, status_code=500
            )

    except Exception as e:
        logger.error(f"Error revoking API key: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def admin_user_api_usage(request: Request) -> Response:
    """Admin page for viewing user API usage statistics"""
    if not Config.is_initialized():
        return RedirectResponse(url="/admincp/init", status_code=303)

    # Check if user is logged in and is admin
    if not request.session.get("user_id") or not request.session.get("is_admin"):
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "title": "Unauthorized",
                "error": "You must be an administrator to access this page",
                "app_name": Config.get("app.name", "moddingcartel"),
            },
            status_code=403,
        )

    # Get user_id from query params if specified
    user_id = request.query_params.get("user_id")

    if user_id:
        # Get specific user's usage
        user = await db.get_user_by_id(user_id)
        if not user:
            return templates.TemplateResponse(
                request,
                "error.html",
                {
                    "title": "User Not Found",
                    "error": "The specified user was not found",
                    "app_name": Config.get("app.name", "moddingcartel"),
                },
                status_code=404,
            )

        usage_stats = await db.get_api_usage_stats_by_user(user_id)
        recent_usage = await db.get_api_usage_by_user(user_id, limit=100)

        return templates.TemplateResponse(
            request,
            "admin/user_api_usage.html",
            {
                "title": f"API Usage - {user.get('username')}",
                "app_name": Config.get("app.name", "moddingcartel"),
                "user": user,
                "usage_stats": usage_stats,
                "recent_usage": recent_usage,
            },
        )
    else:
        # Get all users with their usage stats
        all_users = await db.get_all_users()
        user_usage_list = []

        for user in all_users:
            user_id = user.get("_key")
            stats = await db.get_api_usage_stats_by_user(user_id)
            user_usage_list.append(
                {
                    "user_id": user_id,
                    "username": user.get("username"),
                    "total_calls": stats.get("total_calls", 0),
                    "created_at": user.get("created_at"),
                }
            )

        return templates.TemplateResponse(
            request,
            "admin/api_usage_overview.html",
            {
                "title": "API Usage Overview",
                "app_name": Config.get("app.name", "moddingcartel"),
                "user_usage_list": user_usage_list,
            },
        )


async def admin_audit_logs(request: Request) -> Response:
    """View audit logs"""
    if not Config.is_initialized():
        return RedirectResponse(url="/admincp/init", status_code=303)

    # Check if user is logged in and is admin
    if not request.session.get("user_id") or not request.session.get("is_admin"):
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "title": "Unauthorized",
                "error": "You must be an administrator to access this page",
                "app_name": Config.get("app.name", "moddingcartel"),
            },
            status_code=403,
        )

    # Get filters from query parameters
    action_filter = request.query_params.get("action", None)
    actor_filter = request.query_params.get("actor", None)
    target_filter = request.query_params.get("target", None)
    limit = min(int(request.query_params.get("limit", 100)), 500)  # Max 500

    # Fetch audit logs
    logs = await db.get_audit_logs(
        limit=limit,
        action_filter=action_filter,
        actor_id_filter=actor_filter,
        target_id_filter=target_filter,
    )

    # Get unique actions for filter dropdown
    all_logs_sample = await db.get_audit_logs(limit=1000)
    unique_actions = sorted(
        list(set(log.get("action", "") for log in all_logs_sample if log.get("action")))
    )

    # Get statistics
    stats = await db.get_audit_log_stats()

    return templates.TemplateResponse(
        request,
        "admin/audit_logs.html",
        {
            "title": "Audit Logs",
            "app_name": Config.get("app.name", "moddingcartel"),
            "logs": logs,
            "stats": stats,
            "unique_actions": unique_actions,
            "current_action": action_filter,
            "limit": limit,
        },
    )


async def admin_activity_logs(request: Request) -> Response:
    """View activity logs"""
    if not Config.is_initialized():
        return RedirectResponse(url="/admincp/init", status_code=303)

    # Check if user is logged in and is admin
    if not request.session.get("user_id") or not request.session.get("is_admin"):
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "title": "Unauthorized",
                "error": "You must be an administrator to access this page",
                "app_name": Config.get("app.name", "moddingcartel"),
            },
            status_code=403,
        )

    # Get filters from query parameters
    event_type_filter = request.query_params.get("event_type", None)
    user_filter = request.query_params.get("user", None)
    limit = min(int(request.query_params.get("limit", 100)), 500)  # Max 500

    # Fetch activity logs
    logs = await db.get_activity_logs(
        limit=limit, event_type_filter=event_type_filter, user_id_filter=user_filter
    )

    # Get unique event types for filter dropdown
    all_logs_sample = await db.get_activity_logs(limit=1000)
    unique_event_types = sorted(
        list(
            set(
                log.get("event_type", "")
                for log in all_logs_sample
                if log.get("event_type")
            )
        )
    )

    # Get statistics
    stats = await db.get_activity_log_stats()

    return templates.TemplateResponse(
        request,
        "admin/activity_logs.html",
        {
            "title": "Activity Logs",
            "app_name": Config.get("app.name", "moddingcartel"),
            "logs": logs,
            "stats": stats,
            "unique_event_types": unique_event_types,
            "current_event_type": event_type_filter,
            "limit": limit,
        },
    )


async def admin_storage_info(request: Request) -> Response:
    """View storage and game statistics"""
    if not Config.is_initialized():
        return RedirectResponse(url="/admincp/init", status_code=303)

    # Check if user is logged in and is admin
    if not request.session.get("user_id") or not request.session.get("is_admin"):
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "title": "Unauthorized",
                "error": "You must be an administrator to access this page",
                "app_name": Config.get("app.name", "moddingcartel"),
            },
            status_code=403,
        )

    # Get all directories
    directories = await db.get_all_directories()

    # Get storage info for each directory
    storage_data = []
    total_games = 0
    total_size_bytes = 0

    for directory in directories:
        dir_path = directory.get("path", "")
        if not os.path.exists(dir_path):
            storage_data.append(
                {
                    "path": dir_path,
                    "exists": False,
                    "game_count": 0,
                    "total_size": 0,
                    "available_space": 0,
                    "total_space": 0,
                    "used_space": 0,
                    "usage_percent": 0,
                }
            )
            continue

        try:
            # Get disk usage info
            stat = shutil.disk_usage(dir_path)
            total_space = stat.total
            used_space = stat.used
            available_space = stat.free
            usage_percent = (used_space / total_space * 100) if total_space > 0 else 0

            # Count games in this directory (from entries collection)
            cursor = await db.db.aql.execute(
                "FOR doc IN entries FILTER doc.type == 'filepath' && STARTS_WITH(doc.source, @path) RETURN doc",
                bind_vars={"path": dir_path},
            )

            dir_games = []
            dir_size = 0
            async with cursor:
                async for doc in cursor:
                    dir_games.append(doc)
                    dir_size += doc.get("size", 0)

            game_count = len(dir_games)
            total_games += game_count
            total_size_bytes += dir_size

            storage_data.append(
                {
                    "path": dir_path,
                    "exists": True,
                    "game_count": game_count,
                    "total_size": dir_size,
                    "available_space": available_space,
                    "total_space": total_space,
                    "used_space": used_space,
                    "usage_percent": usage_percent,
                }
            )
        except Exception as e:
            logger.error(f"Error getting storage info for {dir_path}: {e}")
            storage_data.append(
                {
                    "path": dir_path,
                    "exists": False,
                    "error": str(e),
                    "game_count": 0,
                    "total_size": 0,
                    "available_space": 0,
                    "total_space": 0,
                    "used_space": 0,
                    "usage_percent": 0,
                }
            )

    # Get total game count from database (including URLs)
    all_entries = await db.get_all_entries()
    total_entries = len(all_entries)

    return templates.TemplateResponse(
        request,
        "admin/storage_info.html",
        {
            "title": "Storage Information",
            "app_name": Config.get("app.name", "moddingcartel"),
            "storage_data": storage_data,
            "total_games": total_games,
            "total_entries": total_entries,
            "total_size_bytes": total_size_bytes,
        },
    )


async def admin_upload_statistics(request: Request) -> Response:
    """View upload statistics for all uploaders"""
    if not Config.is_initialized():
        return RedirectResponse(url="/admincp/init", status_code=303)

    # Check if user is logged in and is admin
    if not request.session.get("user_id") or not request.session.get("is_admin"):
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

    # Get all uploader statistics
    uploader_stats = await db.get_all_uploader_statistics()

    # Get overall statistics
    overall_stats = await db.get_upload_statistics()

    return templates.TemplateResponse(
        request,
        "admin/upload_statistics.html",
        {
            "title": "Upload Statistics",
            "app_name": Config.get("app.name", "moddingcartel"),
            "uploader_stats": uploader_stats,
            "overall_stats": overall_stats,
        },
    )


async def admin_reports(request: Request) -> Response:
    """View and manage file reports (for admins, mods, and uploaders)"""
    if not Config.is_initialized():
        return RedirectResponse(url="/admincp/init", status_code=303)

    # Check if user is logged in and has permission (admin, mod, or uploader)
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login", status_code=303)

    is_admin = request.session.get("is_admin", False)
    is_moderator = request.session.get("is_moderator", False)
    is_uploader = request.session.get("is_uploader", False)

    if not (is_admin or is_moderator or is_uploader):
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

    # Get status filter from query params (default to open)
    status = request.query_params.get("status", "open")

    # Get all reports
    reports = await db.get_all_reports(status=status if status != "all" else None)

    # Get count of open reports
    open_count = await db.count_reports(status="open")
    resolved_count = await db.count_reports(status="resolved")

    return templates.TemplateResponse(
        request,
        "admin/reports.html",
        {
            "title": "File Reports",
            "app_name": Config.get("app.name", "moddingcartel"),
            "reports": reports,
            "current_status": status,
            "open_count": open_count,
            "resolved_count": resolved_count,
            "is_admin": is_admin,
            "is_moderator": is_moderator,
            "is_uploader": is_uploader,
        },
    )


async def admin_resolve_report(request: Request) -> Response:
    """Mark a report as resolved"""
    if not Config.is_initialized():
        return JSONResponse(
            {"success": False, "error": "System not initialized"}, status_code=400
        )

    # Check if user is logged in and has permission (admin, mod, or uploader)
    if not request.session.get("user_id"):
        return JSONResponse(
            {"success": False, "error": "Unauthorized"}, status_code=403
        )

    is_admin = request.session.get("is_admin", False)
    is_moderator = request.session.get("is_moderator", False)
    is_uploader = request.session.get("is_uploader", False)

    if not (is_admin or is_moderator or is_uploader):
        return JSONResponse(
            {"success": False, "error": "Unauthorized"}, status_code=403
        )

    try:
        form_data = await request.form()
        report_id = form_data.get("report_id", "").strip()

        if not report_id:
            return JSONResponse(
                {"success": False, "error": "Missing report ID"}, status_code=400
            )

        # Resolve the report
        user_id = request.session.get("user_id")
        username = request.session.get("username", "Unknown")

        success = await db.resolve_report(report_id, user_id, username)

        if not success:
            return JSONResponse(
                {"success": False, "error": "Failed to resolve report"}, status_code=500
            )

        # Log the action
        ip_info = get_ip_info(request)
        activity_data = {
            "event_type": "report_resolved",
            "user_id": user_id,
            "username": username,
            "details": {"report_id": report_id},
            "ip_address": ip_info["ip_address"],
            "client_ip": ip_info["client_ip"],
        }
        if "forwarded_ip" in ip_info:
            activity_data["forwarded_ip"] = ip_info["forwarded_ip"]

        await db.add_activity_log(activity_data)

        logger.info(
            f"Report {report_id} resolved by {username} from {format_ip_for_log(request)}"
        )

        return JSONResponse({"success": True, "message": "Report marked as resolved"})

    except Exception as e:
        logger.error(f"Error resolving report: {e}", exc_info=True)
        return JSONResponse(
            {"success": False, "error": "An error occurred while resolving the report"},
            status_code=500,
        )


async def admin_migrate_passwords(request: Request) -> Response:
    """Migrate all user passwords from SHA-256 to Argon2"""
    if not Config.is_initialized():
        return JSONResponse(
            {"success": False, "error": "System not initialized"}, status_code=400
        )

    # Check if user is logged in and is admin
    if not request.session.get("user_id") or not request.session.get("is_admin"):
        return JSONResponse(
            {"success": False, "error": "Unauthorized"}, status_code=403
        )

    try:
        # Get all users
        users = await db.get_all_users()

        already_migrated_count = 0
        failed_count = 0

        for user_data in users:
            user = User.from_dict(user_data)
            password_hash = user.password_hash

            # Check if password needs migration (not Argon2)
            if User.needs_rehash(password_hash):
                # We can't migrate without the plain password, so we skip
                # Migration will happen automatically when users log in
                logger.info(
                    f"User {user.username} password marked for migration on next login"
                )
                failed_count += 1
            else:
                already_migrated_count += 1

        return JSONResponse(
            {
                "success": True,
                "message": f"Password migration status checked. {already_migrated_count} already using Argon2, {failed_count} will be migrated on next login.",
                "already_migrated": already_migrated_count,
                "pending_migration": failed_count,
            }
        )

    except Exception as e:
        logger.error(f"Error checking password migration status: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def admin_password_migration_status(request: Request) -> Response:
    """Get password migration status"""
    if not Config.is_initialized():
        return JSONResponse(
            {"success": False, "error": "System not initialized"}, status_code=400
        )

    # Check if user is logged in and is admin
    if not request.session.get("user_id") or not request.session.get("is_admin"):
        return JSONResponse(
            {"success": False, "error": "Unauthorized"}, status_code=403
        )

    try:
        users = await db.get_all_users()

        total_users = len(users)
        argon2_count = 0
        sha256_count = 0

        for user_data in users:
            password_hash = user_data.get("password_hash", "")
            if password_hash.startswith("$argon2"):
                argon2_count += 1
            else:
                sha256_count += 1

        return JSONResponse(
            {
                "success": True,
                "total_users": total_users,
                "argon2_count": argon2_count,
                "sha256_count": sha256_count,
                "migration_percentage": round(
                    (argon2_count / total_users * 100) if total_users > 0 else 0, 2
                ),
            }
        )

    except Exception as e:
        logger.error(f"Error getting password migration status: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)
