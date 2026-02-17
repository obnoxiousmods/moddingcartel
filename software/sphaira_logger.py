"""
Comprehensive logging module for Sphaira downloader with detailed USB debugging.
Provides both console and file logging with rotation.
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime


def setup_logger(name="sphaira", log_dir=None, debug=True):
    """
    Setup comprehensive logging with file rotation and console output.
    
    Args:
        name: Logger name
        log_dir: Directory for log files (default: ~/.moddingcartel/logs)
        debug: Enable debug level logging
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Set log level
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    
    # Create log directory
    if log_dir is None:
        log_dir = Path.home() / ".moddingcartel" / "logs"
    else:
        log_dir = Path(log_dir)
    
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s:%(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # File handler - Main log with rotation (10MB per file, keep 5 files)
    main_log_file = log_dir / f"sphaira_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = RotatingFileHandler(
        main_log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    logger.addHandler(file_handler)
    
    # File handler - USB-specific debug log
    usb_log_file = log_dir / f"usb_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    usb_handler = RotatingFileHandler(
        usb_log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=3,
        encoding='utf-8'
    )
    usb_handler.setLevel(logging.DEBUG)
    usb_handler.setFormatter(detailed_formatter)
    usb_handler.addFilter(USBLogFilter())
    logger.addHandler(usb_handler)
    
    # Console handler - Less verbose
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO if debug else logging.WARNING)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # Log initialization
    logger.info("="*80)
    logger.info(f"Sphaira Logger initialized - Log directory: {log_dir}")
    logger.info(f"Main log: {main_log_file}")
    logger.info(f"USB debug log: {usb_log_file}")
    logger.info("="*80)
    
    return logger


class USBLogFilter(logging.Filter):
    """Filter to only allow USB-related log messages."""
    
    def filter(self, record):
        msg = record.getMessage().lower()
        func = record.funcName.lower()
        return 'usb' in msg or 'usb' in func or record.funcName.startswith('_usb_')


def log_hex_dump(logger, data: bytes, prefix="", max_bytes=256):
    """
    Log a hex dump of binary data for debugging.
    
    Args:
        logger: Logger instance
        data: Binary data to dump
        prefix: Prefix for log message
        max_bytes: Maximum bytes to dump (truncate if longer)
    """
    if not logger.isEnabledFor(logging.DEBUG):
        return
    
    data_len = len(data)
    data_to_dump = data[:max_bytes] if data_len > max_bytes else data
    truncated = " (truncated)" if data_len > max_bytes else ""
    
    hex_str = data_to_dump.hex(' ', 2)
    logger.debug(f"{prefix}Hex dump ({data_len} bytes{truncated}): {hex_str}")
    
    # Also log as ASCII where printable
    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data_to_dump)
    logger.debug(f"{prefix}ASCII: {ascii_str}")


def log_usb_packet(logger, direction, command, payload, extra_info=""):
    """
    Log detailed information about a USB packet.
    
    Args:
        logger: Logger instance
        direction: "SEND" or "RECV"
        command: Command code
        payload: Packet payload
        extra_info: Additional information to log
    """
    logger.debug(f"USB {direction} - Command: {command}, Payload size: {len(payload)} bytes {extra_info}")
    if len(payload) > 0:
        log_hex_dump(logger, payload, f"USB {direction} payload - ", max_bytes=128)


def log_http_request(logger, method, url, headers=None, cookies=None):
    """
    Log HTTP request details.
    
    Args:
        logger: Logger instance
        method: HTTP method
        url: Request URL
        headers: Request headers
        cookies: Request cookies
    """
    logger.info(f"HTTP {method} {url}")
    if headers:
        logger.debug(f"HTTP headers: {headers}")
    if cookies:
        logger.debug(f"HTTP cookies: {cookies}")


def log_http_response(logger, status_code, headers=None, size=None):
    """
    Log HTTP response details.
    
    Args:
        logger: Logger instance
        status_code: HTTP status code
        headers: Response headers
        size: Response content size
    """
    logger.info(f"HTTP response: {status_code}" + (f" ({size} bytes)" if size else ""))
    if headers:
        logger.debug(f"HTTP response headers: {headers}")
