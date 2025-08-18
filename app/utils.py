"""
工具函数
"""

import numpy as np
import pandas as pd
from sqlalchemy import func

from app.models import Course, Grade, Student, ExamScheme

# 学科列与课程编码映射（可扩展）
SUBJECTS = [
    ("语文", "CN", "语文"),
    ("数学", "MA", "数学"),
    ("英语", "EN", "英语"),
    ("科学", "SC", "科学"),
    ("社会", "SOC", "社会"),
    ("道法", "MOR", "道法"),
]
TOTAL_SUBJECT = ("总分", "TOTAL", "总分")

EXAM_TYPE_MAP = {
    "常规考试": "regular",
    "模拟考试": "mock",
    "regular": "regular",
    "mock": "mock",
}

def normalize_exam_type(exam_type: str) -> str:
    if not exam_type:
        return "regular"
    return EXAM_TYPE_MAP.get(str(exam_type).strip(), "regular")


def ensure_default_exam_scheme(exam_type: str):
    """若该考试类型未配置科目满分，则以默认值创建。
    默认：每科100分，总分为学科数量*100。
    """
    from app import db

    norm = normalize_exam_type(exam_type)
    exists = (
        ExamScheme.query.filter_by(exam_type=norm).first() is not None
    )
    if exists:
        return
    # 创建默认配置
    total = 0
    for _, code, name in SUBJECTS:
        db.session.add(ExamScheme(exam_type=norm, subject_code=code, subject_name=name, max_score=100.0))
        total += 100
    # 总分
    db.session.add(ExamScheme(exam_type=norm, subject_code=TOTAL_SUBJECT[1], subject_name=TOTAL_SUBJECT[2], max_score=float(total)))
    db.session.commit()


def calculate_statistics(grades_query):
    """计算成绩统计信息"""
    scores = [grade.score for grade in grades_query]

    if not scores:
        return {"count": 0, "average": 0, "median": 0, "max": 0, "min": 0, "std": 0, "pass_rate": 0}

    scores_array = np.array(scores)
    pass_count = len([s for s in scores if s >= 60])

    return {
        "count": len(scores),
        "average": round(float(np.mean(scores_array)), 2),
        "median": round(float(np.median(scores_array)), 2),
        "max": round(float(np.max(scores_array)), 2),
        "min": round(float(np.min(scores_array)), 2),
        "std": round(float(np.std(scores_array)), 2),
        "pass_rate": round((pass_count / len(scores)) * 100, 2),
    }


def get_grade_distribution(grades_query):
    """获取成绩分布"""
    scores = [grade.score for grade in grades_query]

    if not scores:
        return {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}

    distribution = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}

    for score in scores:
        if score >= 90:
            distribution["A"] += 1
        elif score >= 80:
            distribution["B"] += 1
        elif score >= 70:
            distribution["C"] += 1
        elif score >= 60:
            distribution["D"] += 1
        else:
            distribution["F"] += 1

    return distribution


def get_student_ranking(course_id=None, class_name=None):
    """获取学生排名"""
    from app import db

    # 构建查询
    query = db.session.query(
        Student.id,
        Student.student_id,
        Student.name,
        Student.class_name,
        func.avg(Grade.score).label("avg_score"),
        func.count(Grade.id).label("grade_count"),
    ).join(Grade)

    if course_id:
        query = query.filter(Grade.course_id == course_id)

    if class_name:
        query = query.filter(Student.class_name == class_name)

    # 按学生分组并排序
    rankings = query.group_by(Student.id).order_by(func.avg(Grade.score).desc()).all()

    # 添加排名
    result = []
    for rank, student in enumerate(rankings, 1):
        result.append(
            {
                "rank": rank,
                "student_id": student.student_id,
                "name": student.name,
                "class_name": student.class_name,
                "avg_score": round(float(student.avg_score), 2),
                "grade_count": student.grade_count,
            }
        )

    return result


def get_course_statistics():
    """获取课程统计信息"""
    from app import db

    stats = (
        db.session.query(
            Course.id,
            Course.code,
            Course.name,
            func.count(Grade.id).label("total_grades"),
            func.avg(Grade.score).label("avg_score"),
            func.max(Grade.score).label("max_score"),
            func.min(Grade.score).label("min_score"),
        )
        .join(Grade)
        .group_by(Course.id)
        .all()
    )

    result = []
    for stat in stats:
        result.append(
            {
                "course_id": stat.id,
                "course_code": stat.code,
                "course_name": stat.name,
                "total_students": stat.total_grades,
                "avg_score": round(float(stat.avg_score), 2),
                "max_score": round(float(stat.max_score), 2),
                "min_score": round(float(stat.min_score), 2),
            }
        )

    return result


def export_grades_to_excel(grades_query, filename):
    """导出成绩到Excel"""
    data = []
    for grade in grades_query:
        data.append(
            {
                "学号": grade.student.student_id,
                "姓名": grade.student.name,
                "班级": grade.student.class_name,
                "课程代码": grade.course.code,
                "课程名称": grade.course.name,
                "成绩": grade.score,
                "等级": grade.letter_grade,
                "考试类型": grade.exam_type,
                "考试日期": grade.exam_date.strftime("%Y-%m-%d"),
                "备注": grade.remarks or "",
            }
        )

    df = pd.DataFrame(data)
    df.to_excel(filename, index=False)
    return filename


def validate_score(score):
    """验证成绩有效性"""
    try:
        score = float(score)
        return 0 <= score <= 100
    except (ValueError, TypeError):
        return False


def get_class_list():
    """获取班级列表"""
    from app import db

    classes = db.session.query(Student.class_name).distinct().all()
    return [cls[0] for cls in classes if cls[0]]
