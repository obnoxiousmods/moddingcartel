# Sphaira USB Logging Documentation

## Overview

The Sphaira downloader now includes comprehensive logging functionality to help debug USB transfers, HTTP streaming, and FTP operations. All logs are written to disk with detailed information about every operation.

## Log Files Location

By default, logs are stored in: `~/.moddingcartel/logs/`

Log files include:
- `sphaira_YYYYMMDD.log` - Main log file with all operations
- `usb_debug_YYYYMMDD_HHMMSS.log` - USB-specific debug log with packet details

## Log Rotation

- Main log: 10MB per file, keeps last 5 files
- USB debug log: 10MB per file, keeps last 3 files

## What Gets Logged

### USB Operations

#### Device Detection
```
- USB device search (VID:0x057E, PID:0x3000)
- Device manufacturer, product, serial number
- USB configuration details
- Endpoint addresses and properties (IN/OUT)
- Device reset status
```

#### Packet Send/Receive
```
- Command codes
- Payload sizes
- Hex dumps of packet headers
- Hex dumps of payloads (first 128-256 bytes)
- ASCII representation of data
- Timestamp for each operation
- Timeout values
```

#### Transfer Progress
```
- Chunk counts and sizes
- Bytes transferred (every 50-100 chunks)
- Transfer completion status
- Performance metrics:
  - Total bytes transferred
  - Elapsed time
  - Average transfer speed (MiB/s)
```

#### Handshakes
```
- Install request details
- Acknowledgment responses
- Command codes and responses
- Handshake success/failure
```

### HTTP Operations

#### Requests
```
- HTTP method (HEAD, GET)
- Full URL
- Headers (if provided)
- Cookies (if provided)
- Proxy settings (if used)
- Connect and read timeouts
```

#### Responses
```
- Status codes
- Response headers (including Content-Length)
- Content size
- Error details for failed requests
```

#### Streaming
```
- Chunk processing (every 100th chunk logged)
- Large chunk warnings
- Stream completion status
```

### FTP Operations

```
- Connection details (host, port)
- Install folder verification
- Upload destination
- Transfer progress
- Completion statistics
```

### Network Discovery

```
- Scan range and parameters
- Number of probes attempted
- Found IP addresses
- Discovery duration
- Connection verification
```

## Using the Logger

### Basic Usage

```python
from sphaira import SphairaDownloader

# Logger is automatically initialized
downloader = SphairaDownloader(
    ip_address="192.168.1.100",
    install_folder="install:",
    debug=True,  # Enable detailed console output
    log_dir="/path/to/logs"  # Optional: custom log directory
)
```

### Custom Log Directory

```python
# Use custom directory
downloader = SphairaDownloader(log_dir="/var/log/sphaira")

# Default is ~/.moddingcartel/logs/
downloader = SphairaDownloader()  # Uses default
```

### Console Output

When `debug=True`:
- INFO level messages go to console
- DEBUG level messages go to file only

When `debug=False`:
- Only WARNING and ERROR messages go to console
- All levels go to file

## Log Format

### Main Log Format
```
YYYY-MM-DD HH:MM:SS.mmm [LEVEL] module:function:line - message
```

Example:
```
2026-02-17 06:42:31.266 [INFO] sphaira:__init__:44 - SphairaDownloader initialized - IP: 192.168.1.100, Install folder: install:, Debug: True
```

### USB Debug Log
Contains only USB-related messages with the same detailed format.

## Performance Impact

- Logging is asynchronous where possible
- File I/O is buffered
- Console output is minimal in non-debug mode
- No significant performance impact on transfers

## Debugging USB Issues

To debug USB transfer issues:

1. Enable debug mode:
   ```python
   downloader = SphairaDownloader(debug=True)
   ```

2. Check the USB debug log for:
   - Device detection failures
   - Endpoint configuration issues
   - Packet send/receive errors
   - Handshake failures
   - Transfer interruptions

3. Look for these error patterns:
   ```
   "USB device not initialized"
   "Invalid magic in USB packet"
   "USB handshake failed"
   "Failed to send USB data chunk"
   ```

4. Review hex dumps to verify:
   - Packet header format (magic: 0x12121212)
   - Command codes (1=handshake, 2=data, 3=complete)
   - Payload sizes match expected values

## Example Log Output

### Successful USB Transfer
```
2026-02-17 06:42:46.301 [INFO] sphaira:detect_usb_switch:48 - Starting USB Switch detection...
2026-02-17 06:42:46.302 [INFO] sphaira:detect_usb_switch:67 - Switch found - VID:0x057E, PID:0x3000
2026-02-17 06:42:46.303 [INFO] sphaira:detect_usb_switch:89 - USB endpoints found - OUT: 0x01, IN: 0x81
2026-02-17 06:42:46.304 [INFO] sphaira:_usb_send_packet:144 - USB packet sent successfully - Command: 1, Total size: 50 bytes
2026-02-17 06:42:46.305 [INFO] sphaira:_usb_recv_packet:172 - USB packet received successfully - Command: 1, Total size: 34 bytes
2026-02-17 06:42:46.306 [INFO] sphaira:_usb_stream_http:576 - USB stream transfer completed successfully!
```

### USB Error
```
2026-02-17 06:42:46.301 [ERROR] sphaira:_usb_send_packet:141 - USB send packet failed: USBError - [Errno 19] No such device
2026-02-17 06:42:46.302 [ERROR] sphaira:_usb_stream_http:455 - Failed to send USB handshake: USBError - [Errno 19] No such device
```

## Troubleshooting

### No logs created
- Check that the log directory exists and is writable
- Verify permissions on `~/.moddingcartel/logs/`
- Check disk space

### USB debug log empty
- Ensure you're performing USB operations (not just FTP)
- Check that USB device detection was attempted
- Verify pyusb is installed

### Logs too large
- Logs rotate automatically at 10MB
- Old log files are automatically cleaned up
- Configure rotation size if needed by modifying `sphaira_logger.py`

## Advanced Usage

### Accessing the Logger Directly

```python
downloader = SphairaDownloader()
downloader.logger.info("Custom log message")
downloader.logger.debug("Detailed debug info")
downloader.logger.error("Error information")
```

### Log Analysis

Use standard tools to analyze logs:
```bash
# View recent USB errors
grep ERROR ~/.moddingcartel/logs/usb_debug_*.log

# Monitor logs in real-time
tail -f ~/.moddingcartel/logs/sphaira_*.log

# Count USB packets sent
grep "USB SEND" ~/.moddingcartel/logs/usb_debug_*.log | wc -l

# Find transfer speeds
grep "Average speed" ~/.moddingcartel/logs/sphaira_*.log
```

## Security Considerations

- Logs may contain URLs and IP addresses
- Cookies and sensitive headers are logged (be careful with API keys)
- Hex dumps show actual data being transferred
- Logs are stored locally only
- Consider clearing logs periodically if privacy is a concern

## Support

If experiencing issues with USB transfers:

1. Enable debug mode
2. Reproduce the issue
3. Collect the log files from `~/.moddingcartel/logs/`
4. Share relevant portions with support (redact sensitive data)
5. Include the USB debug log for USB-specific issues
