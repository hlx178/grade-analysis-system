#!/usr/bin/env python3
"""
成绩分析系统启动文件
"""

import os

import click
from flask.cli import with_appcontext

from app import create_app, db
from app.models import Course, Grade, Student, User

# 获取配置环境
config_name = os.getenv("FLASK_CONFIG", "development")
app = create_app(config_name)


@app.cli.command()
@with_appcontext
def init_db():
    """初始化数据库"""
    click.echo("正在创建数据库表...")
    db.create_all()
    click.echo("数据库初始化完成!")


@app.cli.command()
@with_appcontext
def create_admin():
    """创建管理员用户"""
    from werkzeug.security import generate_password_hash

    username = click.prompt("管理员用户名", default="admin")
    email = click.prompt("管理员邮箱", default="admin@example.com")
    password = click.prompt("管理员密码", hide_input=True, confirmation_prompt=True)

    admin = User(
        username=username, email=email, password_hash=generate_password_hash(password), role="admin"
    )

    db.session.add(admin)
    db.session.commit()
    click.echo(f"管理员用户 {username} 创建成功!")


@app.cli.command()
@with_appcontext
def init_sample_data():
    """初始化示例数据"""
    click.echo("正在创建示例数据...")

    # 创建示例课程
    courses = [
        Course(name="数学", code="MATH001", description="高等数学"),
        Course(name="英语", code="ENG001", description="大学英语"),
        Course(name="物理", code="PHY001", description="大学物理"),
        Course(name="计算机科学", code="CS001", description="计算机科学导论"),
    ]

    for course in courses:
        db.session.add(course)

    # 创建示例学生
    students = [
        Student(
            student_id="2023001", name="张三", class_name="计算机1班", email="zhangsan@example.com"
        ),
        Student(
            student_id="2023002", name="李四", class_name="计算机1班", email="lisi@example.com"
        ),
        Student(
            student_id="2023003", name="王五", class_name="计算机2班", email="wangwu@example.com"
        ),
        Student(
            student_id="2023004", name="赵六", class_name="计算机2班", email="zhaoliu@example.com"
        ),
    ]

    for student in students:
        db.session.add(student)

    db.session.commit()
    click.echo("示例数据创建完成!")


@app.shell_context_processor
def make_shell_context():
    """Shell上下文处理器"""
    return {"db": db, "User": User, "Student": Student, "Course": Course, "Grade": Grade}


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)
