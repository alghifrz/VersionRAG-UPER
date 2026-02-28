import os
import time
from dotenv import load_dotenv
# from pymilvus import MilvusClient
# from util.constants import MILVUS_URI, MILVUS_META_ATTRIBUTE_TEXT, MILVUS_META_ATTRIBUTE_PAGE, MILVUS_META_ATTRIBUTE_FILE, MILVUS_META_ATTRIBUTE_CATEGORY, MILVUS_META_ATTRIBUTE_DOCUMENTATION, MILVUS_META_ATTRIBUTE_VERSION, MILVUS_META_ATTRIBUTE_TYPE, EMBEDDING_DIMENSIONS
from util.constants import MILVUS_META_ATTRIBUTE_TEXT, MILVUS_META_ATTRIBUTE_PAGE, MILVUS_META_ATTRIBUTE_FILE, MILVUS_META_ATTRIBUTE_CATEGORY, MILVUS_META_ATTRIBUTE_DOCUMENTATION, MILVUS_META_ATTRIBUTE_VERSION, MILVUS_META_ATTRIBUTE_TYPE, EMBEDDING_DIMENSIONS
from util.chunker import Chunker, Chunk
from util.embedding_client import get_embedding_client
from util.milvus_client_factory import get_milvus_client

load_dotenv()

class BaseIndexer:
    def __init__(self):
        self.embedding_fn = get_embedding_client()
        self.client = None
        self.chunker = Chunker()
        
    def index_data(self, data_files):
        raise NotImplementedError("Subclasses must implement this method.")
    
    def createCollectionIfRequired(self, collection_name):
        if self.client is None:
            # self.client = MilvusClient(MILVUS_URI)
            self.client = get_milvus_client()
        
        if not self.client.has_collection(collection_name=collection_name):
            self.client.create_collection(
                collection_name=collection_name,
                dimension=EMBEDDING_DIMENSIONS,
            )
    
    def _escape_milvus_filter_string(self, value):
        """
        Escape special characters in string for Milvus filter expression.
        Milvus filter needs backslashes to be escaped.
        """
        if not isinstance(value, str):
            return value
        # Escape backslash and double quotes for Milvus filter
        # Backslash needs to be escaped: \ -> \\
        # Double quote needs to be escaped: " -> \"
        escaped = value.replace('\\', '\\\\').replace('"', '\\"')
        return escaped
    
    def is_file_indexed(self, data_file, collection_name):
        """
        Check if a file is already indexed in the collection.
        Returns True if file exists, False otherwise.
        """
        if self.client is None:
            # self.client = MilvusClient(MILVUS_URI)
            self.client = get_milvus_client()
        
        if not self.client.has_collection(collection_name=collection_name):
            return False
        
        try:
            # Use absolute path for consistent comparison
            abs_file_path = os.path.abspath(data_file)
            # Escape path for Milvus filter (handle Windows backslashes)
            escaped_path = self._escape_milvus_filter_string(abs_file_path)
            result = self.client.query(
                collection_name=collection_name,
                filter=f'{MILVUS_META_ATTRIBUTE_FILE} == "{escaped_path}"',
                output_fields=[MILVUS_META_ATTRIBUTE_FILE],
                limit=1
            )
            return len(result) > 0
        except Exception as e:
            # If query fails, assume file is not indexed
            print(f"Warning: Could not check if file is indexed: {e}")
            return False
    
    def delete_file_from_collection(self, data_file, collection_name):
        """
        Delete all chunks from a specific file from the collection.
        Useful for re-indexing a file.
        """
        if self.client is None:
            # self.client = MilvusClient(MILVUS_URI)
            self.client = get_milvus_client()
        
        if not self.client.has_collection(collection_name=collection_name):
            return
        
        try:
            abs_file_path = os.path.abspath(data_file)
            # Escape path for Milvus filter (handle Windows backslashes)
            escaped_path = self._escape_milvus_filter_string(abs_file_path)
            self.client.delete(
                collection_name=collection_name,
                filter=f'{MILVUS_META_ATTRIBUTE_FILE} == "{escaped_path}"'
            )
            print(f"Deleted existing chunks for: {os.path.basename(data_file)}")
        except Exception as e:
            print(f"Warning: Could not delete file from collection: {e}")
    
    def index_file(self, data_file, collection_name, category="", documentation="", version="", skip_existing=True, re_index=False):
        """
        Index a file to the collection.
        
        Args:
            data_file: Path to the file to index
            collection_name: Name of the Milvus collection
            category: Category metadata
            documentation: Documentation metadata
            version: Version metadata
            skip_existing: If True, skip indexing if file already exists (default: True)
            re_index: If True, delete existing chunks before indexing (default: False)
        """
        data_file_name = os.path.basename(data_file)
        
        # Check if file already indexed
        if self.is_file_indexed(data_file, collection_name):
            if re_index:
                print(f"Re-indexing: {data_file_name} (deleting existing chunks)")
                self.delete_file_from_collection(data_file, collection_name)
            elif skip_existing:
                print(f"Skipping: {data_file_name} (already indexed)")
                return
            else:
                print(f"Warning: {data_file_name} already indexed, but skip_existing=False. This may cause duplicates!")
        
        print(f"Indexing: {data_file_name}")

        chunks = self.chunker.chunk_document(data_file=data_file)
        self.index(chunks=chunks, collection_name=collection_name, data_file=data_file, category=category, documentation=documentation, version=version, type="file")
        print(f"Indexed: {data_file_name} ({len(chunks)} chunks)")
        
    def index_chunk(self, chunk:Chunk, collection_name, category, documentation, version, type, file):
        self.index(chunks=[chunk], collection_name=collection_name, category=category, documentation=documentation, version=version, type=type, data_file=file)
        
    def index(self, chunks, collection_name, data_file="", category="", documentation="", version="", type=""):
        chunk_texts = [chunk.chunk for chunk in chunks]
        batch_size = 100
        
        # Use absolute path for consistent file identification
        abs_file_path = os.path.abspath(data_file) if data_file else ""

        for i in range(0, len(chunk_texts), batch_size):
            batch = chunk_texts[i:i + batch_size]
            batch_vectors = self.embedding_fn.encode_documents(batch)
            
            # Generate unique IDs to avoid conflicts
            # Use hash of file path + chunk index + metadata for uniqueness
            import hashlib
            base_id = int(hashlib.md5(f"{abs_file_path}_{category}_{documentation}_{version}_{type}".encode()).hexdigest()[:15], 16)
            
            data = [
                {"id": base_id + i + j, 
                "vector": batch_vectors[j],
                MILVUS_META_ATTRIBUTE_TEXT: chunks[i + j].chunk, 
                MILVUS_META_ATTRIBUTE_PAGE: chunks[i + j].page, 
                MILVUS_META_ATTRIBUTE_FILE: abs_file_path,
                MILVUS_META_ATTRIBUTE_CATEGORY: category,
                MILVUS_META_ATTRIBUTE_DOCUMENTATION: documentation,
                MILVUS_META_ATTRIBUTE_VERSION: version,
                MILVUS_META_ATTRIBUTE_TYPE: type}
                for j in range(len(batch_vectors))
            ]
            self.client.insert(collection_name=collection_name, data=data)
            time.sleep(1)

    