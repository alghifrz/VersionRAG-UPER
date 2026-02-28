import os

from util.llm_client import LLMClient

system_prompt = """
                You are an intelligent assistant that answers user questions based strictly on the provided retrieved context.
		        - If the context contains relevant information, generate a clear, concise, and accurate answer.
	            - Do not use any external knowledge or make assumptions beyond the given context.
                - If the context does not contain enough information to answer the question, 
                  respond with: “The provided context does not contain enough information to answer this question.”
                - Maintain a confident and professional tone in all responses.
            """

class BaseGenerator:
    def __init__(self):
        """
        Initializes the BaseGenerator with an LLMClient.
        """
        self.llm_client = LLMClient(temp=0.0)  # Initialize the LLM client
        self.system_prompt = system_prompt

    def render_context(self, retrieved_data) -> str:
        """
        Render retrieved data into a bounded string so LLM calls stay fast and
        avoid gateway/proxy timeouts on hosted environments (e.g. Render).
        """
        max_chars = int(os.getenv("RAG_MAX_CONTEXT_CHARS", "12000"))
        s = str(retrieved_data)
        if max_chars > 0 and len(s) > max_chars:
            head = max(0, max_chars - 220)
            s = s[:head] + "\n\n[...context truncated...]\n"
        return s

    def generate(self, retrieved_data, query):
        """
        Generates a response based on the retrieved data and query.

        Args:
            retrieved_data: The data retrieved by the retriever.
            query: The user's question.

        Returns:
            A Response object containing the answer and source files.
        """
        raise NotImplementedError("Subclasses must implement this method.")

class Response:
    def __init__(self, answer):
        self.answer = answer

    def __str__(self):
        return f"Answer: {self.answer}"