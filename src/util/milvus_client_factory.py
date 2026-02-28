from pymilvus import MilvusClient

from util.constants import MILVUS_URI, MILVUS_TOKEN


def get_milvus_client(uri: str | None = None, token: str | None = None) -> MilvusClient:
    """
    Create a Milvus client from centralized settings.

    - Local/self-hosted Milvus: set MILVUS_URI only.
    - Zilliz Cloud: set MILVUS_URI and MILVUS_TOKEN.
    """
    resolved_uri = uri or MILVUS_URI
    resolved_token = token if token is not None else MILVUS_TOKEN

    kwargs = {"uri": resolved_uri}
    if resolved_token:
        kwargs["token"] = resolved_token

    return MilvusClient(**kwargs)


