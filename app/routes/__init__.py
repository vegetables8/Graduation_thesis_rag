from app.routes.admin import admin_bp
from app.routes.auth import auth_bp
from app.routes.main import main_bp


def register_blueprints(app):
    """统一注册蓝图。"""

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
