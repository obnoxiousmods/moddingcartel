import asyncio
import aioftp

"""This file is going to be a library/API for python developers to implement downloading games and automatically sending them to Sphaira on a NSW.

Sphaira supports MTP & FTP & SFTP? for network installation.
I want to support bruteforcing the IP address on port 5000 to find the Sphaira device on the local network, and then send the files there.
Also support manually entering the IP address of the Sphaira device.
Would MTP support ip auto finding idk.

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

"""

async def upload_game