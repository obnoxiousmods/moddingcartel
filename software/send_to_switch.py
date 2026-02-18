#!/usr/bin/env python3
"""
Send to Switch Client

A client application that polls ModdingCartel for games to send to Nintendo Switch
via Sphaira FTP server. Features a TUI (Text User Interface) for monitoring.
"""

import asyncio
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

import yaml
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Add parent directory to path to import local modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from software.cartel import ModdingCartel
from software.sphaira import SphairaDownloader

# Determine working directory (same as executable or script location)
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    WORKING_DIR = Path(sys.executable).parent
else:
    # Running as script
    WORKING_DIR = Path(__file__).parent

# Configuration and logging in working directory
CONFIG_FILE = WORKING_DIR / "config.yaml"
LOG_FILE = WORKING_DIR / "send_to_switch.log"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

POLL_INTERVAL = 3  # seconds


class SendToSwitchClient:
    """Client for sending games to Switch via Sphaira"""

    def __init__(self, config_path: Path = CONFIG_FILE):
        self.config_path = config_path
        self.config = {}
        self.api_client: Optional[ModdingCartel] = None
        self.sphaira: Optional[SphairaDownloader] = None
        self.running = False
        self.current_task = None
        self.current_progress_percent = 0
        self.stats = {
            "total_sent": 0,
            "total_failed": 0,
            "current_queue_size": 0,
            "last_poll_time": None,
            "status": "Initializing...",
        }
        self.console = Console()

    def load_config(self) -> bool:
        """Load configuration from YAML file"""
        try:
            if self.config_path.exists():
                with open(self.config_path, "r") as f:
                    self.config = yaml.safe_load(f) or {}
                logger.info(f"Configuration loaded from {self.config_path}")
                return True
            else:
                logger.info("No configuration file found")
                return False
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            return False

    def save_config(self):
        """Save configuration to YAML file in working directory"""
        try:
            # WORKING_DIR exists (derived from executable/script location)
            with open(self.config_path, "w") as f:
                yaml.dump(self.config, f, default_flow_style=False)
            logger.info(f"Configuration saved to {self.config_path}")
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")

    def setup_authentication(self):
        """Setup authentication with ModdingCartel"""
        # Check if we have an API key
        if "api_key" in self.config:
            logger.info("Using existing API key")
            self.api_client = ModdingCartel(
                base_url=self.config.get("base_url", "https://swdld.obnoxious.lol"),
                api_key=self.config["api_key"],
            )
            return True

        # Prompt for credentials
        self.console.print("\n[bold cyan]ModdingCartel Authentication[/bold cyan]")
        self.console.print("No API key found. Please login to create one.\n")

        username = self.console.input("[yellow]Username:[/yellow] ").strip()
        password = self.console.input(
            "[yellow]Password:[/yellow] ", password=True
        ).strip()

        if not username or not password:
            self.console.print("[red]Username and password are required[/red]")
            return False

        # Get base URL
        base_url = (
            self.console.input(
                    "[yellow]Server URL:[/yellow] [dim](default: https://swdld.obnoxious.lol)[/dim] "
            ).strip()
            or "https://swdld.obnoxious.lol"
        )

        try:
            self.api_client = ModdingCartel(base_url=base_url)
            result = self.api_client.login(username, password)

            if result.get("success"):
                self.config["api_key"] = result["api_key"]
                self.config["base_url"] = base_url
                self.save_config()
                self.console.print("[green]✓ Authentication successful![/green]")
                logger.info("Authentication successful, API key saved")
                return True
            else:
                self.console.print(f"[red]✗ Login failed: {result.get('error')}[/red]")
                return False

        except Exception as e:
            self.console.print(f"[red]✗ Error during login: {e}[/red]")
            logger.error(f"Login error: {e}")
            return False

    def prompt_for_switch_ip(self) -> Optional[str]:
        """
        Prompt user for Switch IP address.
        Returns IP address if provided, None for auto-scan.
        """
        self.console.print("\n[bold cyan]Switch IP Configuration[/bold cyan]")
        self.console.print("Enter your Switch's IP address, or press Enter to auto-scan.\n")
        
        ip_input = self.console.input(
            "[yellow]Switch IP address:[/yellow] [dim](or press Enter for auto-scan)[/dim] "
        ).strip()
        
        if ip_input:
            logger.info(f"User provided IP address: {ip_input}")
            return ip_input
        else:
            logger.info("User opted for auto-scan")
            return None

    async def verify_switch_connection(self) -> bool:
        """
        Verify if the configured Switch IP is still reachable.
        Returns True if connection is good, False if we need to rescan.
        """
        if not self.sphaira or not self.sphaira.ip_address:
            return False
            
        self.console.print(f"\n[cyan]Verifying connection to {self.sphaira.ip_address}...[/cyan]")
        
        is_valid = await self.sphaira.verify_ip_connection(self.sphaira.ip_address)
        
        if is_valid:
            self.console.print(f"[green]✓ Connection verified![/green]")
            return True
        else:
            self.console.print(f"[yellow]✗ Cannot connect to {self.sphaira.ip_address}[/yellow]")
            return False

    def setup_sphaira(self, ip_address: Optional[str] = None):
        """Setup Sphaira downloader"""
        # Get IP address from config or parameter
        if not ip_address:
            ip_address = self.config.get("switch_ip")

        # Disable debug mode to prevent tqdm output that interferes with TUI
        self.sphaira = SphairaDownloader(ip_address=ip_address, debug=False)
        logger.info(
            f"Sphaira downloader initialized with IP: {ip_address or 'auto-discover'}"
        )

    async def discover_switch(self) -> bool:
        """Discover Switch on the network"""
        try:
            self.stats["status"] = "Discovering Switch on network..."
            logger.info("Starting Switch discovery...")

            found = await self.sphaira.discover_and_connect()

            if found:
                self.config["switch_ip"] = self.sphaira.ip_address
                self.save_config()
                self.stats["status"] = (
                    f"Connected to Switch at {self.sphaira.ip_address}"
                )
                logger.info(f"Switch found at {self.sphaira.ip_address}")
                return True
            else:
                self.stats["status"] = "Switch not found on network"
                logger.warning("Switch not found on network")
                return False

        except Exception as e:
            self.stats["status"] = f"Error during discovery: {e}"
            logger.error(f"Discovery error: {e}")
            return False

    async def process_queue(self, queue=None, tui=None):
        """
        Process the send queue.

        Args:
            queue: Optional pre-fetched queue. If None, will fetch from server.
                   Note: When providing a queue, ensure stats are updated separately.
        """
        try:
            # Get queue from server if not provided
            if queue is None:
                self.stats["status"] = "Fetching queue..."
                queue = self.api_client.get_send_queue()
                # Update stats when fetching queue ourselves
                self.stats["current_queue_size"] = len(queue)
                self.stats["last_poll_time"] = time.time()

            logger.debug(f"Processing queue: {len(queue)} items")

            if not queue:
                self.stats["status"] = "Ready! Start adding games to the queue..."
                if tui:
                    tui.update(self.generate_tui())
                return

            # Process first item in queue
            item = queue[0]
            queue_item_id = item["queue_item_id"]
            entry_name = item["entry_name"]
            entry_source = item["entry_source"]
            entry_size = item.get("entry_size", 0)

            logger.info(f"Processing queue item: {entry_name}")
            self.stats["status"] = f"Sending: {entry_name}"
            self.current_task = entry_name

            if tui:
                tui.update(self.generate_tui())

            # Mark as processing with initial progress
            self.api_client.update_queue_progress(
                queue_item_id=queue_item_id,
                status="processing",
                progress_percent=0,
                bytes_transferred=0,
            )

            # Setup progress tracking
            last_progress_update = time.time()
            progress_update_interval = 2  # Update every 2 seconds

            # Create a custom progress callback
            bytes_transferred = 0
            last_bytes = 0
            last_time = time.time()

            async def report_progress(chunk_size: int):
                nonlocal bytes_transferred, last_bytes, last_time, last_progress_update
                bytes_transferred += chunk_size
                current_time = time.time()

                # Calculate transfer speed
                time_delta = current_time - last_time
                if time_delta > 0:
                    transfer_speed = (bytes_transferred - last_bytes) / time_delta
                else:
                    transfer_speed = 0

                # Calculate progress percentage
                if entry_size > 0:
                    progress_percent = int((bytes_transferred / entry_size) * 100)
                else:
                    progress_percent = 0

                # Update local progress for TUI
                self.current_progress_percent = min(progress_percent, 100)

                if tui:
                    tui.update(self.generate_tui())

                # Report progress every N seconds
                if current_time - last_progress_update >= progress_update_interval:
                    try:
                        self.api_client.update_queue_progress(
                            queue_item_id=queue_item_id,
                            progress_percent=min(progress_percent, 100),
                            bytes_transferred=bytes_transferred,
                            transfer_speed=transfer_speed,
                        )
                        last_progress_update = current_time
                    except Exception as e:
                        error_str = str(e)
                        if "Invalid API Key" in error_str:
                            logger.error(
                                "API key is invalid or revoked. Please re-authenticate."
                            )
                            raise
                        logger.warning(f"Failed to update progress: {e}")
                        raise

                last_bytes = bytes_transferred
                last_time = current_time

            if tui:
                tui.update(self.generate_tui())

            # Check if file is local or HTTP
            try:
                if entry_source.startswith("http://") or entry_source.startswith(
                    "https://"
                ):
                    # Stream from HTTP with progress reporting
                    result = await self.stream_with_progress(
                        entry_source, entry_name, report_progress
                    )
                else:
                    # Upload from local file with progress reporting
                    result = await self.upload_with_progress(
                        entry_name, report_progress
                    )

                # Update status based on result
                if result.get("success"):
                    self.api_client.update_queue_progress(
                        queue_item_id=queue_item_id,
                        status="completed",
                        progress_percent=100,
                        bytes_transferred=result.get("size_bytes", bytes_transferred),
                    )
                    self.stats["total_sent"] += 1
                    self.stats["status"] = f"✓ Completed: {entry_name}"
                    logger.info(f"Successfully sent: {entry_name}")
                else:
                    error = result.get("error", "Unknown error")
                    self.api_client.update_queue_progress(
                        queue_item_id=queue_item_id,
                        status="failed",
                        error_message=error,
                    )
                    self.stats["total_failed"] += 1
                    self.stats["status"] = f"✗ Failed: {entry_name} - {error}"
                    logger.error(f"Failed to send {entry_name}: {error}")

            except Exception as e:
                error_msg = str(e)
                # Check if it's an invalid API key error
                if "Invalid API Key" in error_msg:
                    logger.error(
                        "API key is invalid or revoked. Please re-authenticate."
                    )
                    raise
                self.api_client.update_queue_progress(
                    queue_item_id=queue_item_id,
                    status="failed",
                    error_message=error_msg,
                )
                self.stats["total_failed"] += 1
                self.stats["status"] = f"✗ Failed: {entry_name} - {error_msg}"
                logger.error(f"Failed to send {entry_name}: {e}", exc_info=True)

            self.current_task = None
            self.current_progress_percent = 0

            if tui:
                tui.update(self.generate_tui())

        except Exception as e:
            error_str = str(e)
            # Check if it's an invalid API key error
            if "Invalid API Key" in error_str:
                self.stats["status"] = "Invalid API Key - Exiting..."
                logger.error(
                    "API key is invalid or revoked. Clearing config and exiting."
                )
                # Clear the API key from config
                if "api_key" in self.config:
                    del self.config["api_key"]
                    self.save_config()
                # Stop the client
                self.running = False
                raise
            self.stats["status"] = f"Error processing queue: {e}"
            logger.error(f"Queue processing error: {e}", exc_info=True)

        if tui:
            tui.update(self.generate_tui())

    async def stream_with_progress(self, url: str, filename: str, progress_callback):
        """Stream HTTP game with progress reporting"""
        # Pass API key in Authorization header for authenticated downloads
        headers = {}
        if self.config.get("api_key"):
            headers["Authorization"] = f"Bearer {self.config['api_key']}"

        # Set status to indicate streaming
        self.stats["status"] = f"Installing: {filename}"

        result = await self.sphaira.streamHttpGame(
            url=url,
            filename=filename,
            headers=headers if headers else None,
            progress_callback=progress_callback,
            method="auto",  # Auto-detect USB or FTP
        )
        return result

    async def upload_with_progress(self, filename: str, progress_callback):
        """Upload local game with progress reporting"""
        result = await self.sphaira.uploadLocalGame(
            fileName=filename,
            progress_callback=progress_callback,
            method="auto",  # Auto-detect USB or FTP
        )
        return result

    def generate_tui(self) -> Layout:
        """Generate the TUI layout"""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=5),
        )

        # Header
        header_text = Text("moddingcartel", style="bold cyan", justify="center")
        layout["header"].update(Panel(header_text))

        # Body - Stats and Status
        stats_table = Table(show_header=False, box=None, padding=(0, 1))
        stats_table.add_column("Key", style="cyan")
        stats_table.add_column("Value", style="white")

        stats_table.add_row("Status:", self.stats["status"])
        stats_table.add_row("Queue Size:", str(self.stats["current_queue_size"]))
        stats_table.add_row("Total Sent:", str(self.stats["total_sent"]))
        stats_table.add_row("Total Failed:", str(self.stats["total_failed"]))

        if self.stats["last_poll_time"]:
            elapsed = int(time.time() - self.stats["last_poll_time"])
            stats_table.add_row("Last Poll:", f"{elapsed}s ago")

        if self.current_task:
            stats_table.add_row("Current Task:", self.current_task)
            stats_table.add_row("Progress:", f"{self.current_progress_percent}%")

        if self.sphaira and self.sphaira.ip_address:
            stats_table.add_row("Switch IP:", self.sphaira.ip_address)

        layout["body"].update(
            Panel(stats_table, title="Statistics", border_style="green")
        )

        # Footer - Controls
        footer_text = Text.from_markup(
            "[yellow]Press Ctrl+C to stop[/yellow]",
            justify="center",
        )
        layout["footer"].update(Panel(footer_text, border_style="yellow"))

        return layout

    async def update_queue_stats(self):
        """
        Fetch queue from API and update statistics.

        Returns:
            List of queue items for subsequent processing, or empty list on error.
        """
        try:
            # Get queue from server
            queue = self.api_client.get_send_queue()
            self.stats["current_queue_size"] = len(queue)
            self.stats["last_poll_time"] = time.time()
            logger.debug(f"Queue stats updated: {len(queue)} items")
            return queue
        except Exception as e:
            logger.error(f"Error updating queue stats: {e}")
            self.stats["status"] = f"Error fetching queue: {e}"
            return []

    async def run_loop(self):
        """Main polling loop"""
        self.running = True

        try:
            with Live(self.generate_tui(), refresh_per_second=1, screen=True) as tuiVar:
                while self.running:
                    # Update queue stats and get queue
                    queue = await self.update_queue_stats()

                    # Update display with fresh stats
                    tuiVar.update(self.generate_tui())

                    # Process queue (pass queue to avoid duplicate fetch)
                    await self.process_queue(queue, tui=tuiVar)

                    # Wait for next poll
                    await asyncio.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
            self.stats["status"] = "Shutting down..."
        finally:
            self.running = False

    async def run(self):
        """Run the client"""
        try:
            # Load configuration
            self.load_config()

            # Setup authentication
            if not self.setup_authentication():
                return

            # Prompt user for Switch IP or auto-scan
            user_ip = self.prompt_for_switch_ip()
            
            # Setup Sphaira with user-provided IP or from config
            if user_ip:
                self.setup_sphaira(user_ip)
            else:
                self.setup_sphaira()

            # Try USB detection first
            self.console.print("\n[cyan]Checking for USB connection...[/cyan]")
            if await self.sphaira.detect_usb_switch():
                self.console.print(
                    "[green]✓ Switch detected via USB! USB transfers will be prioritized.[/green]"
                )
            else:
                self.console.print(
                    "[yellow]No USB connection detected. Will use network (FTP).[/yellow]"
                )

                # If we have a configured IP, verify it's still good
                if self.sphaira.ip_address:
                    if not await self.verify_switch_connection():
                        self.console.print(
                            "[yellow]Saved IP is no longer reachable. Starting network scan...[/yellow]"
                        )
                        # Clear the saved IP so we scan
                        self.sphaira.ip_address = None
                        if "switch_ip" in self.config:
                            del self.config["switch_ip"]
                            self.save_config()
                
                # Discover Switch if no valid IP
                if not self.sphaira.ip_address:
                    self.console.print(
                        "\n[yellow]Discovering Switch on network...[/yellow]"
                    )
                    if not await self.discover_switch():
                        self.console.print(
                            "[red]Failed to discover Switch. Please check your network connection or USB connection.[/red]"
                        )
                        return

            self.console.print(
                "\n[green]✓ Setup complete! Starting polling loop...[/green]"
            )
            self.console.print(f"[dim]Polling every {POLL_INTERVAL} seconds...[/dim]\n")

            # Run main loop
            await self.run_loop()

        except Exception as e:
            logger.error(f"Error running client: {e}", exc_info=True)
            self.console.print(f"[red]Error: {e}[/red]")
        finally:
            # Cleanup
            if self.api_client:
                self.api_client.close()


async def main():
    """Main entry point"""
    try:
        client = SendToSwitchClient()
        await client.run()
    except Exception as e:
        console = Console()
        console.print(f"\n[bold red]Fatal Error:[/bold red] {e}")
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        
        # Keep window open when running as exe
        if getattr(sys, 'frozen', False):
            console.print("\n[yellow]Press Enter to exit...[/yellow]")
            input()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        console = Console()
        console.print(f"\n[bold red]Unhandled Exception:[/bold red] {e}")
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        
        # Keep window open when running as exe
        if getattr(sys, 'frozen', False):
            console.print("\n[yellow]Press Enter to exit...[/yellow]")
            input()
