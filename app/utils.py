"""
工具函数
"""

import numpy as np
import pandas as pd
from sqlalchemy import func

from app.models import Course, Grade, Student, ExamScheme, GradeBandRule

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


def grade_letter_for(exam_name: str, subject_code: str, score: float) -> str:
    """根据规则或默认阈值计算单个成绩的等级（A-E）。"""
    # 优先查找范围法规则
    rule = GradeBandRule.query.filter_by(exam_name=exam_name, subject_code=subject_code).first()
    if rule and rule.method == 'range':
        # 注意：若a_min等为空，按默认区间
        a = rule.a_min if rule.a_min is not None else 90
        b = rule.b_min if rule.b_min is not None else 80
        c = rule.c_min if rule.c_min is not None else 70
        d = rule.d_min if rule.d_min is not None else 60
        if score >= a:
            return 'A'
        elif score >= b:
            return 'B'
        elif score >= c:
            return 'C'
        elif score >= d:
            return 'D'
        return 'E'
    # 若没有范围法规则配置且方法为percentile，需要整体分布，单个无法计算，回退默认
    if score >= 90:
        return 'A'
    elif score >= 80:
        return 'B'
    elif score >= 70:
        return 'C'
    elif score >= 60:
        return 'D'
    return 'E'


def get_grade_distribution(grades_query, exam_name: str | None = None, subject_code: str | None = None):
    """获取成绩分布，根据需要应用等级规则。
    - 若存在 range 规则，直接按阈值划分
    - 若存在 percentile 规则，则按比例切分
    - 否则使用默认90/80/70/60
    """
    scores = [grade.score for grade in grades_query]
    if not scores:
        return {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0}

    # 检索规则
    rule = None
    if exam_name and subject_code:
        rule = GradeBandRule.query.filter_by(exam_name=exam_name, subject_code=subject_code).first()

    if rule and rule.method == 'range':
        a = rule.a_min if rule.a_min is not None else 90
        b = rule.b_min if rule.b_min is not None else 80
        c = rule.c_min if rule.c_min is not None else 70
        d = rule.d_min if rule.d_min is not None else 60
        dist = {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0}
        for s in scores:
            if s >= a:
                dist['A'] += 1
            elif s >= b:
                dist['B'] += 1
            elif s >= c:
                dist['C'] += 1
            elif s >= d:
                dist['D'] += 1
            else:
                dist['E'] += 1
        return dist

    if rule and rule.method == 'percentile':
        # 计算分位点
        scores_sorted = sorted(scores, reverse=True)
        n = len(scores_sorted)
        # 百分比默认 20% 均分
        ap = (rule.a_pct if rule.a_pct is not None else 20) / 100.0
        bp = (rule.b_pct if rule.b_pct is not None else 20) / 100.0
        cp = (rule.c_pct if rule.c_pct is not None else 20) / 100.0
        dp = (rule.d_pct if rule.d_pct is not None else 20) / 100.0
        ep = (rule.e_pct if rule.e_pct is not None else 20) / 100.0
        # 按比例分配人数（四舍五入/保底）
        # 基于排序后的成绩切分，优先A，再B，再C，再D，剩余E，确保总数精确等于n
        boundaries = [ap, bp, cp, dp]
        counts = []
        remaining = n
        for p in boundaries:
            cnt = int(round(n * p))
            if cnt > remaining:
                cnt = remaining
            counts.append(cnt)
            remaining -= cnt
        counts.append(max(0, remaining))  # E
        a_n, b_n, c_n, d_n, e_n = counts
        dist = {"A": a_n, "B": b_n, "C": c_n, "D": d_n, "E": e_n}
        return dist

    # 默认规则
    dist = {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0}
    for score in scores:
        if score >= 90:
            dist["A"] += 1
        elif score >= 80:
            dist["B"] += 1
        elif score >= 70:
            dist["C"] += 1
        elif score >= 60:
            dist["D"] += 1
        else:
            dist["E"] += 1
    return dist


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
