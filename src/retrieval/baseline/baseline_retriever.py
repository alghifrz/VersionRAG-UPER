from retrieval.baseline.base_retriever import BaseRetriever, RetrievedData
# from pymilvus import MilvusClient
# from util.constants import MILVUS_URI, MILVUS_COLLECTION_NAME_BASELINE, MILVUS_META_ATTRIBUTE_TEXT, MILVUS_META_ATTRIBUTE_PAGE, MILVUS_META_ATTRIBUTE_FILE, MILVUS_BASELINE_SOURCE_COUNT
from util.constants import MILVUS_COLLECTION_NAME_BASELINE, MILVUS_META_ATTRIBUTE_TEXT, MILVUS_META_ATTRIBUTE_PAGE, MILVUS_META_ATTRIBUTE_FILE, MILVUS_BASELINE_SOURCE_COUNT
from util.embedding_client import get_embedding_client
from util.milvus_client_factory import get_milvus_client
from dotenv import load_dotenv
load_dotenv()

class BaselineRetriever(BaseRetriever):
    def __init__(self):
        self.embedding_fn = get_embedding_client()
        self.client = None
        super().__init__()

    def retrieve(self, query):
        if self.client is None:
            # self.client = MilvusClient(MILVUS_URI)
            self.client = get_milvus_client()

        # Friendly behavior when the user hasn't indexed anything yet.
        try:
            if not self.client.has_collection(collection_name=MILVUS_COLLECTION_NAME_BASELINE):
                return RetrievedData("no data indexed")
        except Exception:
            # If Milvus isn't reachable / misconfigured, let the caller surface a clear error.
            # (We avoid swallowing the root cause here.)
            raise
        
        query_vectors = self.embedding_fn.encode_queries([query])

        res = self.client.search(
            collection_name=MILVUS_COLLECTION_NAME_BASELINE,  # target collection
            data=query_vectors,  # query vectors
            limit=MILVUS_BASELINE_SOURCE_COUNT,  # number of returned entities
            output_fields=[MILVUS_META_ATTRIBUTE_TEXT, MILVUS_META_ATTRIBUTE_PAGE, MILVUS_META_ATTRIBUTE_FILE],  # specifies fields to be returned
        )

        results = res[0]
        chunks = [hit["entity"][MILVUS_META_ATTRIBUTE_TEXT] for hit in results]
        page_nrs = [hit["entity"][MILVUS_META_ATTRIBUTE_PAGE] for hit in results]
        source_files = [hit["entity"][MILVUS_META_ATTRIBUTE_FILE] for hit in results]
        
        return RetrievedData(chunks, page_nrs, source_files)