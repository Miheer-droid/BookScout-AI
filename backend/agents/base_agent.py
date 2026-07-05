"""
BookScout AI - Base Agent
Shared base class for all agents with LLM communication helpers.
"""

import logging
from backend.services.llm_service import LLMService

logger = logging.getLogger("bookscout")


class BaseAgent:
    """
    Base class for all BookScout agents.
    Provides LLM interaction helpers with logging and error handling.
    """

    def __init__(self, llm: LLMService, name: str) -> None:
        self.llm = llm
        self.name = name

    async def _ask_json(self, prompt: str, system_prompt: str = "") -> dict:
        """
        Ask the LLM a question and parse the response as JSON.

        Args:
            prompt: The prompt to send
            system_prompt: Optional system context

        Returns:
            Parsed JSON dict, or empty dict on failure
        """
        try:
            logger.info(f"[{self.name}] Requesting JSON from LLM")
            result = await self.llm.generate_json(prompt, system_prompt)
            if not result:
                logger.warning(f"[{self.name}] LLM returned empty JSON")
            return result
        except Exception as e:
            logger.error(f"[{self.name}] LLM JSON request failed: {e}")
            return {}

    async def _ask(self, prompt: str, system_prompt: str = "") -> str:
        """
        Ask the LLM a question and return the text response.

        Args:
            prompt: The prompt to send
            system_prompt: Optional system context

        Returns:
            Text response, or empty string on failure
        """
        try:
            logger.info(f"[{self.name}] Requesting text from LLM")
            result = await self.llm.generate(prompt, system_prompt)
            if not result:
                logger.warning(f"[{self.name}] LLM returned empty text")
            return result
        except Exception as e:
            logger.error(f"[{self.name}] LLM text request failed: {e}")
            return ""
