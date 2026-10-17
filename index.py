# Index management - create, load and insert
import os
from llama_index.core import Settings, StorageContext, VectorStoreIndex
from llama_index.core import load_index_from_storage, load_indices_from_storage
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from server.utils.file import get_save_dir
from server.stores.strage_context import STORAGE_CONTEXT
from server.ingestion import AdvancedIngestionPipeline
from server.data_loader import load_all_data_documents
from server.models.embedding import create_embedding_model
from config import DEV_MODE, DEFAULT_EMBEDDING_MODEL

class IndexManager:
    def __init__(self, index_name):
        self.index_name: str = index_name
        self.storage_context: StorageContext = STORAGE_CONTEXT
        self.index_id: str = None
        self.index: VectorStoreIndex = None

    def check_index_exists(self):
        # 确保在加载索引之前设置嵌入模型
        if Settings.embed_model is None:
            create_embedding_model(DEFAULT_EMBEDDING_MODEL)
        indices = load_indices_from_storage(self.storage_context)
        print(f"Loaded {len(indices)} indices")
        if len(indices) > 0:
            self.index = indices[0]
            self.index_id = indices[0].index_id
            return True
        else:
            return False

    def init_index(self, nodes):
        self.index = VectorStoreIndex(nodes, 
                                      storage_context=self.storage_context, 
                                      store_nodes_override=True) # note: no nodes in doc store if using vector database, set store_nodes_override=True to add nodes to doc store
        self.index_id = self.index.index_id
        if DEV_MODE:
            self.storage_context.persist()
        print(f"Created index {self.index.index_id}")
        return self.index

    def load_index(self): # Load index from storage, using index_id if available
        # 确保在加载索引之前设置嵌入模型
        if Settings.embed_model is None:
            create_embedding_model(DEFAULT_EMBEDDING_MODEL)
        
        # If index is already loaded (e.g., from check_index_exists), no need to reload
        if self.index is not None:
            print(f"Index {self.index.index_id} already loaded")
            return self.index
        
        # If we have a stored index_id, use it for loading
        if self.index_id is not None:
            self.index = load_index_from_storage(self.storage_context, index_id=self.index_id)
        else:
            # Fallback to loading without index_id (for backward compatibility)
            try:
                self.index = load_index_from_storage(self.storage_context)
            except ValueError as e:
                # If loading fails, try to check if indices exist first
                indices = load_indices_from_storage(self.storage_context)
                if len(indices) > 0:
                    self.index = indices[0]
                    self.index_id = indices[0].index_id
                else:
                    raise ValueError("No indices found in storage context. Please create an index first.") from e
        
        if not DEV_MODE:
            self.index._store_nodes_override = True
        print(f"Loaded index {self.index.index_id}")
        return self.index
    
    def insert_nodes(self, nodes):
        if self.index is None:
            try:
                if self.check_index_exists():
                    self.load_index()
            except Exception as e:
                print(f"Failed to load existing index before insert: {e}")

        if self.index is not None:
            self.index.insert_nodes(nodes=nodes)
            if DEV_MODE:
                self.storage_context.persist()
            print(f"Inserted {len(nodes)} nodes into index {self.index.index_id}")
        else:
            self.init_index(nodes=nodes)
        return self.index

    # Build index based on documents under 'data' folder（PDF/文本 + JSON 企业档案）
    def load_dir(self, input_dir, chunk_size, chunk_overlap, progress_callback=None):
        Settings.chunk_size = chunk_size
        Settings.chunk_overlap = chunk_overlap
        
        if progress_callback:
            progress_callback({
                "stage": "loading",
                "progress": 0,
                "message": "开始加载文档...",
                "processed_docs": 0,
                "total_docs": 0
            })
        
        documents = load_all_data_documents(input_dir)
        
        if len(documents) > 0:
            if progress_callback:
                progress_callback({
                    "stage": "loading",
                    "progress": 20,
                    "message": f"成功加载 {len(documents)} 个文档",
                    "processed_docs": 0,
                    "total_docs": len(documents)
                })
            
            pipeline = AdvancedIngestionPipeline()
            nodes = pipeline.run(documents=documents, progress_callback=progress_callback)
            
            if progress_callback:
                progress_callback({
                    "stage": "indexing",
                    "progress": 80,
                    "message": "正在插入向量索引...",
                    "processed_docs": len(documents),
                    "total_docs": len(documents)
                })
            
            index = self.insert_nodes(nodes)
            
            if progress_callback:
                progress_callback({
                    "stage": "completed",
                    "progress": 100,
                    "message": "向量库重建完成",
                    "processed_docs": len(documents),
                    "total_docs": len(documents)
                })
            
            return nodes
        else:
            if progress_callback:
                progress_callback({
                    "stage": "completed",
                    "progress": 100,
                    "message": "未找到文档",
                    "processed_docs": 0,
                    "total_docs": 0
                })
            print("No documents found")
            return []

    def load_data_directory(self, chunk_size, chunk_overlap, input_dir=None, progress_callback=None):
        """索引整个 data 目录：递归扫描 PDF/Office/文本 + 全部 JSON（如 enterprise_data.json）。"""
        target = input_dir if input_dir else get_save_dir()
        return self.load_dir(target, chunk_size, chunk_overlap, progress_callback=progress_callback)
        
    # get file's directory and create index
    def load_files(self, uploaded_files, chunk_size, chunk_overlap):
        Settings.chunk_size = chunk_size
        Settings.chunk_overlap = chunk_overlap
        save_dir = get_save_dir()
        files = [os.path.join(save_dir, file["name"]) for file in uploaded_files]
        print(files)
        documents = SimpleDirectoryReader(input_files=files).load_data()
        if len(documents) > 0:
            pipeline = AdvancedIngestionPipeline()
            nodes = pipeline.run(documents=documents)
            index = self.insert_nodes(nodes)
            return nodes
        else:         
            print("No documents found")
            return []
        
    # Get URL and create index
    # https://docs.llamaindex.ai/en/stable/examples/data_connectors/WebPageDemo/
    def load_websites(self, websites, chunk_size, chunk_overlap):
        Settings.chunk_size = chunk_size
        Settings.chunk_overlap = chunk_overlap

        from server.readers.beautiful_soup_web import BeautifulSoupWebReader
        documents = BeautifulSoupWebReader().load_data(websites)        
        if len(documents) > 0:
            pipeline = AdvancedIngestionPipeline()
            nodes = pipeline.run(documents=documents)
            index = self.insert_nodes(nodes)
            return nodes
        else:
            print("No documents found")
            return []
    
    # Delete a document and all related nodes
    def delete_ref_doc(self, ref_doc_id):
        self.index.delete_ref_doc(ref_doc_id=ref_doc_id, delete_from_docstore=True)
        self.storage_context.persist()
        print("Deleted document", ref_doc_id)
