from __future__ import annotations

from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from app import db


class TimestampMixin:
    """为多个表复用的时间字段混入类。"""

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class User(TimestampMixin, db.Model):
    """系统用户表。"""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="student")
    last_login_at = db.Column(db.DateTime)

    documents = db.relationship("Document", back_populates="uploader", lazy=True)
    query_histories = db.relationship("QueryHistory", back_populates="user", lazy=True)
    search_histories = db.relationship("SearchHistory", back_populates="user", lazy=True)
    audit_logs = db.relationship("AuditLog", back_populates="user", lazy=True)

    ROLE_LABELS = {
        "student": "学生",
        "topic_admin": "课题管理员",
        "academic_admin": "教务管理员",
        "audit_admin": "审计管理员",
    }

    @property
    def role_label(self) -> str:
        """返回中文角色名，方便模板直接展示。"""

        return self.ROLE_LABELS.get(self.role, self.role)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "role_label": self.role_label,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "last_login_at": self.last_login_at.strftime("%Y-%m-%d %H:%M:%S")
            if self.last_login_at
            else "",
        }

    @classmethod
    def bootstrap_default_users(cls, app) -> None:
        """
        启动时初始化默认账号。

        这样用户克隆项目后无需手动插入 SQL，直接启动即可登录演示。
        """

        default_accounts = [
            (
                app.config["DEFAULT_STUDENT_USERNAME"],
                app.config["DEFAULT_STUDENT_PASSWORD"],
                "student",
            ),
            (
                app.config["DEFAULT_TOPIC_ADMIN_USERNAME"],
                app.config["DEFAULT_TOPIC_ADMIN_PASSWORD"],
                "topic_admin",
            ),
            (
                app.config["DEFAULT_ACADEMIC_ADMIN_USERNAME"],
                app.config["DEFAULT_ACADEMIC_ADMIN_PASSWORD"],
                "academic_admin",
            ),
            (
                app.config["DEFAULT_AUDIT_ADMIN_USERNAME"],
                app.config["DEFAULT_AUDIT_ADMIN_PASSWORD"],
                "audit_admin",
            ),
        ]

        created = False
        for username, password, role in default_accounts:
            user = cls.query.filter_by(username=username).first()
            if user:
                continue
            user = cls(username=username, role=role)
            user.set_password(password)
            db.session.add(user)
            created = True

        if created:
            db.session.commit()


class Document(TimestampMixin, db.Model):
    """文档主表，记录上传文件及索引状态。"""

    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    file_ext = db.Column(db.String(20), nullable=False)
    storage_path = db.Column(db.String(500), nullable=False)
    text_path = db.Column(db.String(500), nullable=True)
    content_length = db.Column(db.Integer, default=0)
    chunk_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(30), default="uploaded", nullable=False)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    uploader = db.relationship("User", back_populates="documents")
    chunks = db.relationship(
        "DocumentChunk",
        back_populates="document",
        lazy=True,
        cascade="all, delete-orphan",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "filename": self.filename,
            "original_name": self.original_name,
            "file_ext": self.file_ext,
            "content_length": self.content_length,
            "chunk_count": self.chunk_count,
            "status": self.status,
            "uploaded_by": self.uploader.username if self.uploader else "",
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }


class DocumentChunk(TimestampMixin, db.Model):
    """文档分块表，用于和 Chroma 中的 chunk_id 对应。"""

    __tablename__ = "document_chunks"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    chunk_index = db.Column(db.Integer, nullable=False)
    chunk_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    meta_json = db.Column(db.Text, nullable=True)

    document = db.relationship("Document", back_populates="chunks")


class QueryHistory(TimestampMixin, db.Model):
    """RAG 问答历史。"""

    __tablename__ = "query_histories"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    retrieved_context = db.Column(db.Text, nullable=True)
    reference_documents = db.Column(db.Text, nullable=True)

    user = db.relationship("User", back_populates="query_histories")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "question": self.question,
            "answer": self.answer,
            "retrieved_context": self.retrieved_context or "",
            "reference_documents": self.reference_documents or "",
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }


class SearchHistory(TimestampMixin, db.Model):
    """语义检索历史。"""

    __tablename__ = "search_histories"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    keyword = db.Column(db.Text, nullable=False)
    top_k = db.Column(db.Integer, default=5)
    results_json = db.Column(db.Text, nullable=True)

    user = db.relationship("User", back_populates="search_histories")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "keyword": self.keyword,
            "top_k": self.top_k,
            "results_json": self.results_json or "",
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }


class AuditLog(TimestampMixin, db.Model):
    """审计日志表，记录登录、上传、索引、权限变更等关键行为。"""

    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    username_snapshot = db.Column(db.String(50), nullable=True)
    action = db.Column(db.String(100), nullable=False, index=True)
    target_type = db.Column(db.String(50), nullable=True)
    target_id = db.Column(db.String(50), nullable=True)
    detail = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(100), nullable=True)

    user = db.relationship("User", back_populates="audit_logs")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username_snapshot or "系统",
            "action": self.action,
            "target_type": self.target_type or "",
            "target_id": self.target_id or "",
            "detail": self.detail or "",
            "ip_address": self.ip_address or "",
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
