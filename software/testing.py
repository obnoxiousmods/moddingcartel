import asyncio
import os
import time

import aiofiles
import aioftp
from progress.bar import Bar

"""This file is going to be a library/API for python developers to implement downloading games and automatically sending them to Sphaira on a NSW.

Sphaira supports MTP & FTP & SFTP? for network installation.
I want to support bruteforcing the IP address on port 5000 to find the Sphaira device on the local network, and then send the files there.
Also support manually entering the IP address of the Sphaira device.
Would MTP support ip auto finding idk.

Snippet for AIOFTP usage
import asyncio
import aioftp


async def get_mp3(host, port, login, password):
    async with aioftp.Client.context(host, port, login, password) as client:
        for path, info in (await client.list(recursive=True)):
            if info["type"] == "file" and path.suffix == ".mp3":
                await client.download(path)


async def main():
    tasks = [
        asyncio.create_task(get_mp3("server1.com", 21, "login", "password")),
        asyncio.create_task(get_mp3("server2.com", 21, "login", "password")),
        asyncio.create_task(get_mp3("server3.com", 21, "login", "password")),
    ]
    await asyncio.wait(tasks)

asyncio.run(main())

.....

Sphaira is listening on Host 192.168.1.79 for now, port 5000, user and pass blank
WE must upload the file to the INSTALL folder. Lets check if exists first, if not create it, then upload the file there.

"""


class ProgressBarWithSpeed(Bar):
    """Custom progress bar that displays MB/s speed"""

    def __init__(self, *args, **kwargs):
        self.start_time = time.time()
        self.bytes_transferred = 0
        super().__init__(*args, **kwargs)

    def update_bytes(self, bytes_count):
        """Update the number of bytes transferred"""
        self.bytes_transferred += bytes_count
        self.next()

    @property
    def speed_mbps(self):
        """Calculate current speed in MB/s"""
        elapsed = time.time() - self.start_time
        if elapsed > 0:
            return (self.bytes_transferred / (1024 * 1024)) / elapsed
        return 0.0


class SphairaDownloader:
    def __init__(self, ip_address, install_folder="install:", debug=True):
        """Sphaira uploader helper

        Args:
            ip_address (str): Ip address for your NSW. Must be on LAN.
            install_folder (str, optional): Don't change this. Defaults to "install:".
        """
        self.ip_address = ip_address
        self.install_folder = install_folder
        self.debug = debug
        self.progress_bar = None
        self.bytes_transferred = 0
        self.start_time = None

    async def _uploadViaFTP(self, fileName="bastion.nsp"):
        async with aioftp.Client.context(
            host=self.ip_address, port=5000, user="anon", password=""
        ) as client:
            try:
                path = await client.stat(self.install_folder)

                if path["type"] != "dir":
                    print(
                        f"{self.install_folder} exists but is not a directory. Deleting it and creating a new directory..."
                    )

            except aioftp.StatusCodeError as e:
                if e.code == 550:  # Directory does not exist
                    print(
                        f"{self.install_folder} directory does not exist. Not Sphaira?"
                    )
                    return {
                        "error": f"{self.install_folder} directory does not exist. Not Sphaira?"
                    }

            print(f"Uploading {fileName} to Sphaira at {self.ip_address}...")
            async with client.upload_stream(
                destination=f"{self.install_folder}/{fileName}"
            ) as stream:
                async with aiofiles.open(f"software/{fileName}", "rb") as f:
                    while True:
                        chunk = await f.read(1024 * 1024)  # Read in 1MB chunks
                        if not chunk:
                            break
                        writeResult = await stream.write(chunk)
                        if writeResult is None:
                            self.progress_bar.update_bytes(len(chunk))
                            pass

            if self.progress_bar:
                self.progress_bar.finish()

            if self.debug:
                print(f"Uploaded {fileName} to Sphaira at {self.ip_address}")

    async def uploadLocalGame(self, fileName="bastion.nsp", method="ftp"):
        # Calculate file size for progress bar
        file_path = f"software/{fileName}"
        try:
            file_size = os.path.getsize(file_path)
            chunk_size = 1024 * 1024  # 1MB chunks
            max_chunks = (file_size + chunk_size - 1) // chunk_size  # Round up
        except FileNotFoundError:
            print(f"Error: File {file_path} not found")
            return {"error": f"File {file_path} not found"}

        if method == "ftp":
            self.progress_bar = ProgressBarWithSpeed(
                "Uploading via FTP",
                max=max_chunks,
                suffix="%(percent)d%% - %(speed_mbps).2f MB/s - %(elapsed_td)s - ETA: %(eta_td)s",
            )
            return await self._uploadViaFTP(fileName=fileName)

        if method == "mtp":
            self.progress_bar = ProgressBarWithSpeed(
                "Uploading via MTP",
                max=max_chunks,
                suffix="%(percent)d%% - %(speed_mbps).2f MB/s - %(elapsed_td)s - ETA: %(eta_td)s",
            )
            return await self._uploadViaMTP(fileName=fileName)

        return {
            "error": f"Unsupported upload method: {method} | Supported methods: ftp, mtp"
        }


if __name__ == "__main__":
    downloader = SphairaDownloader(ip_address="192.168.1.79")
    asyncio.run(downloader.uploadLocalGame())
