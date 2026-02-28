import os
from dotenv import load_dotenv
from util.constants import LLM_MODE
import lmstudio as lms
from openai import OpenAI
from util.groq_llm_client import GROQLLM

# Load environment variables from the .env file
load_dotenv()

class LLMClient:
    def __init__(self, json_format=False, temp=None):
        self.temp = temp
        self.json_format = json_format
        self.max_completion_tokens = int(os.getenv("LLM_MAX_COMPLETION_TOKENS", "512"))
        
        if LLM_MODE == 'openai':
            # Allow customizing request timeout for hosted environments.
            timeout_s = float(os.getenv("OPENAI_TIMEOUT", "60"))
            self.client = OpenAI(timeout=timeout_s)
        elif LLM_MODE == 'groq':
            self.client = GROQLLM(response_format_json=json_format, temp=temp)
        else:
            self.model = os.getenv("LLM_OFFLINE_MODEL")
            if not self.model:
                raise ValueError("LLM_OFFLINE_MODEL is not set in the environment variables.")
            
            self.client = lms.llm(self.model)
    

    def generate(self, system_prompt: str, user_prompt: str):
        if LLM_MODE == 'openai':
            kwargs = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
            }

            if self.temp is not None:
                kwargs["temperature"] = self.temp

            if self.json_format:
                kwargs["response_format"] = {"type": "json_object"}

            # Keep completions bounded to reduce latency and avoid gateway timeouts.
            if self.max_completion_tokens and self.max_completion_tokens > 0:
                kwargs["max_completion_tokens"] = self.max_completion_tokens
                
            response = self.client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        elif LLM_MODE == 'groq':
            response = self.client.invoke(system_instruction=system_prompt, input=user_prompt)
            return response.content
        else:
            config = {}
            if self.temp is not None:
                config["temperature"] = self.temp

            if self.json_format:
                config["response_format"] = {"type": "json_object"}
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            response = self.client.respond({"messages": messages}, config=config)
            return response.content