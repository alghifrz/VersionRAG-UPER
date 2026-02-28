from neo4j_graphrag.llm import LLMInterface, LLMResponse
from groq import Groq, AsyncGroq
from typing import List, Optional, Union
from neo4j_graphrag.message_history import MessageHistory
from neo4j_graphrag.types import LLMMessage
import os

TIMEOUT = 300
class GROQLLM(LLMInterface):
    def __init__(
        self,
        # Use an env override so model deprecations can be handled without code changes.
        # If the default ever deprecates, set GROQ_MODEL in src/.env.
        model: str = None,  # e.g. llama-3.3-70b-versatile / llama-3.1-8b-instant
        temp: float = None,
        response_format_json: bool = False
    ):
        self.client = Groq(timeout=TIMEOUT) # longer timeout than default of 60s
        self.aclient = AsyncGroq(timeout=TIMEOUT)
        self.model = model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.temp = temp
        self.response_format_json = response_format_json
        self.max_completion_tokens = int(os.getenv("LLM_MAX_COMPLETION_TOKENS", "512"))

    def _build_kwargs(self, input: str, system_prompt: str = None):
        messages = []

        # Add system prompt if provided
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Add user input
        messages.append({"role": "user", "content": input})

        kwargs = {
            "model": self.model,
            "messages": messages,
            #"max_completion_tokens": 80000, # to give the model sufficient space to complete its reasoning without truncation.
            #"reasoning_format": "parsed" # ignore thinking token in the beginning of response
        }

        if self.temp is not None:
            kwargs["temperature"] = self.temp

        if self.response_format_json:
            kwargs["response_format"] = {"type": "json_object"}

        # Groq uses `max_tokens` (not `max_completion_tokens`).
        if self.max_completion_tokens and self.max_completion_tokens > 0:
            kwargs["max_tokens"] = self.max_completion_tokens

        return kwargs

    def invoke(self, input: str, message_history: Optional[Union[List[LLMMessage], MessageHistory]] = None, system_instruction: Optional[str] = None) -> LLMResponse:
        print(len(input))
        kwargs = self._build_kwargs(input, system_instruction)
        response = self.client.chat.completions.create(**kwargs)
        return LLMResponse(content=response.choices[0].message.content)


    async def ainvoke(self, input: str, message_history: Optional[Union[List[LLMMessage], MessageHistory]] = None, system_instruction: Optional[str] = None) -> LLMResponse:
        kwargs = self._build_kwargs(input, system_instruction)
        response = await self.aclient.chat.completions.create(**kwargs)
        return LLMResponse(content=response.choices[0].message.content)