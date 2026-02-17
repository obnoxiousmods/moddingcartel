# Send to Switch Client

A Python client application for sending Nintendo Switch games from ModdingCartel to your Switch console via Sphaira's FTP server.

## Features

- **Automatic Queue Management**: Poll the ModdingCartel server for games to send
- **Sequential FTP Transfers**: Queue system ensures games are sent one at a time
- **Switch Auto-Discovery**: Automatically finds your Switch on the local network
- **TUI Interface**: Rich text-based user interface for monitoring
- **Persistent Configuration**: API key and settings saved in YAML config
- **Error Handling**: Automatic retry and error reporting

## Requirements

- Python 3.8 or higher
- Network access to both ModdingCartel server and Nintendo Switch
- Nintendo Switch running Sphaira with FTP enabled
- ModdingCartel account

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the client:
```bash
python software/send_to_switch.py
```

## First Time Setup

When you run the client for the first time, you'll be prompted to:

1. **Login**: Enter your ModdingCartel username and password
   - The client will automatically create an API key for you
   - This key is saved securely in `~/.config/send_to_switch/config.yaml`

2. **Server URL**: Enter the ModdingCartel server URL
   - Default: `http://localhost:8000`
   - Or use a public URL like `https://moddingcartel.com`

3. **Switch Discovery**: The client will scan your local network for your Switch
   - Make sure your Switch is running Sphaira with FTP enabled
   - Make sure your Switch is on the same network

## Usage

### Sending Games to Your Switch

1. **From the Website**:
   - Browse or search for games on ModdingCartel
   - Click the "📤 Send to Switch" button on any game
   - The game will be added to your queue

2. **Client Will Automatically**:
   - Poll the server every 3 seconds for new games in your queue
   - Download and stream games directly to your Switch via FTP
   - Update the queue status (processing → completed/failed)
   - Move on to the next game in the queue

### TUI Interface

The TUI shows:
- **Status**: Current operation and connection status
- **Queue Size**: Number of games waiting to be sent
- **Statistics**: Total sent, total failed
- **Current Task**: Game currently being transferred
- **Switch IP**: IP address of your connected Switch

### Stopping the Client

Press `Ctrl+C` to gracefully stop the client.

## Configuration

Configuration is stored in `~/.config/send_to_switch/config.yaml`:

```yaml
api_key: your_api_key_here
base_url: http://localhost:8000
switch_ip: 192.168.1.100  # Auto-discovered on first run
```

## Troubleshooting

### Switch Not Found
- Ensure Sphaira is running on your Switch
- Ensure FTP server is enabled in Sphaira settings
- Check that your Switch and PC are on the same network
- Check your firewall settings

### Login Failed
- Verify your username and password
- Check the server URL is correct
- Ensure the ModdingCartel server is running

### Transfer Failed
- Check network connection
- Ensure Switch has enough storage space
- Check Sphaira logs on Switch for errors

## API Documentation

The client uses the following ModdingCartel API endpoints:

- `POST /api/auth/login` - Login and get/create API key
- `GET /api/send-queue` - Get pending games in queue
- `POST /api/send-queue/update` - Update queue item status

## Architecture

### Components

1. **ModdingCartel Class** (`software/cartel.py`)
   - HTTP client for ModdingCartel API
   - Handles authentication and queue management

2. **SphairaDownloader Class** (`software/sphaira.py`)
   - FTP client for transferring games to Switch
   - Network discovery for finding Switch
   - Stream downloading from HTTP URLs

3. **SendToSwitchClient Class** (`software/send_to_switch.py`)
   - Main application logic
   - TUI interface using Rich
   - Configuration management
   - Queue processing loop

### Flow

```
User clicks "Send to Switch" on website
    ↓
Game added to user's queue in database
    ↓
Client polls /api/send-queue every 3 seconds
    ↓
Client retrieves game from queue
    ↓
Client marks game as "processing"
    ↓
Client transfers game via FTP to Switch
    ↓
Client marks game as "completed" or "failed"
    ↓
Process next game in queue
```

## Development

### Running Tests

```bash
python /tmp/test_send_to_switch.py
```

### Logging

Logs are written to `send_to_switch.log` in the current directory.

## License

See main repository LICENSE file.
