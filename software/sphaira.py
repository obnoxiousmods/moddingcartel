import asyncio
import os
import time
from typing import Optional

import aiofiles
import aioftp
import crc32c
import httpx
from sphaira_logger import (
    log_http_request,
    log_http_response,
    setup_logger,
)
from tqdm import tqdm

try:
    import usb.core
    import usb.util
    from usb_common_x import (
        CMD_OPEN,
        CMD_QUIT,
        FLAG_NONE,
        FLAG_STREAM,
        RESULT_ERROR,
        RESULT_OK,
        Usb,
    )

    USB_AVAILABLE = True
except ImportError:
    USB_AVAILABLE = False


# Constants
USB_CHUNK_SIZE = 1024 * 1024  # 1MB chunks for USB transfers
FTP_CHUNK_SIZE = 1024 * 1024  # 1MB chunks for FTP transfers


class SphairaDownloader:
    def __init__(
        self, ip_address=None, install_folder="install:", debug=True, log_dir=None
    ):
        self.ip_address = ip_address
        self.install_folder = install_folder
        self.debug = debug
        self.usb_conn = None  # Will hold Usb instance from usb_common_x.py

        # Setup comprehensive logging
        self.logger = setup_logger("sphaira", log_dir=log_dir, debug=debug)
        self.logger.info(
            f"SphairaDownloader initialized - IP: {ip_address}, Install folder: {install_folder}, Debug: {debug}"
        )

    async def detect_usb_switch(self) -> bool:
        """
        Detect Nintendo Switch connected via USB using Sphaira protocol.
        Returns True if Switch is detected and USB connection is configured.
        """
        self.logger.info("Starting USB Switch detection using Sphaira protocol...")

        if not USB_AVAILABLE:
            self.logger.warning(
                "pyusb or usb_common_x not available - USB support disabled"
            )
            if self.debug:
                tqdm.write("pyusb not available - USB support disabled")
            return False

        def _detect():
            try:
                self.logger.debug("Creating Usb connection instance...")
                usb_conn = Usb()

                self.logger.debug(
                    "Waiting for Switch to connect (VID:0x057E, PID:0x3000)..."
                )
                # This will wait for the Switch and configure endpoints
                usb_conn.wait_for_connect()

                self.logger.info(
                    "✓ Switch detected and configured via USB (Sphaira protocol)"
                )
                if self.debug:
                    tqdm.write("✓ Switch detected via USB (Sphaira protocol)")

                # Store the USB connection instance
                self.usb_conn = usb_conn
                return True

            except Exception as e:
                self.logger.error(
                    f"USB detection error: {type(e).__name__} - {e}", exc_info=True
                )
                if self.debug:
                    tqdm.write(f"USB detection error: {e}")
                return False

        result = await asyncio.get_event_loop().run_in_executor(None, _detect)
        self.logger.info(f"USB detection result: {result}")
        return result

    async def discover_and_connect(
        self,
        third_octets=range(0, 16),
        fourth_octets=range(1, 255),
        port=5000,
        max_concurrent=350,
        connect_timeout=0.20,
        stat_timeout=1.5,
    ) -> bool:
        """
        Fast concurrent scan for Sphaira → sets self.ip_address when found
        Returns True if found and verified, False otherwise
        """
        self.logger.info(
            f"Starting network discovery - Port: {port}, Max concurrent: {max_concurrent}"
        )
        self.logger.debug(
            f"Scan range: 192.168.{min(third_octets)}-{max(third_octets)}.{min(fourth_octets)}-{max(fourth_octets)}"
        )

        if self.ip_address:
            self.logger.info(f"Already have IP: {self.ip_address} — skipping discovery")
            if self.debug:
                tqdm.write(f"Already have IP: {self.ip_address} — skipping discovery")
            return True

        semaphore = asyncio.Semaphore(max_concurrent)
        found_event = asyncio.Event()
        found_ip = None
        probes_attempted = 0

        async def probe(ip: str):
            nonlocal found_ip, probes_attempted
            if found_event.is_set():
                return

            async with semaphore:
                probes_attempted += 1
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(ip, port), timeout=connect_timeout
                    )

                    async with aioftp.Client.context(
                        host=ip, port=port, user="anon", password=""
                    ) as client:
                        try:
                            path = await asyncio.wait_for(
                                client.stat(self.install_folder), timeout=stat_timeout
                            )
                            if path["type"] == "dir":
                                found_ip = ip
                                found_event.set()
                                self.logger.info(f"Found valid Sphaira at {ip}")
                                if self.debug:
                                    tqdm.write(f"\nFound valid Sphaira → {ip}")
                                return
                        except (aioftp.StatusCodeError, asyncio.TimeoutError):
                            pass

                    writer.close()
                    await writer.wait_closed()

                except (asyncio.TimeoutError, OSError, ConnectionRefusedError):
                    pass

        start = time.monotonic()
        if self.debug:
            tqdm.write(
                f"Scanning 192.168.{min(third_octets)}–{max(third_octets)}.x ..."
            )

        tasks = []
        for a in third_octets:
            for b in fourth_octets:
                if found_event.is_set():
                    break
                ip = f"192.168.{a}.{b}"
                tasks.append(asyncio.create_task(probe(ip)))

        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        for t in pending:
            t.cancel()

        duration = time.monotonic() - start

        if found_ip:
            self.ip_address = found_ip
            self.logger.info(
                f"Discovery successful - Found {found_ip} in {duration:.1f}s after {probes_attempted} probes"
            )
            if self.debug:
                tqdm.write(f"Discovery finished in {duration:.1f}s → using {found_ip}")
            return True
        else:
            self.logger.warning(
                f"No Sphaira found after {duration:.1f}s ({probes_attempted} probes attempted)"
            )
            if self.debug:
                tqdm.write(f"No Sphaira found after {duration:.1f}s")
            return False

    def _send_file_info_result(self, file_size: int, flags: int):
        """Send file info result to Switch using Sphaira protocol"""
        size_lsb = file_size & 0xFFFFFFFF
        size_msb = ((file_size >> 32) & 0xFFFF) | (flags << 16)
        self.usb_conn.send_result(RESULT_OK, size_msb, size_lsb)

    def _file_transfer_loop_local(
        self, file_path: str, file_size: int, flags: int, progress_callback, pbar
    ):
        """Transfer loop for local files using Sphaira protocol"""
        self.logger.info("Starting file transfer loop for local file...")

        bytes_transferred = 0
        total_requests = 0

        with open(file_path, "rb") as f:
            while True:
                # Get offset + size from Switch
                [offset, size, _] = self.usb_conn.get_send_data_header()

                # Check if we should finish now
                if offset == 0 and size == 0:
                    self.usb_conn.send_result(RESULT_OK)
                    self.logger.info("✓ Transfer complete!")
                    break

                total_requests += 1

                try:
                    # Seek to offset and read data
                    f.seek(offset)
                    buf = f.read(size)

                    if len(buf) == 0:
                        self.logger.error(f"Read 0 bytes at offset {offset}")
                        self.usb_conn.send_result(RESULT_ERROR)
                        continue

                    # Progress indicator
                    progress = (offset / file_size) * 100 if file_size > 0 else 0
                    if total_requests % 10 == 0:
                        self.logger.debug(
                            f"[Transfer] offset={offset}, size={size} ({progress:.1f}% - request #{total_requests})"
                        )

                    # Respond with length and CRC32C
                    self.usb_conn.send_result(RESULT_OK, len(buf), crc32c.crc32c(buf))

                    # Send the data
                    self.usb_conn.write(buf)

                    bytes_transferred += len(buf)

                    # Update progress
                    if pbar:
                        pbar.update(len(buf))

                except Exception as e:
                    self.logger.error(
                        f"Error reading/sending chunk at offset {offset}: {e}"
                    )
                    self.usb_conn.send_result(RESULT_ERROR)
                    raise

    async def _file_transfer_loop_http(
        self,
        client: httpx.AsyncClient,
        url: str,
        file_size: int,
        flags: int,
        headers: dict,
        cookies: dict,
        progress_callback,
        pbar,
    ):
        """Transfer loop for HTTP streams using Sphaira protocol"""
        self.logger.info("Starting file transfer loop for HTTP stream...")

        # Create a buffer to cache data
        buffer = {}
        bytes_transferred = 0
        total_requests = 0

        def _transfer_loop():
            nonlocal bytes_transferred, total_requests

            # Use sync httpx client in executor
            import httpx as sync_httpx

            with sync_httpx.Client(
                timeout=sync_httpx.Timeout(30.0, connect=10.0),
                follow_redirects=True,
                http2=True,
            ) as sync_client:
                while True:
                    # Get offset + size from Switch
                    [offset, size, _] = self.usb_conn.get_send_data_header()

                    # Check if we should finish now
                    if offset == 0 and size == 0:
                        self.usb_conn.send_result(RESULT_OK)
                        self.logger.info("✓ Transfer complete!")
                        break

                    total_requests += 1

                    # Check if we have this data cached
                    cache_key = offset
                    if cache_key in buffer:
                        # Use cached data
                        buf = buffer[cache_key][:size]
                        if total_requests % 50 == 0:
                            self.logger.debug(
                                f"[Cache hit] offset={offset}, size={size}"
                            )
                    else:
                        try:
                            # Make a range request
                            end_byte = min(offset + size - 1, file_size - 1)
                            range_headers = {"Range": f"bytes={offset}-{end_byte}"}
                            if headers:
                                range_headers.update(headers)

                            # Progress indicator
                            progress = (
                                (offset / file_size) * 100 if file_size > 0 else 0
                            )
                            if total_requests % 10 == 0:
                                self.logger.debug(
                                    f"[Download] offset={offset}, size={size} ({progress:.1f}% - request #{total_requests})"
                                )

                            response = sync_client.get(
                                url, headers=range_headers, cookies=cookies
                            )
                            response.raise_for_status()

                            buf = response.content
                            bytes_transferred += len(buf)

                            # Cache this chunk
                            buffer[cache_key] = buf

                            # Limit buffer size to prevent memory issues
                            if len(buffer) > 100:  # Keep max 100 chunks
                                oldest_key = min(buffer.keys())
                                del buffer[oldest_key]

                        except Exception as e:
                            self.logger.error(
                                f"Error downloading chunk at offset {offset}: {e}"
                            )
                            self.usb_conn.send_result(RESULT_ERROR)
                            continue

                    # Respond with length and CRC32C
                    self.usb_conn.send_result(RESULT_OK, len(buf), crc32c.crc32c(buf))

                    # Send the data
                    self.usb_conn.write(buf)

                    # Update progress
                    if pbar:
                        pbar.update(len(buf))

        await asyncio.get_event_loop().run_in_executor(None, _transfer_loop)

    async def _usb_install_file(
        self, file_path: str, filename: str, file_size: int, progress_callback=None
    ):
        """Install a file via USB using Sphaira protocol"""
        self.logger.info(
            f"Starting USB file install - File: {file_path}, Size: {file_size} bytes ({file_size / (1024 * 1024):.2f} MiB)"
        )

        if not self.usb_conn:
            error_msg = "USB connection not initialized"
            self.logger.error(error_msg)
            return {"error": error_msg}

        pbar = None
        start_time = time.time()
        loop = asyncio.get_event_loop()

        if not progress_callback:
            pbar = tqdm(
                total=file_size,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                desc="Uploading via USB",
                dynamic_ncols=True,
                miniters=1,
            )

        def _usb_handshake_and_transfer():
            try:
                # Build string table with just one file
                string_table = bytes(filename, "utf8") + b"\n"

                # Read the send header and check the magic (Sphaira handshake)
                self.logger.info("⏳ Waiting for Sphaira handshake...")
                self.usb_conn.get_send_header()
                self.logger.info("✓ Handshake received")

                # Send result and string table
                self.usb_conn.send_result(RESULT_OK, len(string_table))
                self.usb_conn.write(string_table)
                self.logger.info("✓ File list sent to Switch")

                # Wait for command
                self.logger.info("⏳ Waiting for install command from Switch...")
                [cmd, file_index, _] = self.usb_conn.get_send_header()

                if cmd == CMD_QUIT:
                    self.usb_conn.send_result(RESULT_OK)
                    self.logger.info("✓ Quit command received")
                    return {"error": "Transfer cancelled by Switch"}
                elif cmd == CMD_OPEN:
                    self.logger.info(
                        f"✓ Install command received for file index {file_index}"
                    )

                    # Set FLAG_NONE since we can seek
                    flags = FLAG_NONE

                    # Send file info result
                    self._send_file_info_result(file_size, flags)

                    # Start file transfer loop
                    self._file_transfer_loop_local(
                        file_path, file_size, flags, progress_callback, pbar
                    )
                else:
                    self.logger.error(f"✗ Unknown command received: {cmd}")
                    self.usb_conn.send_result(RESULT_ERROR)
                    return {"error": f"Unknown command: {cmd}"}

                return {"success": True}

            except Exception as e:
                self.logger.error(
                    f"USB transfer error: {type(e).__name__} - {e}", exc_info=True
                )
                raise

        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, _usb_handshake_and_transfer
            )

            elapsed_time = time.time() - start_time
            avg_speed = file_size / elapsed_time if elapsed_time > 0 else 0

            if result.get("success"):
                self.logger.info("=" * 80)
                self.logger.info("USB file transfer completed successfully!")
                self.logger.info(f"Filename: {filename}")
                self.logger.info(
                    f"Total bytes: {file_size} ({file_size / (1024 * 1024):.2f} MiB)"
                )
                self.logger.info(f"Elapsed time: {elapsed_time:.2f} seconds")
                self.logger.info(
                    f"Average speed: {avg_speed / (1024 * 1024):.2f} MiB/s"
                )
                self.logger.info("=" * 80)

            if pbar:
                pbar.close()
                if result.get("success"):
                    tqdm.write(f"USB upload complete: {filename}")

            return (
                result
                if result.get("success")
                else {"error": result.get("error", "Unknown error")}
            )

        except Exception as e:
            error_msg = f"USB file transfer error: {type(e).__name__} - {e}"
            self.logger.error(error_msg, exc_info=True)
            if pbar:
                pbar.close()
            return {"error": error_msg}

    async def _usb_stream_http(
        self,
        url: str,
        filename: str,
        headers: Optional[dict] = None,
        cookies: Optional[dict] = None,
        proxy: Optional[str] = None,
        connect_timeout: float = 12.0,
        read_timeout: float = 60.0,
        progress_callback=None,
    ):
        """Stream HTTP content directly to Switch via USB using Sphaira protocol"""
        self.logger.info(f"Starting USB HTTP stream - URL: {url}, Filename: {filename}")
        self.logger.debug(
            f"Parameters - Headers: {headers}, Cookies: {cookies}, Proxy: {proxy}"
        )
        self.logger.debug(
            f"Timeouts - Connect: {connect_timeout}s, Read: {read_timeout}s"
        )

        if not self.usb_conn:
            error_msg = "USB connection not initialized"
            self.logger.error(error_msg)
            return {"error": error_msg}

        # Get file size via HEAD request
        total_size = None
        try:
            self.logger.info("Attempting HEAD request to get content size...")
            log_http_request(self.logger, "HEAD", url, headers, cookies)

            async with httpx.AsyncClient(
                timeout=httpx.Timeout(connect_timeout, read=read_timeout),
                proxy=proxy,
                follow_redirects=True,
            ) as client:
                resp = await client.head(url, headers=headers, cookies=cookies)
                log_http_response(self.logger, resp.status_code, resp.headers)

                if resp.status_code == 200 and "Content-Length" in resp.headers:
                    total_size = int(resp.headers["Content-Length"])
                    self.logger.info(
                        f"Content-Length from HEAD: {total_size} bytes ({total_size / (1024 * 1024):.2f} MiB)"
                    )
                else:
                    self.logger.warning(
                        f"HEAD request returned {resp.status_code}, content length unknown"
                    )
        except Exception as e:
            self.logger.warning(
                f"HEAD request failed (size unknown): {type(e).__name__} - {e}"
            )
            if not progress_callback and self.debug:
                tqdm.write(f"HEAD request failed (size unknown): {e}")

        if not total_size:
            error_msg = "Could not determine file size from HEAD request"
            self.logger.error(error_msg)
            return {"error": error_msg}

        pbar = None
        start_time = time.time()

        if not progress_callback:
            pbar = tqdm(
                total=total_size,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                desc="Streaming to USB",
                dynamic_ncols=True,
                miniters=1,
            )

        def _usb_handshake():
            try:
                # Build string table with just one file
                string_table = bytes(filename, "utf8") + b"\n"

                # Read the send header and check the magic (Sphaira handshake)
                self.logger.info("⏳ Waiting for Sphaira handshake...")
                self.usb_conn.get_send_header()
                self.logger.info("✓ Handshake received")

                # Send result and string table
                self.usb_conn.send_result(RESULT_OK, len(string_table))
                self.usb_conn.write(string_table)
                self.logger.info("✓ File list sent to Switch")

                # Wait for command
                self.logger.info("⏳ Waiting for install command from Switch...")
                [cmd, file_index, _] = self.usb_conn.get_send_header()

                if cmd == CMD_QUIT:
                    self.usb_conn.send_result(RESULT_OK)
                    self.logger.info("✓ Quit command received")
                    return {"error": "Transfer cancelled by Switch"}
                elif cmd == CMD_OPEN:
                    self.logger.info(
                        f"✓ Install command received for file index {file_index}"
                    )

                    # Set FLAG_NONE since we can seek with HTTP range requests
                    flags = FLAG_NONE

                    # Send file info result
                    self._send_file_info_result(total_size, flags)

                    return {"success": True}
                else:
                    self.logger.error(f"✗ Unknown command received: {cmd}")
                    self.usb_conn.send_result(RESULT_ERROR)
                    return {"error": f"Unknown command: {cmd}"}

            except Exception as e:
                self.logger.error(
                    f"USB handshake error: {type(e).__name__} - {e}", exc_info=True
                )
                raise

        try:
            # Perform handshake
            result = await asyncio.get_event_loop().run_in_executor(
                None, _usb_handshake
            )

            if not result.get("success"):
                if pbar:
                    pbar.close()
                return result

            # Now start the file transfer loop
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(connect_timeout, read=read_timeout),
                proxy=proxy,
                follow_redirects=True,
            ) as http_client:
                self.logger.info("Starting HTTP stream transfer loop...")
                await self._file_transfer_loop_http(
                    http_client,
                    url,
                    total_size,
                    FLAG_NONE,
                    headers,
                    cookies,
                    progress_callback,
                    pbar,
                )

            elapsed_time = time.time() - start_time
            avg_speed = total_size / elapsed_time if elapsed_time > 0 else 0

            self.logger.info("=" * 80)
            self.logger.info("USB stream transfer completed successfully!")
            self.logger.info(f"Filename: {filename}")
            self.logger.info(
                f"Total bytes: {total_size} ({total_size / (1024 * 1024):.2f} MiB)"
            )
            self.logger.info(f"Elapsed time: {elapsed_time:.2f} seconds")
            self.logger.info(f"Average speed: {avg_speed / (1024 * 1024):.2f} MiB/s")
            self.logger.info("=" * 80)

            if pbar:
                pbar.close()
                tqdm.write(
                    f"USB stream finished: {filename} ({total_size / (1024 * 1024):.1f} MiB)"
                )

            return {"success": True, "size_bytes": total_size, "filename": filename}

        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP error {e.response.status_code}: {e}"
            self.logger.error(error_msg, exc_info=True)
            if pbar:
                pbar.close()
            return {"error": error_msg}
        except httpx.RequestError as e:
            error_msg = f"HTTP request failed: {type(e).__name__} - {e}"
            self.logger.error(error_msg, exc_info=True)
            if pbar:
                pbar.close()
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"USB transfer error: {type(e).__name__} - {e}"
            self.logger.error(error_msg, exc_info=True)
            if pbar:
                pbar.close()
            return {"error": error_msg}

    async def uploadLocalGame(
        self, fileName="bastion.nsp", method="auto", progress_callback=None
    ):
        self.logger.info(f"uploadLocalGame called - File: {fileName}, Method: {method}")
        file_path = f"software/{fileName}"
        try:
            file_size = os.path.getsize(file_path)
            self.logger.info(
                f"Local file found - Size: {file_size} bytes ({file_size / (1024 * 1024):.2f} MiB)"
            )
        except FileNotFoundError:
            error_msg = f"File {file_path} not found"
            self.logger.error(error_msg)
            return {"error": error_msg}

        # Auto-detect method if set to "auto"
        if method == "auto":
            self.logger.info("Auto-detecting transfer method...")
            # Try USB first
            if await self.detect_usb_switch():
                method = "usb"
                self.logger.info("USB detected, using USB mode for transfer")
                if not progress_callback and self.debug:
                    tqdm.write("Using USB mode for transfer")
            else:
                # Fall back to FTP
                method = "ftp"
                self.logger.info("USB not available, falling back to FTP mode")
                if not progress_callback and self.debug:
                    tqdm.write("USB not available, using FTP mode")

        # Use USB if requested
        if method == "usb":
            self.logger.info("Using USB method for local game upload")
            if not self.usb_conn:
                if not await self.detect_usb_switch():
                    error_msg = "Switch not found via USB. Please ensure it's connected and in Sphaira/Awoo mode."
                    self.logger.error(error_msg)
                    return {"error": error_msg}

            return await self._usb_install_file(
                file_path, fileName, file_size, progress_callback
            )

        # Use FTP
        elif method == "ftp":
            self.logger.info(
                f"Using FTP method for local game upload to {self.ip_address or 'unknown IP'}"
            )
            if not self.ip_address:
                if not progress_callback and self.debug:
                    tqdm.write("No IP set → running discovery first...")
                found = await self.discover_and_connect()
                if not found:
                    error_msg = "Could not find Sphaira on the network"
                    self.logger.error(error_msg)
                    return {"error": error_msg}
            # Only use tqdm if no progress callback is provided
            pbar = None
            bytes_transferred = 0
            start_time = time.time()

            if not progress_callback:
                pbar = tqdm(
                    total=file_size,
                    unit="B",
                    unit_scale=True,
                    unit_divisor=1024,
                    desc="Uploading via FTP",
                    dynamic_ncols=True,
                )

            try:
                self.logger.debug(
                    f"Connecting to FTP - Host: {self.ip_address}, Port: 5000"
                )
                async with aioftp.Client.context(
                    host=self.ip_address, port=5000, user="anon", password=""
                ) as client:
                    try:
                        path = await client.stat(self.install_folder)
                        if path["type"] != "dir":
                            if pbar:
                                pbar.close()
                            error_msg = (
                                f"{self.install_folder} exists but is not a directory"
                            )
                            self.logger.error(error_msg)
                            return {"error": error_msg}
                    except aioftp.StatusCodeError as e:
                        if pbar:
                            pbar.close()
                        if e.code == 550:
                            error_msg = f"{self.install_folder} does not exist → is this Sphaira?"
                            self.logger.error(error_msg)
                            return {"error": error_msg}

                if not progress_callback and self.debug:
                    tqdm.write(
                        f"Uploading {fileName} to {self.ip_address}:{self.install_folder}"
                    )

                self.logger.info(
                    f"Starting FTP upload to {self.ip_address}:{self.install_folder}/{fileName}"
                )
                async with client.upload_stream(
                    destination=f"{self.install_folder}/{fileName}"
                ) as stream:
                    async with aiofiles.open(file_path, "rb") as f:
                        while True:
                            chunk = await f.read(FTP_CHUNK_SIZE)
                            if not chunk:
                                break
                            await stream.write(chunk)
                            chunk_size = len(chunk)
                            bytes_transferred += chunk_size

                            if pbar:
                                pbar.update(chunk_size)
                            elif progress_callback:
                                await progress_callback(chunk_size)

                elapsed_time = time.time() - start_time
                avg_speed = bytes_transferred / elapsed_time if elapsed_time > 0 else 0

                self.logger.info("=" * 80)
                self.logger.info("FTP upload completed successfully!")
                self.logger.info(f"Filename: {fileName}")
                self.logger.info(
                    f"Total bytes transferred: {bytes_transferred} ({bytes_transferred / (1024 * 1024):.2f} MiB)"
                )
                self.logger.info(f"Elapsed time: {elapsed_time:.2f} seconds")
                self.logger.info(
                    f"Average speed: {avg_speed / (1024 * 1024):.2f} MiB/s"
                )
                self.logger.info("=" * 80)

                if pbar:
                    pbar.close()
                    tqdm.write(f"Upload complete: {fileName}")
                return {"success": True, "size_bytes": file_size}

            except Exception as e:
                error_msg = f"FTP upload error: {type(e).__name__} - {e}"
                self.logger.error(error_msg, exc_info=True)
                if pbar:
                    pbar.close()
                return {"error": error_msg}

        elif method == "mtp":
            self.logger.warning("MTP upload requested but not implemented")
            return {"error": "MTP upload not implemented yet"}

        return {"error": f"Unsupported method: {method}"}

    async def streamHttpGame(
        self,
        url: str,
        filename: str = None,
        headers: dict = None,
        cookies: dict = None,
        proxy: str = None,
        chunk_size: int = 1024 * 512,
        connect_timeout: float = 12.0,
        read_timeout: float = 60.0,
        progress_callback=None,
        method: str = "auto",
    ) -> dict:
        """
        Stream download from HTTP/HTTPS URL → stream upload directly to Sphaira
        No disk usage on your PC.
        Supports both USB (faster) and FTP (network) methods.
        """
        self.logger.info(f"streamHttpGame called - URL: {url}, Method: {method}")
        self.logger.debug(
            f"Parameters - Headers: {headers}, Cookies: {cookies}, Proxy: {proxy}"
        )
        self.logger.debug(
            f"Timeouts - Connect: {connect_timeout}s, Read: {read_timeout}s, Chunk size: {chunk_size}"
        )

        if not filename:
            filename = url.split("/")[-1] or "downloaded_game.nsp"
            self.logger.debug(f"Filename extracted from URL: {filename}")

        # Auto-detect method if set to "auto"
        if method == "auto":
            self.logger.info("Auto-detecting transfer method...")
            # Try USB first
            if await self.detect_usb_switch():
                method = "usb"
                self.logger.info("USB detected, using USB mode for streaming")
                if not progress_callback and self.debug:
                    tqdm.write("Using USB mode for streaming")
            else:
                # Fall back to FTP
                method = "ftp"
                self.logger.info(
                    "USB not available, falling back to FTP mode for streaming"
                )
                if not progress_callback and self.debug:
                    tqdm.write("USB not available, using FTP mode")

        # Use USB if requested
        if method == "usb":
            self.logger.info("Using USB method for HTTP streaming")
            if not self.usb_conn:
                if not await self.detect_usb_switch():
                    error_msg = "Switch not found via USB. Please ensure it's connected and in Sphaira/Awoo mode."
                    self.logger.error(error_msg)
                    return {"error": error_msg}

            return await self._usb_stream_http(
                url,
                filename,
                headers,
                cookies,
                proxy,
                connect_timeout,
                read_timeout,
                progress_callback,
            )

        # Use FTP (original implementation)
        elif method == "ftp":
            self.logger.info(
                f"Using FTP method for HTTP streaming to {self.ip_address or 'unknown IP'}"
            )
            if not self.ip_address:
                if not progress_callback and self.debug:
                    tqdm.write("No IP set → starting discovery...")
                found = await self.discover_and_connect()
                if not found:
                    error_msg = "Could not find Sphaira on the network"
                    self.logger.error(error_msg)
                    return {"error": error_msg}

            total_size = None

            # Try HEAD to get size
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(connect_timeout, read=read_timeout),
                    proxy=proxy,
                    follow_redirects=True,
                ) as client:
                    resp = await client.head(url, headers=headers, cookies=cookies)
                    if resp.status_code == 200 and "Content-Length" in resp.headers:
                        total_size = int(resp.headers["Content-Length"])
            except Exception as e:
                if not progress_callback and self.debug:
                    tqdm.write(f"HEAD request failed (size unknown): {e}")

            # Only use tqdm if no progress callback is provided
            pbar = None
            bytes_transferred = 0
            if not progress_callback:
                pbar = tqdm(
                    total=total_size,
                    unit="B",
                    unit_scale=True,
                    unit_divisor=1024,
                    desc="Streaming to Sphaira",
                    dynamic_ncols=True,
                    miniters=1,
                )

            try:
                async with aioftp.Client.context(
                    host=self.ip_address, port=5000, user="anon", password=""
                ) as ftp_client:
                    try:
                        st = await ftp_client.stat(self.install_folder)
                        if st["type"] != "dir":
                            if pbar:
                                pbar.close()
                            return {
                                "error": f"{self.install_folder} exists but is not a directory"
                            }
                    except aioftp.StatusCodeError as e:
                        if pbar:
                            pbar.close()
                        if e.code == 550:
                            return {
                                "error": f"{self.install_folder} not found → is this Sphaira?"
                            }

                    destination = f"{self.install_folder}/{filename}"

                    async with ftp_client.upload_stream(destination) as ftp_stream:
                        async with httpx.AsyncClient(
                            timeout=httpx.Timeout(connect_timeout, read=read_timeout),
                            proxy=proxy,
                            follow_redirects=True,
                        ) as http_client:
                            async with http_client.stream(
                                "GET", url, headers=headers, cookies=cookies
                            ) as response:
                                response.raise_for_status()

                                if not progress_callback and self.debug:
                                    tqdm.write(
                                        f"Streaming: {url} → {self.ip_address}:{destination}"
                                    )

                                async for chunk in response.aiter_bytes():
                                    if not chunk:
                                        break
                                    await ftp_stream.write(chunk)
                                    chunk_size = len(chunk)
                                    bytes_transferred += chunk_size

                                    if pbar:
                                        pbar.update(chunk_size)
                                    elif progress_callback:
                                        await progress_callback(chunk_size)

                if pbar:
                    pbar.close()
                    tqdm.write(
                        f"Stream finished: {filename}  ({pbar.n / (1024 * 1024):.1f} MiB)"
                    )

                return {
                    "success": True,
                    "size_bytes": bytes_transferred if not pbar else pbar.n,
                    "filename": filename,
                }

            except httpx.HTTPStatusError as e:
                if pbar:
                    pbar.close()
                return {"error": f"HTTP error {e.response.status_code}: {e}"}
            except httpx.RequestError as e:
                if pbar:
                    pbar.close()
                return {"error": f"HTTP request failed: {e}"}
            except aioftp.errors.AIOFTPException as e:
                if pbar:
                    pbar.close()
                return {"error": f"FTP error: {e}"}
            except Exception as e:
                if pbar:
                    pbar.close()
                return {"error": f"Unexpected: {type(e).__name__} - {e}"}

        else:
            return {"error": f"Unsupported method: {method}"}


if __name__ == "__main__":

    async def main():
        downloader = SphairaDownloader(debug=True)

        result = await downloader.streamHttpGame(
            url="https://files.obnoxious.lol/switch/switchGames/Doom%20%281993%29%5B010018900DD00000-010018900DD00800-10-base%5D.nsp",
            # filename="Doom 1993.nsp",           # optional - overrides name from URL
            # proxy="http://127.0.0.1:8080",
            # chunk_size=1024*1024,
        )
        tqdm.write(f"Result: {result}")

    asyncio.run(main())
