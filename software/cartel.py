"""
ModdingCartel API Client Library

This module provides a Python client for interacting with the ModdingCartel API.
"""

import logging
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class ModdingCartel:
    """Client for ModdingCartel API"""

    def __init__(
        self, base_url: str = "http://127.0.0.1:6069", api_key: Optional[str] = None
    ):
        """
        Initialize the ModdingCartel client.

        Args:
            base_url: Base URL of the ModdingCartel server
            api_key: Optional API key for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client = httpx.Client(timeout=30.0)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """Close the HTTP client"""
        if self.client:
            self.client.close()

    def login(self, username: str, password: str) -> Dict:
        """
        Login to ModdingCartel and get or create an API key.

        Args:
            username: Username
            password: Password

        Returns:
            Dictionary with success status and API key if successful

        Raises:
            Exception: If login fails
        """
        try:
            response = self.client.post(
                f"{self.base_url}/api/auth/login",
                json={"username": username, "password": password},
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    self.api_key = data.get("api_key")
                    return data
                else:
                    raise Exception(
                        f"Login failed: {data.get('error', 'Unknown error')}"
                    )
            else:
                raise Exception(
                    f"Login failed with status {response.status_code}: {response.text}"
                )

        except httpx.RequestError as e:
            raise Exception(f"Network error during login: {e}")

    def get_send_queue(self) -> List[Dict]:
        """
        Get the current send queue for the authenticated user.

        Returns:
            List of queue items with entry details

        Raises:
            Exception: If not authenticated or request fails
        """
        if not self.api_key:
            raise Exception("Not authenticated. Please call login() first.")

        try:
            response = self.client.get(
                f"{self.base_url}/api/send-queue",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    return data.get("queue", [])
                else:
                    raise Exception(
                        f"Failed to get queue: {data.get('error', 'Unknown error')}"
                    )
            elif response.status_code == 401:
                # Invalid or revoked API key
                raise Exception("Invalid API Key")
            else:
                raise Exception(
                    f"Request failed with status {response.status_code}: {response.text}"
                )

        except httpx.RequestError as e:
            raise Exception(f"Network error: {e}")

    def update_queue_item(self, queue_item_id: str, status: str) -> Dict:
        """
        Update the status of a queue item.

        Args:
            queue_item_id: ID of the queue item
            status: New status ('processing', 'completed', or 'failed')

        Returns:
            Dictionary with success status

        Raises:
            Exception: If not authenticated or request fails
        """
        if not self.api_key:
            raise Exception("Not authenticated. Please call login() first.")

        if status not in ["processing", "completed", "failed"]:
            raise ValueError("Status must be 'processing', 'completed', or 'failed'")

        try:
            response = self.client.post(
                f"{self.base_url}/api/send-queue/update",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"queue_item_id": queue_item_id, "status": status},
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    return data
                else:
                    raise Exception(
                        f"Failed to update queue item: {data.get('error', 'Unknown error')}"
                    )
            else:
                raise Exception(
                    f"Request failed with status {response.status_code}: {response.text}"
                )

        except httpx.RequestError as e:
            raise Exception(f"Network error: {e}")

    def update_queue_progress(
        self,
        queue_item_id: str,
        progress_percent: Optional[int] = None,
        bytes_transferred: Optional[int] = None,
        transfer_speed: Optional[float] = None,
        status: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Dict:
        """
        Update progress information for a queue item.

        Args:
            queue_item_id: ID of the queue item
            progress_percent: Progress percentage (0-100)
            bytes_transferred: Number of bytes transferred
            transfer_speed: Transfer speed in bytes per second
            status: Status update ('processing', 'completed', 'failed')
            error_message: Error message if failed

        Returns:
            Dictionary with success status

        Raises:
            Exception: If not authenticated or request fails
        """
        if not self.api_key:
            raise Exception("Not authenticated. Please call login() first.")

        try:
            payload = {"queue_item_id": queue_item_id}

            if progress_percent is not None:
                payload["progress_percent"] = progress_percent
            if bytes_transferred is not None:
                payload["bytes_transferred"] = bytes_transferred
            if transfer_speed is not None:
                payload["transfer_speed"] = transfer_speed
            if status is not None:
                payload["status"] = status
            if error_message is not None:
                payload["error_message"] = error_message

            response = self.client.post(
                f"{self.base_url}/api/send-queue/progress",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    return data
                else:
                    raise Exception(
                        f"Failed to update progress: {data.get('error', 'Unknown error')}"
                    )
            elif response.status_code == 401:
                # Invalid or revoked API key
                raise Exception("Invalid API Key")
            else:
                raise Exception(
                    f"Request failed with status {response.status_code}: {response.text}"
                )

        except httpx.RequestError as e:
            raise Exception(f"Network error: {e}")

    def get_entry_info(self, entry_id: str) -> Dict:
        """
        Get information about a specific entry.

        Args:
            entry_id: ID of the entry

        Returns:
            Dictionary with entry information

        Raises:
            Exception: If request fails
        """
        try:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            response = self.client.get(
                f"{self.base_url}/api/entries/{entry_id}/info",
                headers=headers,
            )

            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(
                    f"Request failed with status {response.status_code}: {response.text}"
                )

        except httpx.RequestError as e:
            raise Exception(f"Network error: {e}")
