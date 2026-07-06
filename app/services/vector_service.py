import chromadb
from flask import current_app

from app.services.zhipu_embedding import ZhipuEmbeddingFunction


class VectorStoreService:
    """
    ChromaDB 向量服务封装。

    这里专门将 ChromaDB 的创建、写入、查询独立出来，
    便于后续替换 Milvus、FAISS 或其他向量数据库。

    向量化实现：
    - 使用智谱 AI Embedding API 进行向量化
    - 替代本地 sentence-transformers（依赖 torch，在某些环境下有 DLL 问题）
    """

    def __init__(self):
        self._client = None
        self._collection = None

    @property
    def collection(self):
        """延迟初始化集合，避免模块导入时直接加载模型。"""

        if self._collection is None:
            embedding_function = ZhipuEmbeddingFunction(
                model=current_app.config["EMBEDDING_MODEL"]
            )
            self._client = chromadb.PersistentClient(
                path=current_app.config["CHROMA_DIR"]
            )
            self._collection = self._client.get_or_create_collection(
                name=current_app.config["CHROMA_COLLECTION"],
                embedding_function=embedding_function,
                metadata={"description": "毕设选题指南库"},
            )
        return self._collection

    def add_chunks(self, ids: list[str], documents: list[str], metadatas: list[dict]) -> None:
        """批量写入分块数据。"""

        if not ids:
            return
        self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    def delete_by_document(self, document_id: int) -> None:
        """按文档编号删除旧向量，便于重新索引。"""

        self.collection.delete(where={"document_id": document_id})

    def query(self, text: str, top_k: int = 5) -> list[dict]:
        """执行语义检索并整理为前端易消费的数据结构。"""

        result = self.collection.query(
            query_texts=[text],
            n_results=top_k,
        )

        # 处理空结果的情况
        documents_list = result.get("documents", [])
        metadatas_list = result.get("metadatas", [])
        distances_list = result.get("distances", [])
        ids_list = result.get("ids", [])
        
        documents = documents_list[0] if documents_list else []
        metadatas = metadatas_list[0] if metadatas_list else []
        distances = distances_list[0] if distances_list else []
        ids = ids_list[0] if ids_list else []

        rows = []
        for index, content in enumerate(documents):
            metadata = metadatas[index] if index < len(metadatas) else {}
            distance = distances[index] if index < len(distances) else None
            score = round(1 - distance, 4) if distance is not None else None
            rows.append(
                {
                    "chunk_id": ids[index] if index < len(ids) else "",
                    "content": content,
                    "score": score,
                    "metadata": metadata,
                }
            )
        return rows


vector_store = VectorStoreService()
