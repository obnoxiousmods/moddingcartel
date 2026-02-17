import sys

import crc32c
import httpx
from usb_common_x import CMD_OPEN, CMD_QUIT, FLAG_NONE, RESULT_ERROR, RESULT_OK, Usb

# URL of the file to stream
FILE_URL = "https://files.obnoxious.lol/switch/switchGames/Celeste%5B01002B30028F6000-01002B30028F6800-6-base%5D.xci"


def send_file_info_result(usb_conn: Usb, result: int, file_size: int, flags: int):
    size_lsb = file_size & 0xFFFFFFFF
    size_msb = ((file_size >> 32) & 0xFFFF) | (flags << 16)
    usb_conn.send_result(result, size_msb, size_lsb)


def file_transfer_loop(
    usb_conn: Usb, client: httpx.Client, file_size: int, flags: int
) -> None:
    print("inside file transfer loop now\n")

    # Create a buffer to cache data
    buffer = {}
    bytes_transferred = 0
    total_requests = 0

    while True:
        # get offset + size.
        [off, size, _] = usb_conn.get_send_data_header()

        # check if we should finish now.
        if off == 0 and size == 0:
            usb_conn.send_result(RESULT_OK)
            print("\n✓ Transfer complete!")
            break

        total_requests += 1

        # Check if we have this data cached
        cache_key = off
        if cache_key in buffer:
            # Use cached data if available
            buf = buffer[cache_key][:size]
            print(f"  [Cache hit] offset={off}, size={size}")
        else:
            try:
                # Make a range request to get the specific chunk
                end_byte = min(off + size - 1, file_size - 1)
                headers = {"Range": f"bytes={off}-{end_byte}"}

                # Progress indicator
                progress = (off / file_size) * 100 if file_size > 0 else 0
                print(
                    f"  [Download] offset={off}, size={size} ({progress:.1f}% - request #{total_requests})"
                )

                response = client.get(FILE_URL, headers=headers)
                response.raise_for_status()

                buf = response.content
                bytes_transferred += len(buf)

                # Cache this chunk
                buffer[cache_key] = buf

                # Limit buffer size to prevent memory issues
                if len(buffer) > 100:  # Keep max 100 chunks (~100MB)
                    # Remove oldest entry
                    oldest_key = min(buffer.keys())
                    del buffer[oldest_key]

            except httpx.HTTPError as e:
                print(f"✗ Error: failed to download chunk at offset {off}: {str(e)}")
                usb_conn.send_result(RESULT_ERROR)
                continue

        # respond back with the length of the data and the crc32c.
        usb_conn.send_result(RESULT_OK, len(buf), crc32c.crc32c(buf))

        # send the data.
        usb_conn.write(buf)


def wait_for_input(
    usb_conn: Usb, client: httpx.Client, file_index: int, file_size: int
) -> None:
    print("now waiting for input\n")

    try:
        # Set FLAG_NONE since we can seek with HTTP range requests
        flags: int = FLAG_NONE

        print("Streaming file from URL")
        print(f"File size: {file_size} bytes ({file_size / (1024 * 1024):.2f} MB)\n")

        send_file_info_result(usb_conn, RESULT_OK, file_size, flags)
        file_transfer_loop(usb_conn, client, file_size, flags)

    except httpx.HTTPError as e:
        print(f"✗ Error: failed to connect to URL: {str(e)}")
        usb_conn.send_result(RESULT_ERROR)
    except OSError as e:
        print(f"✗ Error: {str(e)}")
        usb_conn.send_result(RESULT_ERROR)


if __name__ == "__main__":
    print("=" * 70)
    print(" " * 15 + "Sphaira USB Stream Installer")
    print(" " * 20 + "(pyusb + httpx)")
    print("=" * 70)
    print()

    # Create httpx client with timeout settings
    client = httpx.Client(
        timeout=httpx.Timeout(30.0, connect=10.0),
        follow_redirects=True,
        http2=True,
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
    )

    try:
        # Get file size first
        print("📡 Getting file information...")
        head_response = client.head(FILE_URL)
        head_response.raise_for_status()
        file_size = int(head_response.headers.get("content-length", 0))

        if file_size == 0:
            print("✗ Error: Could not determine file size")
            sys.exit(1)

        print(f"✓ File size: {file_size:,} bytes ({file_size / (1024 * 1024):.2f} MB)")

        # Check if server supports range requests
        accept_ranges = head_response.headers.get("accept-ranges", "")
        if accept_ranges.lower() == "bytes":
            print("✓ Server supports range requests")
        else:
            print("⚠  Warning: Server may not support range requests properly")

        # Extract filename from URL
        filename = "Bastion[010038600B27E000-010038600B27E800-0-base].nsp"
        print(f"✓ Filename: {filename}")
        print()

    except httpx.HTTPError as e:
        print(f"✗ Error: Failed to connect to URL: {str(e)}")
        client.close()
        sys.exit(1)

    usb_conn = Usb()

    try:
        # get usb endpoints.
        usb_conn.wait_for_connect()

        # build string table with just one file
        string_table = bytes(filename, "utf8") + b"\n"

        # this reads the send header and checks the magic.
        print("⏳ Waiting for sphaira handshake...")
        usb_conn.get_send_header()
        print("✓ Handshake received")

        # send recv and string table.
        usb_conn.send_result(RESULT_OK, len(string_table))
        usb_conn.write(string_table)
        print("✓ File list sent to Switch")
        print()

        # wait for command.
        print("⏳ Waiting for install command from Switch...")
        while True:
            [cmd, arg3, arg4] = usb_conn.get_send_header()

            if cmd == CMD_QUIT:
                usb_conn.send_result(RESULT_OK)
                print("✓ Quit command received")
                break
            elif cmd == CMD_OPEN:
                print(f"✓ Install command received for file index {arg3}")
                print()
                wait_for_input(usb_conn, client, arg3, file_size)
            else:
                print(f"✗ Unknown command received: {cmd}")
                usb_conn.send_result(RESULT_ERROR)
                break

        print()
        print("=" * 70)
        print(" " * 20 + "🎉 Transfer Completed! 🎉")
        print("=" * 70)

    except KeyboardInterrupt:
        print("\n\n✗ Transfer cancelled by user")
    except Exception as inst:
        print(f"\n✗ An exception occurred: {str(inst)}")
        import traceback

        traceback.print_exc()
    finally:
        print("\n🔌 Closing connections...")
        client.close()
        print("✓ Done!")
