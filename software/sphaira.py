import asyncio
import os
import struct
import time
from typing import Tuple

import aiofiles
import aioftp
import httpx
from tqdm import tqdm

try:
    import usb.core
    import usb.util
    USB_AVAILABLE = True
except ImportError:
    USB_AVAILABLE = False


# Constants
USB_CHUNK_SIZE = 1024 * 1024  # 1MB chunks for USB transfers
FTP_CHUNK_SIZE = 1024 * 1024  # 1MB chunks for FTP transfers


class SphairaDownloader:
    def __init__(self, ip_address=None, install_folder="install:", debug=True):
        self.ip_address = ip_address
        self.install_folder = install_folder
        self.debug = debug
        self.usb_device = None
        self.usb_in_ep = None
        self.usb_out_ep = None

    async def detect_usb_switch(self) -> bool:
        """
        Detect Nintendo Switch connected via USB using Tinfoil/Awoo protocol.
        Returns True if Switch is detected and USB endpoints are configured.
        """
        if not USB_AVAILABLE:
            if self.debug:
                tqdm.write("pyusb not available - USB support disabled")
            return False

        def _detect():
            try:
                # Try to find Switch in USB mode
                # VID: 0x057E (Nintendo), PID: 0x3000 (Switch in Tinfoil/Awoo mode)
                dev = usb.core.find(idVendor=0x057E, idProduct=0x3000)

                if dev is None:
                    if self.debug:
                        tqdm.write("No Switch detected in USB mode (VID:0x057E, PID:0x3000)")
                    return False

                # Reset and configure the device
                try:
                    dev.reset()
                except Exception as e:
                    if self.debug:
                        tqdm.write(f"Device reset failed (may be normal): {e}")

                dev.set_configuration()
                cfg = dev.get_active_configuration()

                # Find IN and OUT endpoints
                def is_out_ep(ep):
                    return usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT

                def is_in_ep(ep):
                    return usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN

                out_ep = usb.util.find_descriptor(cfg[(0, 0)], custom_match=is_out_ep)
                in_ep = usb.util.find_descriptor(cfg[(0, 0)], custom_match=is_in_ep)

                if out_ep is None or in_ep is None:
                    if self.debug:
                        tqdm.write("Failed to find USB endpoints")
                    return False

                # Store device and endpoints
                self.usb_device = dev
                self.usb_out_ep = out_ep
                self.usb_in_ep = in_ep

                if self.debug:
                    tqdm.write(f"✓ Switch detected via USB (VID:0x{dev.idVendor:04X}, PID:0x{dev.idProduct:04X})")

                return True

            except Exception as e:
                if self.debug:
                    tqdm.write(f"USB detection error: {e}")
                return False

        return await asyncio.get_event_loop().run_in_executor(None, _detect)

    def _usb_send_packet(self, command: int, payload: bytes, timeout: int = 60000):
        """Send a packet over USB using Tinfoil/Awoo protocol"""
        if not self.usb_device or not self.usb_out_ep:
            raise RuntimeError("USB device not initialized")

        # Packet format:
        # Magic: 4 bytes (0x12121212)
        # Command: 4 bytes (little endian)
        # Size: 8 bytes (little endian)
        # ThreadId: 4 bytes (little endian)
        # PacketIndex: 2 bytes (little endian)
        # PacketCount: 2 bytes (little endian)
        # Timestamp: 8 bytes (little endian)
        # Payload: variable length

        header = b'\x12\x12\x12\x12'  # Magic
        header += struct.pack('<I', command)  # Command
        header += struct.pack('<Q', len(payload))  # Size
        header += struct.pack('<I', 0)  # ThreadId
        header += struct.pack('<H', 0)  # PacketIndex
        header += struct.pack('<H', 0)  # PacketCount
        header += struct.pack('<Q', 0)  # Timestamp

        self.usb_out_ep.write(header, timeout=timeout)
        if len(payload) > 0:
            self.usb_out_ep.write(payload, timeout=timeout)

    def _usb_recv_packet(self, timeout: int = 60000) -> Tuple[int, bytes]:
        """Receive a packet over USB using Tinfoil/Awoo protocol"""
        if not self.usb_device or not self.usb_in_ep:
            raise RuntimeError("USB device not initialized")

        # Read header (32 bytes)
        header = bytes(self.usb_in_ep.read(32, timeout=timeout))

        magic = header[:4]
        if magic != b'\x12\x12\x12\x12':
            raise RuntimeError(f"Invalid magic in USB packet: {magic.hex()}")

        command = int.from_bytes(header[4:8], byteorder='little')
        size = int.from_bytes(header[8:16], byteorder='little')

        # Read payload
        payload = b''
        if size > 0:
            payload = bytes(self.usb_in_ep.read(size, timeout=timeout))

        return command, payload

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
        if self.ip_address:
            if self.debug:
                tqdm.write(f"Already have IP: {self.ip_address} — skipping discovery")
            return True

        semaphore = asyncio.Semaphore(max_concurrent)
        found_event = asyncio.Event()
        found_ip = None

        async def probe(ip: str):
            nonlocal found_ip
            if found_event.is_set():
                return

            async with semaphore:
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
            tqdm.write(f"Scanning 192.168.{min(third_octets)}–{max(third_octets)}.x ...")

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
            if self.debug:
                tqdm.write(f"Discovery finished in {duration:.1f}s → using {found_ip}")
            return True
        else:
            if self.debug:
                tqdm.write(f"No Sphaira found after {duration:.1f}s")
            return False

    async def _usb_install_file(self, file_path: str, filename: str, file_size: int, progress_callback=None):
        """Install a file via USB using Tinfoil/Awoo protocol"""
        # Send initial handshake - request to install
        install_request = f"install:/{filename}".encode('utf-8')
        await asyncio.get_event_loop().run_in_executor(
            None, self._usb_send_packet, 1, install_request
        )

        # Wait for acknowledgment
        cmd, response = await asyncio.get_event_loop().run_in_executor(
            None, self._usb_recv_packet
        )
        if cmd != 1 or response != b'OK':
            return {"error": f"USB handshake failed: cmd={cmd}, response={response}"}

        # Open and send file
        pbar = None
        if not progress_callback:
            pbar = tqdm(
                total=file_size,
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
                desc="Uploading via USB",
                dynamic_ncols=True,
            )

        try:
            async with aiofiles.open(file_path, "rb") as f:
                while True:
                    chunk = await f.read(USB_CHUNK_SIZE)
                    if not chunk:
                        break

                    # Send data packet
                    await asyncio.get_event_loop().run_in_executor(
                        None, self._usb_send_packet, 2, chunk
                    )

                    chunk_size = len(chunk)
                    if pbar:
                        pbar.update(chunk_size)
                    elif progress_callback:
                        await progress_callback(chunk_size)

            # Send completion signal
            await asyncio.get_event_loop().run_in_executor(
                None, self._usb_send_packet, 3, b''
            )

            if pbar:
                pbar.close()
                tqdm.write(f"USB upload complete: {filename}")

            return {"success": True, "size_bytes": file_size}

        except Exception as e:
            if pbar:
                pbar.close()
            raise e

    async def _usb_stream_http(self, url: str, filename: str, headers: dict, cookies: dict, proxy: str,
                               connect_timeout: float, read_timeout: float, progress_callback=None):
        """Stream HTTP content directly to Switch via USB"""
        # Get file size via HEAD request
        total_size = None
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

        # Send initial handshake
        install_request = f"install:/{filename}".encode('utf-8')
        await asyncio.get_event_loop().run_in_executor(
            None, self._usb_send_packet, 1, install_request
        )

        # Wait for acknowledgment
        cmd, response = await asyncio.get_event_loop().run_in_executor(
            None, self._usb_recv_packet
        )
        if cmd != 1 or response != b'OK':
            return {"error": f"USB handshake failed: cmd={cmd}, response={response}"}

        pbar = None
        bytes_transferred = 0
        if not progress_callback:
            pbar = tqdm(
                total=total_size,
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
                desc="Streaming to USB",
                dynamic_ncols=True,
                miniters=1,
            )

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(connect_timeout, read=read_timeout),
                proxy=proxy,
                follow_redirects=True,
            ) as http_client:
                async with http_client.stream("GET", url, headers=headers, cookies=cookies) as response:
                    response.raise_for_status()

                    if not progress_callback and self.debug:
                        tqdm.write(f"Streaming: {url} → Switch via USB")

                    async for chunk in response.aiter_bytes():
                        if not chunk:
                            break

                        # Send chunk via USB
                        await asyncio.get_event_loop().run_in_executor(
                            None, self._usb_send_packet, 2, chunk
                        )

                        chunk_size = len(chunk)
                        bytes_transferred += chunk_size

                        if pbar:
                            pbar.update(chunk_size)
                        elif progress_callback:
                            await progress_callback(chunk_size)

            # Send completion signal
            await asyncio.get_event_loop().run_in_executor(
                None, self._usb_send_packet, 3, b''
            )

            if pbar:
                pbar.close()
                tqdm.write(f"USB stream finished: {filename} ({bytes_transferred / (1024*1024):.1f} MiB)")

            return {"success": True, "size_bytes": bytes_transferred, "filename": filename}

        except httpx.HTTPStatusError as e:
            if pbar:
                pbar.close()
            return {"error": f"HTTP error {e.response.status_code}: {e}"}
        except httpx.RequestError as e:
            if pbar:
                pbar.close()
            return {"error": f"HTTP request failed: {e}"}
        except Exception as e:
            if pbar:
                pbar.close()
            return {"error": f"USB transfer error: {type(e).__name__} - {e}"}

    async def uploadLocalGame(self, fileName="bastion.nsp", method="auto", progress_callback=None):
        file_path = f"software/{fileName}"
        try:
            file_size = os.path.getsize(file_path)
        except FileNotFoundError:
            return {"error": f"File {file_path} not found"}

        # Auto-detect method if set to "auto"
        if method == "auto":
            # Try USB first
            if await self.detect_usb_switch():
                method = "usb"
                if not progress_callback and self.debug:
                    tqdm.write("Using USB mode for transfer")
            else:
                # Fall back to FTP
                method = "ftp"
                if not progress_callback and self.debug:
                    tqdm.write("USB not available, using FTP mode")

        # Use USB if requested
        if method == "usb":
            if not self.usb_device:
                if not await self.detect_usb_switch():
                    return {"error": "Switch not found via USB. Please ensure it's connected and in Sphaira/Awoo mode."}

            return await self._usb_install_file(file_path, fileName, file_size, progress_callback)

        # Use FTP
        elif method == "ftp":
            if not self.ip_address:
                if not progress_callback and self.debug:
                    tqdm.write("No IP set → running discovery first...")
                found = await self.discover_and_connect()
                if not found:
                    return {"error": "Could not find Sphaira on the network"}
            # Only use tqdm if no progress callback is provided
            pbar = None
            if not progress_callback:
                pbar = tqdm(
                    total=file_size,
                    unit='B',
                    unit_scale=True,
                    unit_divisor=1024,
                    desc="Uploading via FTP",
                    dynamic_ncols=True,
                )

            async with aioftp.Client.context(
                host=self.ip_address, port=5000, user="anon", password=""
            ) as client:
                try:
                    path = await client.stat(self.install_folder)
                    if path["type"] != "dir":
                        if pbar:
                            pbar.close()
                        return {"error": f"{self.install_folder} exists but is not a directory"}
                except aioftp.StatusCodeError as e:
                    if pbar:
                        pbar.close()
                    if e.code == 550:
                        return {"error": f"{self.install_folder} does not exist → is this Sphaira?"}

                if not progress_callback and self.debug:
                    tqdm.write(f"Uploading {fileName} to {self.ip_address}:{self.install_folder}")

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

                            if pbar:
                                pbar.update(chunk_size)
                            elif progress_callback:
                                await progress_callback(chunk_size)

                if pbar:
                    pbar.close()
                    tqdm.write(f"Upload complete: {fileName}")
                return {"success": True, "size_bytes": file_size}

        elif method == "mtp":
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
        if not filename:
            filename = url.split("/")[-1] or "downloaded_game.nsp"

        # Auto-detect method if set to "auto"
        if method == "auto":
            # Try USB first
            if await self.detect_usb_switch():
                method = "usb"
                if not progress_callback and self.debug:
                    tqdm.write("Using USB mode for streaming")
            else:
                # Fall back to FTP
                method = "ftp"
                if not progress_callback and self.debug:
                    tqdm.write("USB not available, using FTP mode")

        # Use USB if requested
        if method == "usb":
            if not self.usb_device:
                if not await self.detect_usb_switch():
                    return {"error": "Switch not found via USB. Please ensure it's connected and in Sphaira/Awoo mode."}

            return await self._usb_stream_http(
                url, filename, headers, cookies, proxy,
                connect_timeout, read_timeout, progress_callback
            )

        # Use FTP (original implementation)
        elif method == "ftp":
            if not self.ip_address:
                if not progress_callback and self.debug:
                    tqdm.write("No IP set → starting discovery...")
                found = await self.discover_and_connect()
                if not found:
                    return {"error": "Could not find Sphaira on the network"}

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
                    unit='B',
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
                            return {"error": f"{self.install_folder} exists but is not a directory"}
                    except aioftp.StatusCodeError as e:
                        if pbar:
                            pbar.close()
                        if e.code == 550:
                            return {"error": f"{self.install_folder} not found → is this Sphaira?"}

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
                                    tqdm.write(f"Streaming: {url} → {self.ip_address}:{destination}")

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
                    tqdm.write(f"Stream finished: {filename}  ({pbar.n / (1024*1024):.1f} MiB)")

                return {
                    "success": True,
                    "size_bytes": bytes_transferred if not pbar else pbar.n,
                    "filename": filename
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
