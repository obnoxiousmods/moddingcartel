from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.templating import Jinja2Templates

from app.config import Config
from app.database import db

# We'll import templates from main.py after we update it
templates = Jinja2Templates(directory="app/templates")


async def index(request: Request) -> Response:
    """Homepage with search dashboard"""
    # Check if system is initialized
    if not Config.is_initialized():
        return RedirectResponse(url="/admincp/init", status_code=303)

    # Check if user is moderator or admin to show pending requests
    is_moderator = request.session.get("is_moderator", False) or request.session.get(
        "is_admin", False
    )
    pending_count = 0

    if is_moderator:
        # Get pending requests count for mods (efficient count query)
        pending_count = await db.count_requests(status="pending")

    # Get system statistics for dashboard
    system_stats = await db.get_system_statistics()

    # Get user statistics if logged in
    user_stats = None
    user_id = request.session.get("user_id")
    if user_id:
        user_stats = await db.get_user_statistics(user_id)

    response = templates.TemplateResponse(
        request,
        "index.html",
        {
            "title": "Home",
            "app_name": Config.get("app.name", "moddingcartel"),
            "is_moderator": is_moderator,
            "pending_count": pending_count,
            "system_stats": system_stats,
            "user_stats": user_stats,
        },
    )

    # Add header to deter automated API usage of the homepage
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"

    return response


async def search_page(request: Request) -> Response:
    """Dedicated search page"""
    # Check if system is initialized
    if not Config.is_initialized():
        return RedirectResponse(url="/admincp/init", status_code=303)

    # Check if user is moderator or admin for the search.js script
    is_moderator = request.session.get("is_moderator", False) or request.session.get(
        "is_admin", False
    )

    return templates.TemplateResponse(
        request,
        "search.html",
        {
            "title": "Search Games",
            "app_name": Config.get("app.name", "moddingcartel"),
            "is_moderator": is_moderator,
        },
    )


async def api_docs_page(request: Request) -> Response:
    """API documentation page"""
    # Check if system is initialized
    if not Config.is_initialized():
        return RedirectResponse(url="/admincp/init", status_code=303)

    return templates.TemplateResponse(
        request,
        "api_docs.html",
        {
            "title": "API Documentation",
            "app_name": Config.get("app.name", "moddingcartel"),
        },
    )
