#!/usr/bin/env python3
"""
Example demonstrating the comprehensive logging functionality
Run this to see logs being created in ~/.moddingcartel/logs/
"""
import asyncio
import sys
from pathlib import Path

# Add software directory to path
sys.path.insert(0, str(Path(__file__).parent))

from sphaira import SphairaDownloader


async def example_usb_detection():
    """Example: USB device detection with logging"""
    print("="*80)
    print("Example 1: USB Device Detection")
    print("="*80)

    downloader = SphairaDownloader(debug=True)

    print("\nAttempting USB device detection...")
    print("(Check logs at ~/.moddingcartel/logs/ for detailed output)")

    usb_available = await downloader.detect_usb_switch()

    if usb_available:
        print("✓ USB device detected!")
        print("  See USB debug log for detailed device information")
    else:
        print("✗ USB device not detected")
        print("  This is normal if no Switch is connected")
        print("  Check main log for detection attempts")

    return downloader


async def example_network_discovery():
    """Example: Network discovery with logging"""
    print("\n" + "="*80)
    print("Example 2: Network Discovery")
    print("="*80)

    downloader = SphairaDownloader(debug=True)

    print("\nScanning local network for Sphaira...")
    print("(This will scan 192.168.0-15.1-254)")
    print("(Check logs for scan progress and results)")

    # Scan smaller range for demo
    found = await downloader.discover_and_connect(
        third_octets=range(0, 2),
        fourth_octets=range(1, 10),
        max_concurrent=20
    )

    if found:
        print(f"✓ Sphaira found at {downloader.ip_address}")
    else:
        print("✗ Sphaira not found")
        print("  This is normal if Sphaira is not running on the network")

    return downloader


async def example_log_inspection():
    """Example: Show log files created"""
    print("\n" + "="*80)
    print("Example 3: Log Files")
    print("="*80)

    log_dir = Path.home() / ".moddingcartel" / "logs"

    if log_dir.exists():
        log_files = sorted(log_dir.glob("*.log"))
        print(f"\nLog files in {log_dir}:")
        for log_file in log_files:
            size = log_file.stat().st_size
            print(f"  - {log_file.name}: {size:,} bytes")

        if log_files:
            # Show last few lines of main log
            main_logs = [f for f in log_files if "sphaira_" in f.name and "usb_debug" not in f.name]
            if main_logs:
                print(f"\nLast 10 lines of {main_logs[-1].name}:")
                print("-" * 80)
                with open(main_logs[-1], 'r') as f:
                    lines = f.readlines()
                    for line in lines[-10:]:
                        print(line.rstrip())
                print("-" * 80)

            # Show USB debug log info
            usb_logs = [f for f in log_files if "usb_debug" in f.name]
            if usb_logs:
                print(f"\nUSB Debug log: {usb_logs[-1].name}")
                print(f"Size: {usb_logs[-1].stat().st_size:,} bytes")
                print("This file contains detailed USB packet information")
    else:
        print(f"\nLog directory not found: {log_dir}")


async def example_logging_overview():
    """Example: Overview of what gets logged"""
    print("\n" + "="*80)
    print("Example 4: What Gets Logged")
    print("="*80)

    print("""
The Sphaira logger captures:

1. USB Operations:
   - Device detection (VID/PID, manufacturer, serial)
   - Endpoint configuration (IN/OUT addresses)
   - Every packet sent/received with hex dumps
   - Handshake requests and responses
   - Transfer progress (chunks, bytes, speed)

2. HTTP Operations:
   - Request URLs, methods, headers, cookies
   - Response status codes and headers
   - Streaming progress
   - Error details with stack traces

3. FTP Operations:
   - Connection details
   - Upload progress
   - Transfer statistics

4. Network Discovery:
   - IP ranges scanned
   - Devices found
   - Connection verification

All logs include:
   - Timestamp (millisecond precision)
   - Log level (DEBUG, INFO, WARNING, ERROR)
   - Module and function name
   - Line number
   - Detailed message

Example log entry:
2026-02-17 06:42:31.266 [INFO] sphaira:__init__:44 - SphairaDownloader initialized - IP: 192.168.1.100

Log files rotate at 10MB to prevent disk space issues.
    """)


async def main():
    """Run all examples"""
    print("\n" + "="*80)
    print("SPHAIRA COMPREHENSIVE LOGGING - EXAMPLES")
    print("="*80)

    # Example 4 first (overview)
    await example_logging_overview()

    # Example 1: USB detection
    downloader1 = await example_usb_detection()

    # Example 2: Network discovery (optional, can be slow)
    # Uncomment to test:
    # await example_network_discovery()

    # Example 3: Log inspection
    await example_log_inspection()

    print("\n" + "="*80)
    print("Examples complete!")
    print("="*80)
    print(f"\nCheck logs at: {Path.home() / '.moddingcartel' / 'logs'}")
    print("\nTo view logs:")
    print(f"  Main log:      tail -f ~/.moddingcartel/logs/sphaira_*.log")
    print(f"  USB debug log: tail -f ~/.moddingcartel/logs/usb_debug_*.log")
    print("\nTo search logs:")
    print(f"  USB errors:    grep ERROR ~/.moddingcartel/logs/usb_debug_*.log")
    print(f"  Transfer info: grep 'Average speed' ~/.moddingcartel/logs/sphaira_*.log")


if __name__ == "__main__":
    asyncio.run(main())
