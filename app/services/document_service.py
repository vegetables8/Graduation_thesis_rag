import json
from pathlib import Path
from uuid import uuid4

from flask import current_app
from werkzeug.utils import secure_filename

from app import db
from app.models import Document, DocumentChunk
from app.services.audit_service import write_audit_log
from app.services.vector_service import vector_store
from app.utils.file_parser import parse_document
from app.utils.text_chunker import split_text


class DocumentService:
    """负责文档上传、解析、索引、重建索引等流程。"""

    @staticmethod
    def allowed_file(filename: str) -> bool:
        if "." not in filename:
            return False
        ext = filename.rsplit(".", 1)[1].lower()
        return ext in current_app.config["ALLOWED_EXTENSIONS"]

    @staticmethod
    def save_upload(file_storage, current_user) -> Document:
        """保存上传文件并写入数据库。"""

        original_name = file_storage.filename
        safe_name = secure_filename(original_name)
        ext = safe_name.rsplit(".", 1)[1].lower()
        unique_name = f"{uuid4().hex}.{ext}"
        storage_path = Path(current_app.config["UPLOAD_FOLDER"]) / unique_name

        file_storage.save(storage_path)

        document = Document(
            filename=unique_name,
            original_name=original_name,
            file_ext=ext,
            storage_path=str(storage_path),
            uploaded_by_id=current_user.id,
            status="uploaded",
        )
        db.session.add(document)
        db.session.commit()

        write_audit_log(
            user=current_user,
            action="document_upload",
            target_type="document",
            target_id=document.id,
            detail=f"上传文件：{original_name}",
        )
        return document

    @staticmethod
    def parse_and_index(document: Document, current_user) -> dict:
        """解析文档并写入 ChromaDB。"""

        text = parse_document(document.storage_path).strip()
        if not text:
            document.status = "empty"
            db.session.commit()
            raise ValueError("课题资料解析结果为空，无法建立索引。")

        parsed_path = Path(current_app.config["PARSED_FOLDER"]) / f"{document.filename}.txt"
        parsed_path.write_text(text, encoding="utf-8")

        chunks = split_text(
            text,
            chunk_size=current_app.config["CHUNK_SIZE"],
            overlap=current_app.config["CHUNK_OVERLAP"],# 关键，确保不重叠，两个大写参数均为默认值
        )
        if not chunks:
            raise ValueError("课题资料分块失败，未得到有效片段。")

        # 重新索引时先删除旧数据，避免向量和数据库重复。
        vector_store.delete_by_document(document.id)
        DocumentChunk.query.filter_by(document_id=document.id).delete()

        ids = []
        docs = []
        metadatas = []

        for index, chunk in enumerate(chunks):
            chunk_id = f"doc-{document.id}-chunk-{index}"
            meta = {
                "document_id": document.id,
                "document_name": document.original_name,
                "chunk_index": index,
            }
            ids.append(chunk_id)
            docs.append(chunk)
            metadatas.append(meta)

            db.session.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=index,
                    chunk_id=chunk_id,
                    content=chunk,
                    meta_json=json.dumps(meta, ensure_ascii=False),
                )
            )

        vector_store.add_chunks(ids=ids, documents=docs, metadatas=metadatas)

        document.text_path = str(parsed_path)
        document.content_length = len(text)
        document.chunk_count = len(chunks)
        document.status = "indexed"
        db.session.commit()

        write_audit_log(
            user=current_user,
            action="document_index",
            target_type="document",
            target_id=document.id,
            detail=f"完成解析与索引，分块数量：{len(chunks)}",
        )

        return {
            "document": document.to_dict(),
            "chunk_count": len(chunks),
        }


    @staticmethod
    def delete_document(document: Document, current_user) -> dict:
        """删除文档及其关联数据（分块、向量、磁盘文件）。"""

        doc_id = document.id
        doc_name = document.original_name

        # 1. 删除 ChromaDB 中的向量数据
        try:
            vector_store.delete_by_document(doc_id)
        except Exception:
            pass  # ChromaDB 中可能没有数据，忽略错误

        # 2. 删除磁盘上的上传文件和解析文件
        for path_attr in ("storage_path", "text_path"):
            file_path = getattr(document, path_attr, None)
            if file_path:
                try:
                    Path(file_path).unlink(missing_ok=True)
                except OSError:
                    pass

        # 3. 删除数据库记录（级联删除 DocumentChunk）
        db.session.delete(document)
        db.session.commit()

        write_audit_log(
            user=current_user,
            action="document_delete",
            target_type="document",
            target_id=doc_id,
            detail=f"删除课题资料：{doc_name}",
        )

        return {"deleted_id": doc_id, "original_name": doc_name}

    @staticmethod
    def batch_delete_documents(document_ids: list[int], current_user) -> dict:
        """批量删除文档。"""

        documents = Document.query.filter(Document.id.in_(document_ids)).all()
        if not documents:
            raise ValueError("未找到需要删除的课题资料。")

        deleted = []
        for doc in documents:
            result = DocumentService.delete_document(doc, current_user)
            deleted.append(result)

        write_audit_log(
            user=current_user,
            action="document_batch_delete",
            target_type="document",
            detail=f"批量删除 {len(deleted)} 个文档",
        )

        return {"deleted_count": len(deleted), "deleted": deleted}

    @staticmethod
    def reindex_document(document: Document, current_user) -> dict:
        """重新解析并索引文档（适用于分块参数变更或数据修复）。"""

        # 清理旧向量和分块
        try:
            vector_store.delete_by_document(document.id)
        except Exception:
            pass
        DocumentChunk.query.filter_by(document_id=document.id).delete()

        # 重新解析
        text = parse_document(document.storage_path).strip()
        if not text:
            document.status = "empty"
            db.session.commit()
            raise ValueError("课题资料解析结果为空，无法重建索引。")

        # 更新解析文件
        parsed_path = Path(current_app.config["PARSED_FOLDER"]) / f"{document.filename}.txt"
        parsed_path.write_text(text, encoding="utf-8")

        # 重新分块
        chunks = split_text(
            text,
            chunk_size=current_app.config["CHUNK_SIZE"],
            overlap=current_app.config["CHUNK_OVERLAP"],
        )
        if not chunks:
            raise ValueError("课题资料分块失败，未得到有效片段。")

        # 写入新的向量和分块记录
        ids, docs, metadatas = [], [], []
        for index, chunk in enumerate(chunks):
            chunk_id = f"doc-{document.id}-chunk-{index}"
            meta = {
                "document_id": document.id,
                "document_name": document.original_name,
                "chunk_index": index,
            }
            ids.append(chunk_id)
            docs.append(chunk)
            metadatas.append(meta)
            db.session.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=index,
                    chunk_id=chunk_id,
                    content=chunk,
                    meta_json=json.dumps(meta, ensure_ascii=False),
                )
            )

        vector_store.add_chunks(ids=ids, documents=docs, metadatas=metadatas)

        document.text_path = str(parsed_path)
        document.content_length = len(text)
        document.chunk_count = len(chunks)
        document.status = "indexed"
        db.session.commit()

        write_audit_log(
            user=current_user,
            action="document_reindex",
            target_type="document",
            target_id=document.id,
            detail=f"重建索引完成，分块数量：{len(chunks)}",
        )

        return {
            "document": document.to_dict(),
            "chunk_count": len(chunks),
        }

    @staticmethod
    def get_document_detail(document: Document) -> dict:
        """获取文档详情，包含所有分块信息。"""

        chunks = (
            DocumentChunk.query
            .filter_by(document_id=document.id)
            .order_by(DocumentChunk.chunk_index.asc())
            .all()
        )

        return {
            "document": document.to_dict(),
            "chunks": [
                {
                    "chunk_index": c.chunk_index,
                    "chunk_id": c.chunk_id,
                    "content": c.content,
                    "content_preview": c.content[:200] + ("..." if len(c.content) > 200 else ""),
                }
                for c in chunks
            ],
        }


document_service = DocumentService()
