import re
from datetime import datetime

from flask import Blueprint, flash, g, jsonify, redirect, render_template, request, session, url_for

from app import db
from app.models import User
from app.services.audit_service import write_audit_log


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """登录页面与登录提交。"""

    if session.get("user_id"):
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = User.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            write_audit_log(
                action="login_failed",
                target_type="user",
                detail=f"登录失败，用户名：{username}",
            )
            flash("用户名或密码错误。", "danger")
            return render_template("login.html")

        user.last_login_at = datetime.utcnow()
        db.session.commit()
        # 登录成功后，将用户信息存储到会话中
        session["user_id"] = user.id
        session["username"] = user.username
        session["role"] = user.role

        write_audit_log(
            user=user,
            action="login_success",
            target_type="user",
            target_id=user.id,
            detail="用户登录成功。",
        )
        flash("登录成功。", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    """退出登录。"""

    username = session.get("username", "未知用户")
    user = User.query.filter_by(username=username).first()
    if user:
        write_audit_log(
            user=user,
            action="logout",
            target_type="user",
            target_id=user.id,
            detail="用户退出登录。",
        )

    session.clear()
    flash("您已退出登录。", "info")
    return redirect(url_for("auth.login"))


# ---------------------------------------------------------------------------
# 用户注册
# ---------------------------------------------------------------------------


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """用户自助注册页面。"""

    if session.get("user_id"):
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        confirm = request.form.get("confirm_password", "").strip()

        # 校验
        errors = []
        if not username or len(username) < 3 or len(username) > 20:
            errors.append("用户名需为 3-20 个字符。")
        elif not re.match(r"^[a-zA-Z0-9_]+$", username):
            errors.append("用户名仅允许字母、数字和下划线。")
        elif User.query.filter_by(username=username).first():
            errors.append("该用户名已被注册，请更换。")

        if not password or len(password) < 6:
            errors.append("密码至少需要 6 个字符。")
        elif not re.search(r"[a-zA-Z]", password) or not re.search(r"[0-9]", password):
            errors.append("密码需同时包含字母和数字。")
        if password != confirm:
            errors.append("两次输入的密码不一致。")

        if errors:
            for err in errors:
                flash(err, "danger")
            return render_template("register.html")

        # 创建用户
        user = User(username=username, role="student")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        write_audit_log(
            user=user,
            action="user_register",
            target_type="user",
            target_id=user.id,
            detail=f"新用户注册：{username}",
        )

        # 自动登录
        session["user_id"] = user.id
        session["username"] = user.username
        session["role"] = user.role
        flash("注册成功，欢迎加入！", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("register.html")


# ---------------------------------------------------------------------------
# 修改密码
# ---------------------------------------------------------------------------


@auth_bp.route("/change-password", methods=["GET", "POST"])
def change_password():
    """修改密码页面（需登录）。"""

    user_id = session.get("user_id")
    if not user_id:
        flash("请先登录系统。", "warning")
        return redirect(url_for("auth.login"))

    user = User.query.get(user_id)
    if not user:
        session.clear()
        flash("登录状态已失效。", "warning")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        old_password = request.form.get("old_password", "").strip()
        new_password = request.form.get("new_password", "").strip()
        confirm = request.form.get("confirm_password", "").strip()

        errors = []
        if not user.check_password(old_password):
            errors.append("旧密码不正确。")
        if not new_password or len(new_password) < 6:
            errors.append("新密码至少需要 6 个字符。")
        elif not re.search(r"[a-zA-Z]", new_password) or not re.search(r"[0-9]", new_password):
            errors.append("新密码需同时包含字母和数字。")
        if new_password != confirm:
            errors.append("两次输入的新密码不一致。")
        if old_password == new_password:
            errors.append("新密码不能与旧密码相同。")

        if errors:
            for err in errors:
                flash(err, "danger")
            return render_template("change_password.html", user=user)

        user.set_password(new_password)
        db.session.commit()

        write_audit_log(
            user=user,
            action="password_change",
            target_type="user",
            target_id=user.id,
            detail="用户修改密码",
        )

        flash("密码修改成功。", "success")
        return redirect(url_for("main.profile_page"))

    return render_template("change_password.html", user=user)
