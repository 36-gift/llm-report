"""
Simple DeepSeek API client for direct API calls.
"""
import logging
import time
from typing import Any, Dict, List, Optional

import requests

from ..exceptions import APIError

logger = logging.getLogger(__name__)


class DeepSeekAPIClient:
    """Simple DeepSeek API client for chat completions."""

    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com"):
        """
        Initialize the DeepSeek API client.

        Args:
            api_key: DeepSeek API key
            base_url: Base URL for the API
        """
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "LLM-Report-Tool/1.0",
        }

        # Track API metrics
        self.total_requests = 0
        self.total_tokens_used = 0
        self.average_response_time = 0.0

        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "deepseek-chat",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Make a chat completion request.

        Args:
            messages: List of messages for the conversation
            model: Model to use (deepseek-chat or deepseek-reasoner)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Returns:
            API response dictionary

        Raises:
            APIError: If API call fails
        """
        start_time = time.time()

        data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }

        try:
            response = self.session.post(
                f"{self.base_url}/chat/completions",
                json=data,
                timeout=30,  # DeepSeek supports up to 30 minutes
            )

            response.raise_for_status()
            result = response.json()

            # Track metrics
            self._update_metrics(start_time, result)

            return result

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                # Rate limit exceeded (rare with DeepSeek)
                logger.warning("DeepSeek API temporarily rate limited")
                raise APIError(f"Rate limit exceeded: {str(e)}")
            elif e.response.status_code == 401:
                raise APIError("Invalid DeepSeek API key")
            elif e.response.status_code >= 500:
                raise APIError(f"DeepSeek server error: {str(e)}")
            else:
                raise APIError(f"HTTP error: {str(e)}")

        except requests.exceptions.Timeout:
            raise APIError("Request timed out")

        except requests.exceptions.ConnectionError:
            raise APIError("Connection error")

        except Exception as e:
            raise APIError(f"Unexpected error: {str(e)}")

    def _update_metrics(self, start_time: float, response: Dict[str, Any]):
        """Update API usage metrics."""
        response_time = time.time() - start_time

        # Update average response time
        self.total_requests += 1
        self.average_response_time = (
            self.average_response_time * (self.total_requests - 1) + response_time
        ) / self.total_requests

        # Track token usage if available
        if "usage" in response:
            usage = response["usage"]
            total_tokens = usage.get("total_tokens", 0)
            self.total_tokens_used += total_tokens

    def get_metrics(self) -> Dict[str, Any]:
        """Get API usage metrics."""
        return {
            "total_requests": self.total_requests,
            "total_tokens_used": self.total_tokens_used,
            "average_response_time": round(self.average_response_time, 3),
        }

    def health_check(self) -> Dict[str, Any]:
        """Perform a health check on the API."""
        try:
            start_time = time.time()

            # Simple test request
            response = self.chat_completion(
                messages=[{"role": "user", "content": "Hello"}], max_tokens=5, temperature=0.1
            )

            response_time = time.time() - start_time

            return {
                "status": "healthy",
                "response_time": round(response_time, 3),
                "timestamp": time.time(),
            }

        except Exception as e:
            return {"status": "unhealthy", "error": str(e), "timestamp": time.time()}

    def __del__(self):
        """Cleanup on destruction."""
        if hasattr(self, "session"):
            self.session.close()
