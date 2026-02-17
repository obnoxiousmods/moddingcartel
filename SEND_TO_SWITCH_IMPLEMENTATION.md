# Send to Switch Feature - Implementation Summary

## Overview

This implementation adds a comprehensive "Send to Switch" feature that allows users to send Nintendo Switch games directly to their console via Sphaira's USB connection (preferred) or FTP server (fallback), with real-time progress tracking and queue management.

## Key Update: USB Support

**USB transfer support has been added** with automatic detection and preference over FTP:

- **Faster Transfers**: USB transfers are significantly faster than network FTP
- **Auto-Detection**: Client automatically detects USB connection on startup
- **Fallback to FTP**: If USB is not available, falls back to network FTP
- **Tinfoil/Awoo Protocol**: Uses industry-standard protocol compatible with Sphaira, Awoo Installer, and Tinfoil
- **Seamless Integration**: Same API and queue system, just faster transfers

## Components

### 1. Backend API (`app/routes/api.py`)

#### New Endpoints:
- `POST /api/auth/login` - JSON login endpoint that creates/regenerates "Send to Switch" API keys
- `POST /api/send-to-switch` - Add a game to the send queue
- `GET /api/send-queue` - Get pending/processing queue items (for client polling)
- `POST /api/send-queue/update` - Update queue item status
- `POST /api/send-queue/progress` - Update queue item progress (percentage, speed, bytes)
- `POST /api/send-queue/delete` - Delete a queue item (web UI)
- `POST /api/send-queue/clear` - Clear all queue items (web UI)
- `GET /api/queue/status` - Get queue status for web UI real-time updates

### 2. Database Layer (`app/database.py`)

#### New Collection:
- `send_queue` - Stores queue items with progress tracking

#### New Methods:
- `add_to_send_queue()` - Add game to user's queue
- `get_send_queue()` - Get pending/processing items
- `get_all_send_queue_items()` - Get all items including completed/failed
- `update_send_queue_item()` - Update item status
- `update_send_queue_progress()` - Update progress information
- `delete_send_queue_item()` - Delete single item
- `clear_send_queue()` - Clear all user's queue items

#### Queue Item Schema:
```python
{
    "user_id": str,
    "entry_id": str,
    "status": str,  # pending, processing, completed, failed
    "created_at": str,
    "updated_at": str,
    "progress_percent": int,  # 0-100
    "bytes_transferred": int,
    "transfer_speed": float,  # bytes per second
    "error_message": str  # if failed
}
```

### 3. Python Client Library (`software/cartel.py`)

A reusable HTTP client for the ModdingCartel API:

#### Methods:
- `login(username, password)` - Authenticate and get API key
- `get_send_queue()` - Poll for pending games
- `update_queue_item(queue_item_id, status)` - Update status
- `update_queue_progress(...)` - Report progress during transfer
- `get_entry_info(entry_id)` - Get entry details

### 4. Send to Switch Client (`software/send_to_switch.py`)

A full-featured Python application with TUI interface:

#### Features:
- **USB Connection Detection**: Automatic detection of Switch via USB on startup (preferred)
- **Network Discovery**: Automatic Switch discovery on local network (fallback)
- **Auto Method Selection**: Intelligently chooses USB or FTP based on availability
- Configuration stored in `~/.config/send_to_switch/config.yaml`
- Polls server every 3 seconds for new games
- Sequential transfers (one at a time, USB or FTP)
- Progress reporting every 2 seconds
- Rich TUI showing:
  - Connection status (USB or FTP)
  - Queue size
  - Transfer statistics
  - Current task
  - Switch IP address (for FTP mode)

#### Configuration:
```yaml
api_key: <generated_on_login>
base_url: http://127.0.0.1:6069
switch_ip: <auto_discovered>
```

### 5. Web Interface

#### Game Queue Page (`app/templates/user/game_queue.html`)

Accessible from user dropdown menu:
- Real-time updates (auto-refresh every 3 seconds)
- Visual progress bars for active transfers
- Transfer speed and bytes transferred display
- Status badges (pending, processing, completed, failed)
- Delete individual items
- Clear all items button
- Queue statistics (pending, processing, completed, failed counts)
- Error messages for failed items

#### Search Page Updates (`static/js/search.js`, `app/templates/search.html`)

- New "📤 Send to Switch" button on each game (authenticated users only)
- JavaScript handler to call API endpoint
- Toast notifications for success/error
- CSS styling for the button

#### User Dropdown (`app/templates/base.html`)

- Added "Game Queue" menu item with 📤 icon

## Workflow

### Adding a Game to Queue (Web → Database):
```
1. User clicks "Send to Switch" button on game
2. JavaScript sends POST to /api/send-to-switch
3. Backend adds item to send_queue collection
4. User sees success toast notification
```

### Processing Queue (Client → Switch):
```
1. Client polls /api/send-queue every 3 seconds
2. If queue has items, client:
   a. Detects connection type (USB preferred, FTP fallback)
   b. Marks first item as "processing"
   c. For USB: Direct transfer via USB using Tinfoil/Awoo protocol
   d. For FTP: Discovers Switch if needed (via network scan), initiates FTP transfer
   e. Reports progress every 2 seconds
   f. Marks as "completed" or "failed"
3. Client moves to next item in queue
```

### Viewing Progress (Web):
```
1. User opens Game Queue page
2. JavaScript calls /api/queue/status every 3 seconds
3. Updates progress bars and stats in real-time
4. Shows transfer speed, bytes transferred, percentage
```

## Security

### Authentication:
- API endpoints use either session auth (web) or API key auth (client)
- API keys are hashed with SHA-256 before storage
- Keys are shown only once during creation/regeneration
- Each user gets one "Send to Switch" API key (auto-regenerated on re-login)

### Authorization:
- Users can only access their own queue items
- All endpoints verify user_id matches queue item owner
- Queue items include user_id for isolation

### Validation:
- Entry existence checked before adding to queue
- Queue item ownership verified on all operations
- Status values validated (pending/processing/completed/failed)
- Progress values validated (0-100%, positive bytes, etc.)

## CodeQL Security Scan

✅ **No vulnerabilities detected** in Python or JavaScript code.

## Dependencies Added

```
httpx     # HTTP client for cartel.py
tqdm      # Progress bars for sphaira.py
rich      # TUI framework for send_to_switch.py
pyusb     # USB device communication for USB transfers
```

## Known Limitations

1. **Progress Reporting**: Progress is reported during transfers with real-time updates to the TUI and server.

2. **Single Transfer at a Time**: By design, only one game is transferred at a time to avoid overwhelming the Switch or connection. Additional items wait in the queue.

3. **USB Requirements**: For USB transfers, the Switch must be connected via USB cable and running Sphaira/Awoo installer in USB mode.

4. **Network Requirements**: For FTP transfers (when USB not available), both the PC and Switch must be on the same local network, and Sphaira FTP server must be enabled on port 5000.

5. **USB Library**: On Linux, udev rules may be needed for non-root USB access. On Windows, Zadig driver installation may be required.

## Testing

- ✅ Syntax validation (py_compile)
- ✅ Code linting (ruff)
- ✅ Code review completed
- ✅ Security scan (CodeQL)
- ✅ Client library instantiation test

## Future Enhancements

1. **Retry Logic**: Automatic retry for failed transfers
2. **Bandwidth Limiting**: Configurable transfer speed limits
3. **Multiple Switches**: Support for managing multiple Switch consoles via USB or network
4. **Priority Queue**: Allow users to reorder queue items
5. **Notifications**: Desktop/mobile notifications when transfers complete
6. **Transfer History**: Long-term storage of completed/failed transfers with statistics
7. **MTP Support**: Add MTP protocol support as another transfer method

## Files Modified

### New Files:
- `app/routes/queue.py` - Queue manager routes
- `app/templates/user/game_queue.html` - Queue manager page
- `software/cartel.py` - API client library
- `software/send_to_switch.py` - Client application with TUI
- `software/README.md` - Client documentation

### Modified Files:
- `app/database.py` - Added send_queue collection and methods
- `app/routes/api.py` - Added API endpoints
- `app/main.py` - Registered new routes
- `app/templates/base.html` - Added Game Queue menu item
- `app/templates/search.html` - Added isAuthenticated flag
- `static/js/search.js` - Added Send to Switch button handler
- `static/css/style.css` - Added button styling
- `requirements.txt` - Added httpx, tqdm, rich

## Conclusion

This implementation provides a complete end-to-end solution for sending games from ModdingCartel to Nintendo Switch consoles, with robust queue management, real-time progress tracking, and a user-friendly interface. The architecture is extensible and secure, with proper authentication, authorization, and error handling throughout.
