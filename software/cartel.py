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

    def __init__(self, base_url: str = "http://localhost:8000", api_key: Optional[str] = None):
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
                    raise Exception(f"Login failed: {data.get('error', 'Unknown error')}")
            else:
                raise Exception(f"Login failed with status {response.status_code}: {response.text}")

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
                headers={"X-API-Key": self.api_key},
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    return data.get("queue", [])
                else:
                    raise Exception(f"Failed to get queue: {data.get('error', 'Unknown error')}")
            else:
                raise Exception(f"Request failed with status {response.status_code}: {response.text}")

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
                headers={"X-API-Key": self.api_key},
                json={"queue_item_id": queue_item_id, "status": status},
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    return data
                else:
                    raise Exception(f"Failed to update queue item: {data.get('error', 'Unknown error')}")
            else:
                raise Exception(f"Request failed with status {response.status_code}: {response.text}")

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
                headers["X-API-Key"] = self.api_key

            response = self.client.get(
                f"{self.base_url}/api/entries/{entry_id}/info",
                headers=headers,
            )

            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"Request failed with status {response.status_code}: {response.text}")

        except httpx.RequestError as e:
            raise Exception(f"Network error: {e}")
