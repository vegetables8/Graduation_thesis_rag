from flask import Blueprint, g, jsonify, request

from app import db
from app.decorators import role_required
from app.models import AuditLog, User
from app.services.audit_service import write_audit_log


admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/api/admin/users", methods=["GET"])
@role_required("academic_admin")
def list_users():
    """权限管理员查看用户列表。"""

    items = [user.to_dict() for user in User.query.order_by(User.id.asc()).all()]
    return jsonify({"ok": True, "items": items})


@admin_bp.route("/api/admin/users/<int:user_id>/role", methods=["PUT"])
@role_required("academic_admin")
def update_user_role(user_id: int):
    """权限管理员更新角色，且角色值只能是固定 4 类之一。"""

    current_user = g.current_user
    payload = request.get_json(silent=True) or {}
    role = (payload.get("role") or "").strip()

    if role not in User.ROLE_LABELS:
        return jsonify({"ok": False, "message": "角色值非法，仅允许 4 类固定角色。"}), 400

    user = User.query.get_or_404(user_id)
    old_role = user.role
    user.role = role
    db.session.commit()

    write_audit_log(
        user=current_user,
        action="role_update",
        target_type="user",
        target_id=user.id,
        detail=(
            f"将用户 {user.username} 的角色从 "
            f"{User.ROLE_LABELS.get(old_role, old_role)} 修改为 "
            f"{User.ROLE_LABELS.get(role, role)}"
        ),
    )
    return jsonify({"ok": True, "message": "角色更新成功。"})


@admin_bp.route("/api/audits", methods=["GET"])
@role_required("audit_admin")
def audit_list():
    """审计管理员查看系统审计日志。"""

    items = [
        item.to_dict()
        for item in AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()
    ]
    return jsonify({"ok": True, "items": items})
