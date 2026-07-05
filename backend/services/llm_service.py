"""
BookScout AI - LLM Service
Communicates with the local Ollama server.
Designed for easy replacement with other LLM providers.
"""

import json
import logging
import httpx

from backend.config import settings
from backend.utils.helpers import extract_json_from_response

logger = logging.getLogger("bookscout")


class LLMService:
    """
    Service for communicating with the local Ollama LLM.
    All agent reasoning goes through this service.
    """

    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL
        self.timeout = settings.OLLAMA_TIMEOUT

    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        """
        Send a prompt to Ollama and return the text response.
        
        Args:
            prompt: The user/agent prompt to send
            system_prompt: Optional system prompt for context
            
        Returns:
            The LLM's text response
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 2048,
            },
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()
                return result.get("response", "")
        except httpx.TimeoutException:
            logger.error("Ollama request timed out")
            return ""
        except httpx.HTTPError as e:
            logger.error(f"Ollama HTTP error: {e}")
            return ""
        except Exception as e:
            logger.error(f"Ollama unexpected error: {e}")
            return ""

    async def generate_json(self, prompt: str, system_prompt: str = "") -> dict:
        """
        Send a prompt to Ollama and parse the response as JSON.
        Handles common LLM quirks like markdown fences around JSON.
        
        Args:
            prompt: The prompt requesting JSON output
            system_prompt: Optional system prompt
            
        Returns:
            Parsed JSON dict, or empty dict on failure
        """
        # Append explicit JSON instruction to improve compliance
        json_instruction = (
            "\n\nIMPORTANT: Respond with ONLY valid JSON. "
            "No markdown, no explanation, no text before or after the JSON. "
            "Do NOT wrap in ```json``` code fences."
        )
        full_prompt = prompt + json_instruction
        
        raw_response = await self.generate(full_prompt, system_prompt)
        
        if not raw_response:
            return {}
        
        return extract_json_from_response(raw_response)

    async def is_available(self) -> bool:
        """Check if the Ollama server is running and the model is available."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    model_names = [m.get("name", "") for m in models]
                    # Check if our model is available (with or without :latest tag)
                    return any(
                        self.model in name or name.startswith(self.model.split(":")[0])
                        for name in model_names
                    )
                return False
        except Exception:
            return False
