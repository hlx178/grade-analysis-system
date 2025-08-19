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
    from app.routes import api_bp, auth_bp, main_bp, health_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(health_bp)

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
    # 启动时加载品牌配置（数据库中的 key/value）
    with app.app_context():
        try:
            # 确保 brand_settings 表存在（仅创建此表，不影响其它表）
            from sqlalchemy import inspect as _insp
            from app import db as _db
            if not _insp(_db.engine).has_table('brand_settings'):
                from app.models import BrandSetting as _BrandSetting
                _BrandSetting.__table__.create(_db.engine)
        except Exception:
            pass
        try:
            from app.models import BrandSetting
            kv = BrandSetting.get_map()
            mapping = {
                'BRAND_SCHOOL_NAME': 'school_name',
                'BRAND_SCHOOL_NAME_FULL': 'school_name_full',
                'BRAND_REPORT_SUBTITLE': 'subtitle',
                'BRAND_REPORT_COVER_COLOR': 'cover_color',
                'BRAND_HEADER_TEXT': 'header_text',
                'BRAND_FOOTER_TEXT': 'footer_text',
            }

            for cfg_key, k in mapping.items():
                if k in kv and kv[k] is not None:
                    app.config[cfg_key] = kv[k]
        except Exception:
            pass
            pass

        @app.context_processor
        def inject_brand():
            try:
                name = app.config.get('BRAND_SCHOOL_NAME') or '成绩分析系统'
            except Exception:
                name = '成绩分析系统'
            return { 'brand_school_name': name }


    return app
