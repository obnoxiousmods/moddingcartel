# Send to Switch Client

A Python client application for sending Nintendo Switch games from ModdingCartel to your Switch console via Sphaira's FTP or USB connection.

## Features

- **USB and FTP Transfer Support**: Automatic detection and preference for faster USB transfers
- **Automatic Queue Management**: Poll the ModdingCartel server for games to send
- **Sequential Transfers**: Queue system ensures games are sent one at a time
- **Switch Auto-Discovery**: Automatically finds your Switch via USB or local network
- **TUI Interface**: Rich text-based user interface for monitoring
- **Persistent Configuration**: API key and settings saved in YAML config
- **Error Handling**: Automatic retry and error reporting

## Requirements

- Python 3.8 or higher
- Network access to ModdingCartel server
- Nintendo Switch running Sphaira with FTP enabled (for network transfers) or USB mode (for USB transfers)
- ModdingCartel account
- For USB transfers: pyusb library and libusb installed

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. For USB support on Linux, you may need to add udev rules:
```bash
# Create udev rules file (using your preferred text editor, e.g., nano or vim)
sudo nano /etc/udev/rules.d/99-NS.rules

# Add this line:
SUBSYSTEM=="usb", ATTRS{idVendor}=="057e", ATTRS{idProduct}=="3000", MODE="0666"

# Reload udev rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```

3. Run the client:
```bash
python software/send_to_switch.py
```

## First Time Setup

When you run the client for the first time, you'll be prompted to:

1. **Login**: Enter your ModdingCartel username and password
   - The client will automatically create an API key for you
   - This key is saved securely in `~/.config/send_to_switch/config.yaml`

2. **Server URL**: Enter the ModdingCartel server URL
   - Default: `http://127.0.0.1:6069`
   - Or use a public URL like `https://moddingcartel.com`

3. **Connection Detection**: The client will automatically:
   - First, try to detect Switch via USB (faster)
   - If USB not available, scan your local network for Switch via FTP
   - Make sure your Switch is running Sphaira with USB mode or FTP enabled
   - Make sure your Switch is on the same network (for FTP mode)

## Usage

### Sending Games to Your Switch

1. **From the Website**:
   - Browse or search for games on ModdingCartel
   - Click the "📤 Send to Switch" button on any game
   - The game will be added to your queue

2. **Client Will Automatically**:
   - Poll the server every 3 seconds for new games in your queue
   - Detect the best transfer method (USB preferred, FTP fallback)
   - Download and stream games directly to your Switch
   - Update the queue status (processing → completed/failed)
   - Move on to the next game in the queue

### Transfer Methods

The client supports two transfer methods:

1. **USB (Recommended - Faster)**
   - Requires Switch connected via USB cable
   - Switch must be in Sphaira/Awoo installer USB mode
   - Uses Tinfoil/Awoo protocol
   - Significantly faster than network transfers
   - Automatically detected and prioritized

2. **FTP (Network - Fallback)**
   - Requires Switch and PC on same network
   - Sphaira FTP server must be enabled
   - Used when USB is not available
   - Still provides good transfer speeds

### TUI Interface

The TUI shows:
- **Status**: Current operation and connection status (USB or FTP)
- **Queue Size**: Number of games waiting to be sent
- **Statistics**: Total sent, total failed
- **Current Task**: Game currently being transferred
- **Switch IP**: IP address of your connected Switch (FTP mode)

### Stopping the Client

Press `Ctrl+C` to gracefully stop the client.

## Configuration

Configuration is stored in `~/.config/send_to_switch/config.yaml`:

```yaml
api_key: your_api_key_here
base_url: http://127.0.0.1:6069
switch_ip: 192.168.1.100  # Auto-discovered on first run (for FTP mode)
```

## Troubleshooting

### Switch Not Found (USB)
- Ensure Switch is connected via USB cable
- Ensure Switch is running Sphaira/Awoo installer
- On Linux, check udev rules are properly configured
- Try running with sudo if permissions are an issue

### Switch Not Found (FTP)
- Ensure Sphaira is running on your Switch
- Ensure FTP server is enabled in Sphaira settings
- Check that your Switch and PC are on the same network
- Check your firewall settings

### Login Failed
- Verify your username and password
- Check the server URL is correct
- Ensure the ModdingCartel server is running

### Transfer Failed
- Check network connection (for FTP mode)
- Check USB connection (for USB mode)
- Ensure Switch has enough storage space
- Check Sphaira logs on Switch for errors

### USB Library Not Available
- Install pyusb: `pip install pyusb`
- Install libusb:
  - Linux: `sudo apt install libusb-1.0-0`
  - macOS: `brew install libusb`
  - Windows: Drivers installed automatically via Zadig

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
   - USB client using Tinfoil/Awoo protocol (fast)
   - FTP client for network transfers (fallback)
   - Network discovery for finding Switch
   - USB device detection
   - Stream downloading from HTTP URLs

3. **SendToSwitchClient Class** (`software/send_to_switch.py`)
   - Main application logic
   - TUI interface using Rich
   - Configuration management
   - Queue processing loop
   - Automatic USB/FTP detection

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
Client detects connection type (USB preferred, FTP fallback)
    ↓
Client marks game as "processing"
    ↓
Client transfers game via USB or FTP to Switch
    ↓
Client marks game as "completed" or "failed"
    ↓
Process next game in queue
```

## USB Protocol

The USB implementation uses the Tinfoil/Awoo protocol, which is compatible with:
- Sphaira (Nintendo Switch homebrew)
- Awoo Installer
- Tinfoil
- ns-usbloader (PC tool)

The protocol uses USB endpoints with the following packet structure:
- Magic: `0x12121212` (4 bytes)
- Command: 4 bytes (little endian)
- Size: 8 bytes (little endian)
- ThreadId: 4 bytes
- PacketIndex: 2 bytes
- PacketCount: 2 bytes
- Timestamp: 8 bytes
- Payload: variable length

## Development

### Logging

Logs are written to `send_to_switch.log` in the current directory.

## License

See main repository LICENSE file.
