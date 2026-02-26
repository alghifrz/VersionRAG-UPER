from enum import Enum
from util.llm_client import LLMClient
from util.chunker import Chunker
import json
import re
import os
import PyPDF2

llm_client = LLMClient(json_format=True, temp=0.0)
chunker = Chunker()

class FileType(Enum):
    WithoutChangelog = 1
    Changelog = 2
    
class FileAttributes:
    def __init__(self, data_file: str, type: FileType, documentation: str, description: str, version: str, additional_attributes: list, category: str = None, document_id: str = None):
        self.data_file = data_file
        self.type = type
        # documentation is a stable identifier used in the graph; prefer document_id if provided
        self.documentation = document_id or documentation
        self.display_name = documentation
        self.description = description
        self.version = version
        self.additional_attributes = additional_attributes
        self.category = category
        
    def __str__(self):
        return (f"File: {self.data_file}\n"
                f"File Type: {self.type.name}\n"
                f"Documentation: {self.documentation}\n"
                f"Display Name: {self.display_name}\n"
                f"Category: {self.category}\n"
                f"Description: {self.description}\n"
                f"Version: {self.version}\n"
                f"Additional Attributes:\n" +
                (
                    "\n".join([f"  - {attr}: {value}" for attr, value in self.additional_attributes.items()])
                    if self.additional_attributes else "  - None"
                ))

def extract_attributes_from_file(data_file, category: str = None) -> FileAttributes:
    print(f"extract attributes from file {data_file}")
    # If category not provided, infer it from the parent folder name of the file.
    # Example: data/raw/kalender-akademik/2024-2025.pdf -> category = "kalender-akademik"
    if category is None:
        file_dir = os.path.dirname(os.path.abspath(data_file))
        inferred_category = os.path.basename(file_dir)
        # If the file is directly under "raw", treat it as having no category.
        category = None if inferred_category.lower() == "raw" else inferred_category
    first_text_short = ""
    first_text_long = ""
    if data_file.lower().endswith(".pdf"):
        # extract pages from pdf
        page_count = get_page_count(data_file)
        if page_count == 0:
            raise ValueError(f"file is empty: {data_file}")
        print(f"page count {page_count}")
        
        chunks = chunker.chunk_document(data_file=data_file, page_to=1)
        first_text_short = "\n".join(chunk.chunk for chunk in chunks if chunk.chunk)
        chunks = chunker.chunk_document(data_file=data_file, page_to=min(page_count, 10))
        first_text_long = "\n".join(chunk.chunk for chunk in chunks if chunk.chunk)
    elif data_file.lower().endswith(".md"):
        # extract chunks from markdown
        chunks = chunker.chunk_document(data_file=data_file)
        chunk_count = len(chunks)
        if chunk_count == 0:
            raise ValueError(f"file is empty: {data_file}")
        print(f"chunk count {chunk_count}")
        # Kombiniere alle Chunks zu einem durchgehenden Text
        full_text = "".join(chunk.chunk for chunk in chunks if chunk.chunk)

        # Schneide die ersten 200 bzw. 500 Zeichen aus dem kombinierten Text
        first_text_short = full_text[:200]
        first_text_long = full_text[:300]
    else:
        raise ValueError(f'unsupported file type {data_file}')
    
    first_page_attributes = extract_attributes_from_first_page(first_text_short)
    file_type = extract_file_type_from_pages(first_text_long)
    
    # Extract version from filename instead of from LLM
    version_from_filename = extract_version_from_filename(data_file)
    print(f"Extracted version from filename: {version_from_filename}")

    return FileAttributes(data_file=data_file,
                          type=file_type,
                          documentation=first_page_attributes["topic"],
                          description=first_page_attributes["description"],
                          version=version_from_filename,
                          additional_attributes=first_page_attributes.get("additional_attributes"),
                          category=category)

def get_page_count(data_file):
    with open(data_file, "rb") as file:
        pdfReader = PyPDF2.PdfReader(file)
        return len(pdfReader.pages)
    raise ValueError(f"unable to read page count from file: {data_file}")
    
def clean_version_string(version_str):
    """Keep only numbers, dashes, and dots from the version string."""
    return re.sub(r'[^0-9\-.]', '', version_str)

def extract_version_from_filename(data_file):
    """
    Extract version from filename (without extension).
    Examples:
    - 2016-2017.pdf -> 2016-2017
    - 2017-2018.pdf -> 2017-2018
    - kalender-2024.pdf -> kalender-2024 (returns as-is if no clear pattern)
    - file_v1.0.pdf -> file_v1.0 (returns as-is)
    - changelog-2016-2017.pdf -> 2016-2017 (changelog- prefix stripped)
    
    Returns the filename without extension as the version.
    """
    # Get filename without path and extension
    filename = os.path.basename(data_file)
    # Remove extension (.pdf, .md, etc.)
    filename_without_ext = os.path.splitext(filename)[0]
    
    # Strip common changelog prefixes so that changelog and main file share the same version
    # Example: changelog-2016-2017 -> 2016-2017
    if filename_without_ext.lower().startswith("changelog-"):
        filename_without_ext = filename_without_ext[len("changelog-"):]
    elif filename_without_ext.lower().startswith("changelog_"):
        filename_without_ext = filename_without_ext[len("changelog_"):]
    
    # Clean the version string (keep only alphanumeric, dashes, dots, underscores)
    # This preserves formats like "2016-2017", "v1.0", "2024", etc.
    cleaned_version = re.sub(r'[^a-zA-Z0-9\-._]', '', filename_without_ext)
    
    return cleaned_version if cleaned_version else "unknown"

def extract_attributes_from_first_page(first_page_content):
    system_prompt_first_page = """
    You are an intelligent assistant specialized in extracting structured information from documents.  
    Your task is to analyze the first page of a given PDF and extract the following details in a structured JSON format. 
    Do not add JSON comments to the output.

    1 **"topic"**: The main subject of the document.  
    - Provide a short, clear, and descriptive title (max. 10 words).  
    - Do not include any version reference in the title.
    - If no clear topic is found, return `"unknown"`.  
    
    2 **"description"**: A brief summary of the document based on the first page without explicit version-naming.
    - Summarize the content in 1-3 sentences.  
    - **IMPORTANT: Preserve the original language of the document.** If the document is in Indonesian, write the description in Indonesian. If it's in English, write in English.
    - If no meaningful description is available, return `"unknown"`.
    
    **Note:** Version will be extracted from the filename automatically, so you don't need to extract it.
 
    **Output format (JSON example):**  
    ```json
    {
        "topic": "Node.js Assertion Module",
        "description": "The document provides information about the assert module in Node.js, detailing its functions and strict assertion mode, including examples of usage and error messaging."
    }
    """

    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            first_page_response = llm_client.generate(system_prompt=system_prompt_first_page, user_prompt=first_page_content)

            # Convert JSON string to a Python dictionary
            first_page_response = first_page_response.replace("```json", "").replace("```", "").strip()
            data = json.loads(first_page_response)
            # Version is no longer extracted from LLM, it comes from filename
            # So we don't need to check for version field
            return data
        except Exception as e:
            print(f"error during extraction: {e}")
            if attempt >= max_attempts:
                raise ValueError(f"Error: failed to parse llm response:\n response: {first_page_response}\n input:{first_page_content}")
    raise ValueError(f"unable to extract attributes from first page\n first page: {first_page_content}")

def extract_file_type_from_pages(pages_content):
    system_prompt_file_type = """
    You are an intelligent assistant specialized in analyzing document content.

    You will receive the first few chunks of a document (representing its beginning). Your task is to determine whether the document is a **changelog** or a general document.

    Return **only** a valid JSON object in the following format:  
    { "answer": 1 } or { "answer": 2 }

    ### Classification rules:

    1. **1** = WithoutChangelog  
        → The document does **not** contain a changelog in the provided chunks.  
        → These are general documents (e.g., manuals, specifications, reports) **without** a focus on version updates or modifications.  
        → Even if the document mentions changes or has some update history, **if it is not focused on listing changes**, classify it as **1**.

    2. **2** = Changelog  
        → The document **is a changelog** or **release/update log**.  
        → It is specifically focused on listing **changes**, updates, or version history. It includes terms like `Change`, `Revision`, `Modification`, `Amendment`, `Update`, etc.  
        → The document must be **dedicated to listing changes** and not just mention them casually.

    ### Notes:
    - Use only the given text chunks to make your decision.
    - If the type is unclear or you're unsure, return **1** as a safe default.
    - Return **only** the JSON object – no extra text or formatting.
    """
    max_attempts = 5

    for attempt in range(max_attempts):
        try:
            response = llm_client.generate(system_prompt=system_prompt_file_type, user_prompt=pages_content)
            data = json.loads(response) 
            answer = data.get("answer")
            if answer is not None and str(answer).isdigit():
                return FileType(int(answer))
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"Attempt {attempt + 1} failed: {e}")

    raise ValueError('Unable to extract file type from file')

