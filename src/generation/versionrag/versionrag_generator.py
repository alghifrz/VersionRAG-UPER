from generation.baseline.base_generator import BaseGenerator, Response

class VersionRAGGenerator(BaseGenerator):
    def __init__(self):
        """
        Initializes the VersionRAGGenerator with version-aware system prompt.
        """
        super().__init__()
        # Override system prompt to be more version-aware
        self.system_prompt = """
                You are an intelligent assistant that answers user questions based strictly on the provided retrieved context.
                The context may contain information from multiple document versions.
                
                Guidelines:
                - If the context contains relevant information, generate a clear, concise, and accurate answer.
                - Pay attention to version information when provided - different versions may have different or updated information.
                - If multiple versions are mentioned, you can compare or reference specific versions when relevant.
                - Do not use any external knowledge or make assumptions beyond the given context.
                - If the context does not contain enough information to answer the question, 
                  respond with: "The provided context does not contain enough information to answer this question."
                - Maintain a confident and professional tone in all responses.
                - When version information is available, you may reference it to provide more precise answers.
            """
    
    def generate(self, retrieved_data, query):        
        user_prompt = f"Question: {query}\n\nRetrieved Data:\n{retrieved_data}"
        llm_response = self.llm_client.generate(system_prompt=self.system_prompt, user_prompt=user_prompt)
        return Response(answer=llm_response)