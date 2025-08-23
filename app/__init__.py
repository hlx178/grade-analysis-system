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

    # 结构化日志 & 慢请求
    import logging, time, json, sys
    from flask import g, request

    # 基础 logging 配置
    root_level = getattr(logging, app.config.get('LOG_LEVEL','INFO').upper(), logging.INFO)
    logging.basicConfig(level=root_level, stream=sys.stdout)

    def _json_log(logger_name, level, **fields):
        try:
            if app.config.get('LOG_FORMAT_JSON', True):
                fields.setdefault('ts', int(time.time()*1000))
                fields.setdefault('app', 'gas')
                fields.setdefault('level', logging.getLevelName(level))
                msg = json.dumps(fields, ensure_ascii=False)
            else:
                msg = f"{fields}"
            logging.getLogger(logger_name).log(level, msg)
        except Exception:
            pass

    @app.before_request
    def _start_timer():
        g._t0 = time.time()

    @app.after_request
    def _log_slow(response):
        try:
            t = (time.time() - getattr(g, '_t0', time.time())) * 1000
            threshold = app.config.get('SLOW_QUERY_MS', 500)
            if t >= threshold:
                _json_log('slow', logging.WARNING,
                          kind='slow', latency_ms=int(t), method=request.method, path=request.path, status=response.status_code)
        except Exception:
            pass
        return response

    if app.config.get('LOG_ACCESS', True):
        @app.after_request
        def _access_log(response):
            try:
                from flask_login import current_user as _cu
                uid = _cu.id if getattr(_cu, 'is_authenticated', False) and _cu.is_authenticated else None
                role = getattr(_cu, 'role', None) if uid else None
                t = (time.time() - getattr(g, '_t0', time.time())) * 1000
                _json_log('access', logging.INFO,
                          kind='access', latency_ms=int(t), method=request.method, path=request.path,
                          status=response.status_code, user_id=uid, role=role)
            except Exception:
                pass
            return response

    # 全局异常处理：记录完整栈并对 /api/* 返回 JSON，便于快速定位 500 根因
    @app.errorhandler(Exception)
    def _handle_exception(e):
        try:
            from flask import request, jsonify
            # 结构化错误日志
            _json_log('error', logging.ERROR,
                      kind='exception', path=getattr(request, 'path', None),
                      error=str(e), type=type(e).__name__)
            try:
                import traceback as _tb
                tb = _tb.format_exc()
                _json_log('error', logging.ERROR, traceback=tb)
            except Exception:
                pass
            # API 路径返回 JSON，页面仍走默认错误页面
            if getattr(request, 'path', '') .startswith('/api/'):
                return jsonify({'error': 'internal_error', 'type': type(e).__name__, 'message': str(e)}), 500
        except Exception:
            pass
        return e

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
            # 轻量迁移：如 users 表缺少 student_ref_id 列则添加
            from sqlalchemy import text as _text
            from sqlalchemy import inspect as _insp2
            insp = _insp2(_db.engine)
            if insp.has_table('users'):
                res = _db.engine.execute(_text('PRAGMA table_info(users)')).fetchall()
                cols = {row[1] for row in res} if res else set()
                if 'student_ref_id' not in cols:
                    _db.engine.execute(_text('ALTER TABLE users ADD COLUMN student_ref_id INTEGER'))
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
                'BRAND_SHOW_HEADER': 'show_header',
                'BRAND_SHOW_FOOTER': 'show_footer',
            }
            for cfg_key, k in mapping.items():
                if k in kv and kv[k] is not None:
                    app.config[cfg_key] = kv[k]
        except Exception:
            pass

        @app.context_processor
        def inject_brand():
            try:
                name = app.config.get('BRAND_SCHOOL_NAME') or '成绩分析系统'
            except Exception:
                name = '成绩分析系统'
            # 角色模块权限（用于导航显示）
            try:
                from flask_login import current_user as _cu
                from app.models import RolePermission as _RP
                import json as _json
                def _default_modules(role: str):
                    all_mods = ['students','courses','grades','summary','import','exam_schemes','grade_bands','users','diagnostics','branding','student_analysis','my_scores']
                    if role == 'admin': return set(all_mods)
                    if role == 'teacher': return set(['students','courses','grades','summary','import','my_scores'])
                    if role == 'student': return set(['my_scores','student_analysis'])
                    return set()
                mods = set()
                if _cu.is_authenticated:
                    rp = _RP.query.filter_by(role=_cu.role).first()
                    if rp and rp.modules:
                        try:
                            mods = set(m for m in _json.loads(rp.modules) if isinstance(m, str))
                        except Exception:
                            mods = _default_modules(_cu.role)
                    else:
                        mods = _default_modules(_cu.role)
                return { 'brand_school_name': name, 'allowed_modules': mods }
            except Exception:
                return { 'brand_school_name': name, 'allowed_modules': set() }

        # 确保模型对应的数据表就绪（避免测试环境未导入模型导致缺列）
        try:
            from app import models as _models  # noqa: F401
            db.create_all()
        except Exception:
            pass
        # 启动自检：若无管理员账号则自动创建（密码可由环境变量 ADMIN_INITIAL_PASSWORD 指定，默认 123456）
        try:
            from app.models import User
            from werkzeug.security import generate_password_hash
            import os as _os
            if User.query.filter_by(username='admin').first() is None:
                _pw = _os.environ.get('ADMIN_INITIAL_PASSWORD', '123456')
                _u = User(username='admin', email='admin@example.com', role='admin')
                _u.password_hash = generate_password_hash(_pw)
                db.session.add(_u); db.session.commit()
        except Exception:
            pass

        except Exception:
            pass
        try:
            # 轻量迁移：如 users 表缺少 student_ref_id 列则添加
            from sqlalchemy import text as _text
            from sqlalchemy import inspect as _insp2
            insp = _insp2(_db.engine)
            if insp.has_table('users'):
                res = _db.engine.execute(_text('PRAGMA table_info(users)')).fetchall()
                cols = {row[1] for row in res} if res else set()
                if 'student_ref_id' not in cols:
                    _db.engine.execute(_text('ALTER TABLE users ADD COLUMN student_ref_id INTEGER'))
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
                'BRAND_SHOW_HEADER': 'show_header',
                'BRAND_SHOW_FOOTER': 'show_footer',
            }
            for cfg_key, k in mapping.items():
                if k in kv and kv[k] is not None:
                    app.config[cfg_key] = kv[k]
        except Exception:
            pass

        @app.context_processor
        def inject_brand():
            try:
                name = app.config.get('BRAND_SCHOOL_NAME') or '成绩分析系统'
            except Exception:
                name = '成绩分析系统'
            # 角色模块权限（用于导航显示）
            try:
                from flask_login import current_user as _cu
                from app.models import RolePermission as _RP
                import json as _json
                def _default_modules(role: str):
                    all_mods = ['students','courses','grades','summary','import','exam_schemes','grade_bands','users','diagnostics','branding']
                    if role == 'admin': return set(all_mods)
                    if role == 'teacher': return set(['students','courses','grades','summary','import','exam_schemes','grade_bands'])
                    if role == 'student': return set(['students','grades','summary'])
                    return set()
                mods = set()
                if _cu.is_authenticated:
                    rp = _RP.query.filter_by(role=_cu.role).first()
                    if rp and rp.modules:
                        try:
                            mods = set(m for m in _json.loads(rp.modules) if isinstance(m, str))
                        except Exception:
                            mods = _default_modules(_cu.role)
                    else:
                        mods = _default_modules(_cu.role)
                return { 'brand_school_name': name, 'allowed_modules': mods }
            except Exception:
                return { 'brand_school_name': name, 'allowed_modules': set() }


    return app
