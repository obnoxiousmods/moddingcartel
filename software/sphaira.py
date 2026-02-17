import asyncio
import os
import time

import aiofiles
import aioftp
import httpx
from tqdm import tqdm


class SphairaDownloader:
    def __init__(self, ip_address=None, install_folder="install:", debug=True):
        self.ip_address = ip_address
        self.install_folder = install_folder
        self.debug = debug

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

    async def uploadLocalGame(self, fileName="bastion.nsp", method="ftp", progress_callback=None):
        if not self.ip_address:
            if not progress_callback and self.debug:
                tqdm.write("No IP set → running discovery first...")
            found = await self.discover_and_connect()
            if not found:
                return {"error": "Could not find Sphaira on the network"}

        file_path = f"software/{fileName}"
        try:
            file_size = os.path.getsize(file_path)
        except FileNotFoundError:
            return {"error": f"File {file_path} not found"}

        if method == "ftp":
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
                            chunk = await f.read(1024 * 1024)
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
    ) -> dict:
        """
        Stream download from HTTP/HTTPS URL → stream upload directly to Sphaira
        No disk usage on your PC.
        """
        if not filename:
            filename = url.split("/")[-1] or "downloaded_game.nsp"

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