from indexing.baseline.base_indexer import BaseIndexer
from indexing.versionrag.versionrag_indexer_graph import VersionRAGIndexerGraph
from indexing.versionrag.versionrag_indexer_extract_attributes import extract_attributes_from_file
from indexing.versionrag.versionrag_indexer_clustering import cluster_documentation
from util.chunker import Chunk
from util.constants import MILVUS_COLLECTION_NAME_VERSIONRAG, MILVUS_META_ATTRIBUTE_TYPE, MILVUS_META_ATTRIBUTE_DOCUMENTATION, MILVUS_META_ATTRIBUTE_VERSION, MILVUS_URI
from pymilvus import MilvusClient

class VersionRAGIndexer(BaseIndexer):
    def __init__(self):
        self.graph = VersionRAGIndexerGraph()
        super().__init__()
         
    def index_data(self, data_files):
        files_with_extracted_attributes = self.extract_attributes(data_files)
        print(f"extracted attributes from {len(files_with_extracted_attributes)} files")
                
        # cluster documentations
        cluster_documentation(files_with_extracted_attributes)
        print("clustered documentations")
            
        # basic graph structure
        self.graph.generate_basic_graph(files_with_extracted_attributes)
        print("basic graph generated")
            
        # change level construction
        self.graph.generate_change_level()
        print("change level constructed")
        
        # content indexing
        content_nodes = self.graph.get_all_content_nodes_with_context()
        change_nodes = self.graph.get_all_change_nodes_with_context()
        self.index_content(content_nodes=content_nodes, change_nodes=change_nodes)
        print("content indexed")
            
    def index_content(self, content_nodes: list, change_nodes: list, skip_existing=True, re_index=False):
        """
        Index content and change nodes to Milvus.
        
        Args:
            content_nodes: List of content nodes from graph
            change_nodes: List of change nodes from graph
            skip_existing: If True, skip files that are already indexed (default: True)
            re_index: If True, re-index files even if they already exist (default: False)
        """
        self.createCollectionIfRequired(MILVUS_COLLECTION_NAME_VERSIONRAG)
        
        indexed_count = 0
        skipped_count = 0
        
        for content_node in content_nodes:
            was_indexed = self.is_file_indexed(content_node["file"], MILVUS_COLLECTION_NAME_VERSIONRAG)
            self.index_file(data_file=content_node["file"], 
                            collection_name=MILVUS_COLLECTION_NAME_VERSIONRAG, 
                            category=content_node["category"],
                            documentation=content_node["documentation"],
                            version=content_node["version"],
                            skip_existing=skip_existing,
                            re_index=re_index)
            
            if was_indexed and skip_existing and not re_index:
                skipped_count += 1
            else:
                indexed_count += 1
        
        # For change nodes, we need to check if changes for this version already exist
        # Note: Changes are tied to version, so we check by version + documentation + category
        for change_node in change_nodes:
            # Check if changes for this version already exist
            if skip_existing and not re_index:
                # Query to check if changes exist for this version
                try:
                    if self.client is None:
                        self.client = MilvusClient(MILVUS_URI)
                    # Escape strings for Milvus filter
                    escaped_doc = change_node["documentation"].replace('\\', '\\\\').replace('"', '\\"')
                    escaped_version = change_node["version"].replace('\\', '\\\\').replace('"', '\\"')
                    existing_changes = self.client.query(
                        collection_name=MILVUS_COLLECTION_NAME_VERSIONRAG,
                        filter=f'{MILVUS_META_ATTRIBUTE_TYPE} == "change" and {MILVUS_META_ATTRIBUTE_DOCUMENTATION} == "{escaped_doc}" and {MILVUS_META_ATTRIBUTE_VERSION} == "{escaped_version}"',
                        output_fields=[MILVUS_META_ATTRIBUTE_VERSION],
                        limit=1
                    )
                    if len(existing_changes) > 0:
                        print(f"Skipping changes for version {change_node['version']} (already indexed)")
                        continue
                except Exception as e:
                    print(f"Warning: Could not check existing changes: {e}")
            
            chunk_text = change_node["name"]
            description = change_node.get("description")
            if description:
                chunk_text += "\n" + description
            self.index_chunk(chunk=Chunk(chunk=chunk_text, page=-1),
                             collection_name=MILVUS_COLLECTION_NAME_VERSIONRAG, 
                             category=change_node["category"],
                             documentation=change_node["documentation"],
                             version=change_node["version"],
                             file=change_node["file"],
                             type="change")
            
    def extract_attributes(self, data_files):
        """Extract metadata (version, documentation, type, etc.) from each file via LLM."""
        files_with_extracted_attributes = []
        for data_file in data_files:
            try:
                # Let the extractor infer category from the file path when not provided.
                attributes = extract_attributes_from_file(data_file=data_file)
                print(attributes)
                files_with_extracted_attributes.append(attributes)
            except Exception as e:
                raise ValueError(f"attribute extraction of file {data_file} failed: {e}")
        return files_with_extracted_attributes
        
            