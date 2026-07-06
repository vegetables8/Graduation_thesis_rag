from flask import has_request_context, request

from app import db
from app.models import AuditLog


def write_audit_log(
    action: str,
    target_type: str = "",
    target_id: str = "",
    detail: str = "",
    user=None,
) -> None:
    """
    写入审计日志。

    审计日志是本项目的重要课程设计点之一，用于记录：
    1. 登录 / 退出
    2. 上传 / 解析 / 索引
    3. 检索 / 问答
    4. 权限拒绝 / 角色修改
    """

    ip_address = request.remote_addr if has_request_context() else "127.0.0.1"

    log = AuditLog(
        user_id=getattr(user, "id", None),
        username_snapshot=getattr(user, "username", "系统"),
        action=action,
        target_type=target_type,
        target_id=str(target_id or ""),
        detail=detail,
        ip_address=ip_address,
    )
    db.session.add(log)
    db.session.commit()
