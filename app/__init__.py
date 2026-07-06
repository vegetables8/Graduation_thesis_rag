import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# 加载环境变量 —— 显式指定项目根目录下的 .env 文件。
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)

from config import config_map


# 数据库扩展对象，供全项目共享。
db = SQLAlchemy()


def create_app(config_name: str = None) -> Flask:
    """
    应用工厂。

    使用工厂模式可以让项目结构更清晰，也方便课程设计答辩时说明：
    “配置、扩展、蓝图注册都在统一入口集中管理”。
    """

    app = Flask(
        __name__,
        instance_relative_config=True,
        static_folder="static",
        template_folder="templates",
    )

    selected_config = config_name or os.getenv("FLASK_ENV", "development")
    app.config.from_object(config_map.get(selected_config, config_map["development"]))

    # 确保关键目录存在，避免首次运行时报错。
    _ensure_directories(app)

    db.init_app(app)

    with app.app_context():
        from app.models import User
        from app.routes import register_blueprints
        from app.services.audit_service import write_audit_log

        # 启动时检查关键配置，提前给出明确提示而非运行时才报错。
        _validate_config_on_startup(app)

        register_blueprints(app)
        db.create_all()
        User.bootstrap_default_users(app)
        write_audit_log(
            action="system_startup",
            target_type="system",
            detail="应用初始化完成，SQLite 已自动建表，默认 4 类角色账号已检查。",
        )

    return app


def _validate_config_on_startup(app: Flask) -> None:
    """启动时校验关键配置，避免运行时才发现 API Key 缺失等问题。"""

    import logging

    logger = logging.getLogger(__name__)

    api_key = (app.config.get("LLM_API_KEY") or "").strip()
    if not api_key:
        logger.warning(
            "⚠ 未配置 LLM_API_KEY！请在 .env 文件中设置 LLM_API_KEY，"
            "或在 config.py 中设置默认值。语义检索和 RAG 问答将无法正常工作。"
        )
    elif len(api_key) < 10:
        logger.warning(
            "⚠ LLM_API_KEY 长度过短（< 10 字符），可能不是有效的 API Key，请检查配置。"
        )
    else:
        logger.info("✅ LLM_API_KEY 已配置（%d 字符），格式检查通过。", len(api_key))

    embedding_model = app.config.get("EMBEDDING_MODEL", "")
    logger.info("📐 Embedding 模型：%s", embedding_model)
    logger.info("🤖 LLM 模型：%s", app.config.get("LLM_MODEL", ""))
    logger.info("📂 ChromaDB 目录：%s", app.config.get("CHROMA_DIR", ""))


def _ensure_directories(app: Flask) -> None:
    """保证运行依赖目录存在。"""

    folders = [
        app.config["UPLOAD_FOLDER"],
        app.config["PARSED_FOLDER"],
        app.config["CHROMA_DIR"],
        app.config["INSTANCE_DIR"],
    ]

    for folder in folders:
        Path(folder).mkdir(parents=True, exist_ok=True)
