import os
from datetime import timedelta


class Config:
    """应用配置类"""

    # 基础配置
    SECRET_KEY = os.environ.get("SECRET_KEY") or "your-secret-key-here"

    # 诊断与慢查询
    SLOW_QUERY_MS = int(os.environ.get("SLOW_QUERY_MS") or 500)
    DIAG_SQL_LOG = os.environ.get("DIAG_SQL_LOG", "false").lower() in ["1","true","on"]

    # COUNT 微缓存
    SUMMARY_COUNT_TTL_SECONDS = int(os.environ.get("SUMMARY_COUNT_TTL_SECONDS") or 60)

    # 导出目录
    EXPORT_DIR = os.environ.get("EXPORT_DIR") or "exports"
    EXPORT_RETENTION_DAYS = int(os.environ.get("EXPORT_RETENTION_DAYS") or 7)
    EXPORT_MAX_CONCURRENT_PER_USER = int(os.environ.get("EXPORT_MAX_CONCURRENT_PER_USER") or 2)
    DOWNLOAD_LINK_TTL_SECONDS = int(os.environ.get("DOWNLOAD_LINK_TTL_SECONDS") or 3600)

    # 就绪探针阈值（磁盘剩余，单位 MB）
    READY_DISK_FREE_MB = int(os.environ.get("READY_DISK_FREE_MB") or 1024)

    # 数据库配置
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or "sqlite:///grade_analysis.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 会话配置
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)

    # 文件上传配置
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    UPLOAD_FOLDER = "uploads"

    # 分页配置
    POSTS_PER_PAGE = 20

    # 邮件配置（可选）
    MAIL_SERVER = os.environ.get("MAIL_SERVER")
    MAIL_PORT = int(os.environ.get("MAIL_PORT") or 587)
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() in ["true", "on", "1"]
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")


class DevelopmentConfig(Config):
    """开发环境配置"""

    DEBUG = True


class ProductionConfig(Config):
    """生产环境配置"""

    DEBUG = False


class TestingConfig(Config):
    """测试环境配置"""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
