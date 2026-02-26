from indexing.baseline.base_indexer import BaseIndexer
from util.constants import MILVUS_COLLECTION_NAME_BASELINE

class BaselineIndexer(BaseIndexer):
    def index_data(self, data_files, skip_existing=True, re_index=False):
        """
        Index data files using Baseline Indexer.
        
        Args:
            data_files: List of file paths to index
            skip_existing: If True, skip files that are already indexed (default: True)
            re_index: If True, re-index files even if they already exist (default: False)
        """
        print("Indexing data using Baseline Indexer.")
        
        self.createCollectionIfRequired(MILVUS_COLLECTION_NAME_BASELINE)
        
        indexed_count = 0
        skipped_count = 0
        
        for data_file in data_files:
            was_indexed = self.is_file_indexed(data_file, MILVUS_COLLECTION_NAME_BASELINE)
            self.index_file(data_file, MILVUS_COLLECTION_NAME_BASELINE, skip_existing=skip_existing, re_index=re_index)
            
            if was_indexed and skip_existing and not re_index:
                skipped_count += 1
            else:
                indexed_count += 1
        
        print(f"\n✅ Indexing complete: {indexed_count} files indexed, {skipped_count} files skipped")