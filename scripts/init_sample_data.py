import random
from datetime import date

from app import create_app, db
from app.models import Course, Grade, Student

app = create_app("production")

COURSES = [
    ("CN", "语文"),
    ("MA", "数学"),
    ("EN", "英语"),
    ("SC", "科学"),
    ("SOC", "社会"),
    ("MOR", "道法"),
]

STUDENTS = [
    ("20240001", "张三", "七年级一班", "七年级"),
    ("20240002", "李四", "七年级一班", "七年级"),
    ("20240003", "王五", "七年级一班", "七年级"),
    ("20240004", "赵六", "七年级二班", "七年级"),
    ("20240005", "孙七", "七年级二班", "七年级"),
    ("20240006", "周八", "七年级二班", "七年级"),
    ("20240007", "吴九", "七年级三班", "七年级"),
    ("20240008", "郑十", "七年级三班", "七年级"),
]


def ensure_courses():
    created = 0
    for code, name in COURSES:
        c = Course.query.filter_by(code=code).first()
        if not c:
            c = Course(code=code, name=name, description=f"{name}课程")
            db.session.add(c)
            created += 1
    if created:
        db.session.commit()
    return created


def ensure_students():
    created = 0
    for sid, name, cls, gl in STUDENTS:
        s = Student.query.filter_by(student_id=sid).first()
        if not s:
            s = Student(student_id=sid, name=name, class_name=cls, grade_level=gl)
            db.session.add(s)
            created += 1
    if created:
        db.session.commit()
    return created


def ensure_grades():
    random.seed(42)
    created = 0
    # 一个默认考试名称
    exam_name = "default"
    for sid, *_ in STUDENTS:
        stu = Student.query.filter_by(student_id=sid).first()
        if not stu:
            continue
        for code, _name in COURSES:
            course = Course.query.filter_by(code=code).first()
            if not course:
                continue
            g = Grade.query.filter_by(student_id=stu.id, course_id=course.id).first()
            score = max(0, min(100, int(60 + random.gauss(10, 15))))
            if not g:
                g = Grade(
                    student_id=stu.id,
                    course_id=course.id,
                    score=score,
                    exam_type="regular",
                    exam_name=exam_name,
                    exam_date=date.today(),
                )
                db.session.add(g)
                created += 1
            else:
                g.score = score
                g.exam_type = "regular"
                g.exam_name = exam_name
    if created:
        db.session.commit()
    return created


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        c = ensure_courses()
        s = ensure_students()
        g = ensure_grades()
        print(f"Sample data ready: courses+{c}, students+{s}, grades+{g}")
