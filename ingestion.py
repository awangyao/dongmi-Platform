# Import pipeline IngestionPipeline
# https://docs.llamaindex.ai/en/stable/api_reference/ingestion/
# https://docs.llamaindex.ai/en/stable/examples/ingestion/advanced_ingestion_pipeline/

from llama_index.core import Settings
from llama_index.core.ingestion import IngestionPipeline, DocstoreStrategy
from server.splitters import ChineseTitleExtractor
from server.stores.strage_context import STORAGE_CONTEXT
from server.stores.ingestion_cache import INGESTION_CACHE

class AdvancedIngestionPipeline(IngestionPipeline):
    def __init__(
        self, 
    ):
        # Initialize the embedding model, text splitter
        embed_model = Settings.embed_model
        text_splitter = Settings.text_splitter

        # Call the super class's __init__ method with the necessary arguments
        super().__init__(
            transformations=[
                text_splitter,
                embed_model,
                ChineseTitleExtractor(), # modified Chinese title enhance: zh_title_enhance
            ],
            docstore=STORAGE_CONTEXT.docstore,
            vector_store=STORAGE_CONTEXT.vector_store,
            cache=INGESTION_CACHE,
            docstore_strategy=DocstoreStrategy.UPSERTS,  # UPSERTS: Update or insert
        )

    # If you need to override the run method or add new methods, you can do so here
    def run(self, documents, progress_callback=None):
        total_docs = len(documents)
        print(f"Load {total_docs} Documents")
        
        # Process documents in batches to show progress
        batch_size = 10
        processed_docs = 0
        all_nodes = []
        
        for i in range(0, total_docs, batch_size):
            batch = documents[i:i+batch_size]
            batch_nodes = super().run(documents=batch)
            all_nodes.extend(batch_nodes)
            
            processed_docs += len(batch)
            progress = min(100, int((processed_docs / total_docs) * 100))
            
            if progress_callback:
                progress_callback({
                    "stage": "processing",
                    "progress": progress,
                    "message": f"处理文档 {processed_docs}/{total_docs}",
                    "processed_docs": processed_docs,
                    "total_docs": total_docs
                })
            
            print(f"Processed {processed_docs}/{total_docs} documents ({progress}%)")
        
        print(f"Ingested {len(all_nodes)} Nodes")
        return all_nodes