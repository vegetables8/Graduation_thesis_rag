import os
from pathlib import Path

from dotenv import load_dotenv

# 这里统一维护项目根目录，后续所有路径都基于它展开，
# 这样无论从哪个位置启动 Flask，都能稳定找到 SQLite、上传目录和 ChromaDB 目录。
BASE_DIR = Path(__file__).resolve().parent

# 加载 .env 文件中的环境变量 —— 显式指定路径，确保无论从哪个目录启动都能正确加载。
load_dotenv(BASE_DIR / ".env")


class BaseConfig:
    """项目基础配置。"""

    # Flask 会话密钥。
    SECRET_KEY = os.getenv("SECRET_KEY", "course-design-secret-key-change-me")
    JSON_AS_ASCII = False

    # SQLite 自动建表所依赖的数据库地址。
    # 使用绝对路径可以避免 Windows 下相对路径解析不一致的问题。
    INSTANCE_DIR = BASE_DIR / "instance"
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URI",
        f"sqlite:///{(INSTANCE_DIR / 'app.db').as_posix()}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 上传目录与解析目录。
    UPLOAD_FOLDER = os.getenv(
        "UPLOAD_FOLDER",
        str(BASE_DIR / "app" / "uploads" / "raw"),
    )
    PARSED_FOLDER = os.getenv(
        "PARSED_FOLDER",
        str(BASE_DIR / "app" / "uploads" / "parsed"),
    )

    # ChromaDB 本地持久化目录。
    CHROMA_DIR = os.getenv(
        "CHROMA_DIR",
        str(BASE_DIR / "app" / "data" / "chroma_db"),
    )
    CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "course_design_documents")

    # 向量嵌入模型。
    # 使用智谱 AI 的 Embedding API 进行向量化
    # 可选模型：embedding-3（推荐，1024维度）、embedding-2（2048维度）
    EMBEDDING_MODEL = os.getenv(
        "EMBEDDING_MODEL",
        "embedding-3",
    )

    # 文本分块参数。
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 500))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 80))
    TOP_K = int(os.getenv("TOP_K", 5))

    # 上传文件限制。
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 20 * 1024 * 1024))
    ALLOWED_EXTENSIONS = {"txt", "md", "pdf", "docx"}

    # 本项目严格固定 4 类角色，不再保留任何多余角色。
    ROLE_OPTIONS = (
        "student",
        "topic_admin",
        "academic_admin",
        "audit_admin",
    )

    # 默认演示账号。项目首次启动后会自动建表并自动补齐这 4 个账号。
    DEFAULT_STUDENT_USERNAME = os.getenv("DEFAULT_STUDENT_USERNAME", "student")
    DEFAULT_STUDENT_PASSWORD = os.getenv("DEFAULT_STUDENT_PASSWORD", "Stu@123")
    DEFAULT_TOPIC_ADMIN_USERNAME = os.getenv(
        "DEFAULT_TOPIC_ADMIN_USERNAME",
        "topic_admin",
    )
    DEFAULT_TOPIC_ADMIN_PASSWORD = os.getenv(
        "DEFAULT_TOPIC_ADMIN_PASSWORD",
        "TopicAdmin@123",
    )
    DEFAULT_ACADEMIC_ADMIN_USERNAME = os.getenv(
        "DEFAULT_ACADEMIC_ADMIN_USERNAME",
        "academic_admin",
    )
    DEFAULT_ACADEMIC_ADMIN_PASSWORD = os.getenv(
        "DEFAULT_ACADEMIC_ADMIN_PASSWORD",
        "AcadAdmin@123",
    )
    DEFAULT_AUDIT_ADMIN_USERNAME = os.getenv(
        "DEFAULT_AUDIT_ADMIN_USERNAME",
        "audit_admin",
    )
    DEFAULT_AUDIT_ADMIN_PASSWORD = os.getenv(
        "DEFAULT_AUDIT_ADMIN_PASSWORD",
        "Audit@123",
    )

    # 真实第三方 HTTP 大模型接口配置。
    # 这里默认对接智谱开放平台 GLM 接口，调用方式为标准 HTTP POST，
    # 不使用 mock、Ollama、Docker 或本地大模型。
    LLM_BASE_URL = os.getenv(
        "LLM_BASE_URL",
        "https://open.bigmodel.cn/api/paas/v4",
    )
    LLM_MODEL = os.getenv("LLM_MODEL", "glm-4-flash")

    # Embedding API 使用与 Chat API 相同的 Base URL（智谱平台统一入口）。
    EMBEDDING_BASE_URL = os.getenv(
        "EMBEDDING_BASE_URL",
        "https://open.bigmodel.cn/api/paas/v4",
    )

    # 按用户要求，config.py 中直接保留用户提供的 Key，便于课程设计演示时直接启动。
    # 若后续更换账号，也可以通过环境变量 LLM_API_KEY / ZHIPUAI_API_KEY 覆盖这里的默认值。
    LLM_API_KEY = os.getenv(
        "LLM_API_KEY",
        os.getenv(
            "ZHIPUAI_API_KEY",
            "5d501da2a88b4be2b7aaa2dc9fb2a9ff.1NBwMu3hMsBXciZr",
        ),
    )
    LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", 60))


class DevelopmentConfig(BaseConfig):
    """开发环境配置。"""

    DEBUG = True


class ProductionConfig(BaseConfig):
    """生产环境配置。"""

    DEBUG = False


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}
