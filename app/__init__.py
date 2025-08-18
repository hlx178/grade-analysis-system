"""
成绩分析系统应用工厂
"""

from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

from config import config

# 初始化扩展
db = SQLAlchemy()
login_manager = LoginManager()


def create_app(config_name="default"):
    """应用工厂函数"""
    app = Flask(__name__)

    # 加载配置
    app.config.from_object(config[config_name])

    # 初始化扩展
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "请先登录以访问此页面。"
    login_manager.login_message_category = "info"

    # 注册蓝图
    from app.routes import api_bp, auth_bp, main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(api_bp, url_prefix="/api")

    # 慢查询日志（开发/生产均可开启）
    import logging, time
    from flask import g, request

    @app.before_request
    def _start_timer():
        g._t0 = time.time()

    @app.after_request
    def _log_slow(response):
        try:
            t = (time.time() - getattr(g, '_t0', time.time())) * 1000
            threshold = app.config.get('SLOW_QUERY_MS', 500)
            if t >= threshold:
                logging.getLogger('slow').warning(f"SLOW {int(t)}ms {request.method} {request.path}")
        except Exception:
            pass
        return response

    # 用户加载回调
    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User

        return User.query.get(int(user_id))

    return app
