from functools import wraps

from flask import flash, g, jsonify, redirect, request, session, url_for

from app.models import User
from app.services.audit_service import write_audit_log


def login_required(view_func):
    """要求用户先登录。"""

    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            flash("请先登录系统。", "warning")
            return redirect(url_for("auth.login"))

        user = User.query.get(user_id)
        if not user:
            session.clear()
            flash("登录状态已失效，请重新登录。", "warning")
            return redirect(url_for("auth.login"))

        g.current_user = user
        session["username"] = user.username
        session["role"] = user.role
        return view_func(*args, **kwargs)

    return wrapped_view


def role_required(*allowed_roles):
    """要求用户必须属于指定角色之一。"""

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapped_view(*args, **kwargs):
            current_user = g.current_user
            if current_user.role not in allowed_roles:
                role_names = [User.ROLE_LABELS.get(role, role) for role in allowed_roles]
                write_audit_log(
                    user=current_user,
                    action="permission_denied",
                    target_type="route",
                    detail=(
                        f"访问 {request.path} 被拒绝，"
                        f"当前角色：{current_user.role_label}，"
                        f"允许角色：{'、'.join(role_names)}"
                    ),
                )
                if request.path.startswith("/api"):
                    return (
                        jsonify(
                            {
                                "ok": False,
                                "message": f"当前账号无权执行该操作，允许角色：{'、'.join(role_names)}。",
                            }
                        ),
                        403,
                    )
                flash(
                    f"当前账号无权访问该页面，允许角色：{'、'.join(role_names)}。",
                    "danger",
                )
                return redirect(url_for("main.dashboard"))
            return view_func(*args, **kwargs)

        return wrapped_view

    return decorator
