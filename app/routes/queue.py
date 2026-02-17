import logging

from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.templating import Jinja2Templates

from app.database import db

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="app/templates")


async def game_queue_page(request: Request) -> Response:
    """Game queue page for users"""
    # Check if user is logged in
    if not request.session.get("username"):
        return RedirectResponse(url="/login", status_code=303)

    user_id = request.session.get("user_id")

    # Get user's send queue (all items including completed/failed)
    queue_items = await db.get_all_send_queue_items(user_id)

    return templates.TemplateResponse(
        request,
        "user/game_queue.html",
        {
            "title": "Game Queue",
            "queue_items": queue_items,
        }
    )


async def get_queue_status(request: Request) -> Response:
    """API endpoint to get current queue status (for real-time updates)"""
    # Check if user is logged in
    if not request.session.get("username"):
        return JSONResponse(
            {"error": "Authentication required"},
            status_code=401,
        )

    try:
        user_id = request.session.get("user_id")

        # Get pending/processing items
        queue_items = await db.get_send_queue(user_id)

        return JSONResponse({
            "success": True,
            "queue": queue_items,
        })

    except Exception as e:
        logger.error(f"Get queue status error: {e}", exc_info=True)
        return JSONResponse(
            {"success": False, "error": "An error occurred"},
            status_code=500,
        )
