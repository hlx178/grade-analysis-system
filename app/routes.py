"""
路由与 API 定义
包含健康检查与就绪探针
"""

from flask import Blueprint

# Health and readiness endpoints
health_bp = Blueprint('health', __name__)

@health_bp.route('/health', methods=['GET'])
def health():
    return {'status': 'ok'}, 200

@health_bp.route('/ready', methods=['GET'])
def ready():
    from flask import current_app
    import os, shutil, tempfile
    # 1) DB 探针
    try:
        from app import db
        db.session.execute('SELECT 1')
    except Exception:
        return {'status': 'not_ready', 'reason': 'db_unreachable'}, 503
    # 2) 目录可写
    upload_dir = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    export_dir = current_app.config.get('EXPORT_DIR', 'exports')
    for d in [upload_dir, export_dir]:
        try:
            os.makedirs(d, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=d)
            os.close(fd); os.remove(tmp)
        except Exception:
            return {'status': 'not_ready', 'reason': f'dir_not_writable:{d}'}, 503
    # 3) 磁盘剩余阈值
    try:
        total, used, free = shutil.disk_usage('/')
        free_mb = int(free / (1024*1024))
        threshold = int(current_app.config.get('READY_DISK_FREE_MB', 1024))
        if free_mb < threshold:
            return {'status': 'not_ready', 'reason': f'low_disk:{free_mb}MB < {threshold}MB'}, 503
    except Exception:
        return {'status': 'not_ready', 'reason': 'disk_check_failed'}, 503
    return {'status': 'ready'}, 200


import os
import uuid
import io
from io import BytesIO

import pandas as pd
from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for, send_file, Response, abort, stream_with_context
from flask_login import current_user, login_required, login_user, logout_user

from app import db
from app.models import Course, Grade, Student, User, ExamScheme, GradeBandRule, GradeBandSet, ExportJob
from app.utils import (
    SUBJECTS,
    TOTAL_SUBJECT,
    calculate_statistics,
    ensure_default_exam_scheme,
    get_class_list,
    get_course_statistics,
    get_grade_distribution,
    get_student_ranking,
    normalize_exam_type,
    validate_score,
)

# 蓝图定义
main_bp = Blueprint("main", __name__)
auth_bp = Blueprint("auth", __name__)
api_bp = Blueprint("api", __name__)
import_bp = Blueprint("importer", __name__)

# Prometheus metrics endpoint (/metrics)
try:
    from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
    _REQ_COUNT = Counter('gas_http_requests_total', 'Total HTTP requests', ['method','endpoint','status'])
    _REQ_LATENCY = Histogram('gas_http_request_duration_seconds', 'Request latency', ['endpoint'])

    @main_bp.before_app_request
    def _metrics_req_start():
        from flask import g, request
        g._metrics_path = request.endpoint or request.path or 'unknown'
        g._metrics_timer = _REQ_LATENCY.labels(g._metrics_path).time()

    @main_bp.after_app_request
    def _metrics_req_end(response):
        from flask import g, request
        try:
            if getattr(g, '_metrics_timer', None):
                g._metrics_timer.observe_duration()  # stop timer
            _REQ_COUNT.labels(request.method, getattr(g, '_metrics_path','unknown'), response.status_code).inc()
        except Exception:
            pass
        return response

    @health_bp.route('/metrics')
    def metrics():
        data = generate_latest()
        return data, 200, {'Content-Type': CONTENT_TYPE_LATEST}
except Exception:
    pass


# 首页仪表盘
@main_bp.route("/")
@login_required
def dashboard():
    course_stats = get_course_statistics()
    courses = Course.query.order_by(Course.code).all()
    classes = get_class_list()
    # 可选：提供已存在的考试名称列表
    exam_names = [row[0] for row in db.session.query(GradeBandRule.exam_name).distinct().all()]
    grade_levels = [row[0] for row in db.session.query(Student.grade_level).distinct().all() if row[0]]
    return render_template(
        "dashboard.html",
        course_stats=course_stats,
        courses=courses,
        classes=classes,
        exam_names=exam_names,
        grade_levels=grade_levels,
    )


# 学生管理页面
@main_bp.route("/students")
@login_required
def students():
    students = Student.query.order_by(Student.class_name, Student.student_id).all()
    return render_template("students.html", students=students)


# 课程管理页面
@main_bp.route("/courses")
@login_required
def courses():
    courses = Course.query.order_by(Course.code).all()
    return render_template("courses.html", courses=courses)


# 成绩管理页面
@main_bp.route("/grades")
@login_required
def grades():
    grades = Grade.query.order_by(Grade.created_at.desc()).limit(100).all()
    return render_template("grades.html", grades=grades)


# 登录/登出
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash("登录成功", "success")
            next_page = request.args.get("next") or url_for("main.dashboard")
            return redirect(next_page)
        flash("用户名或密码错误", "danger")
    return render_template("login.html")


# 导入页面
@main_bp.route("/import")
@login_required
def import_page():
    return render_template("import.html")


@main_bp.route("/summary")
@login_required
def summary_page():
    return render_template("summary.html")


@main_bp.route("/users")
@login_required
def users_page():
    if current_user.role != 'admin':
        abort(403)
    return render_template("users.html")


@main_bp.route("/diagnostics")
@login_required
def diagnostics_page():
    if current_user.role != 'admin':
        abort(403)
    return render_template("diagnostics.html")


@main_bp.route("/exam-schemes")
@login_required
def exam_schemes_page():
    # 初始显示常规考试，若无则创建默认方案
    ensure_default_exam_scheme("regular")
    return render_template("exam_schemes.html")


@main_bp.route("/grade-bands")
@login_required
def grade_bands_page():
    courses = Course.query.order_by(Course.code).all()
    # 版本信息初步加载（默认exam_name=default）
    sets = GradeBandSet.query.filter_by(exam_name='default').order_by(GradeBandSet.version.desc()).all()

@main_bp.route('/student-analysis')
@login_required
def student_analysis_page():
    sid = request.args.get('student_id')
    sid_int = request.args.get('id', type=int)
    student = None
    if sid_int:
        student = Student.query.get_or_404(sid_int)
    elif sid:
        student = Student.query.filter_by(student_id=sid).first_or_404()
    else:
        abort(400)
    from app.utils import SUBJECTS, TOTAL_SUBJECT
    subjects = [('TOTAL', TOTAL_SUBJECT[1])] + [(code, name) for (_col, code, name) in SUBJECTS]
    return render_template('student_analysis.html', student=student, subjects=subjects)

    return render_template("grade_bands.html", courses=courses, subjects=SUBJECTS + [TOTAL_SUBJECT], sets=sets)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("您已退出登录", "info")
    return redirect(url_for("auth.login"))


# API: 学生
@api_bp.route("/students", methods=["GET", "POST"])
@login_required
def api_students():
    if request.method == "POST":
        data = request.get_json() or request.form
        student = Student(
            student_id=data.get("student_id"),
            name=data.get("name"),
            class_name=data.get("class_name"),
            email=data.get("email"),
        )
        db.session.add(student)
        db.session.commit()
        return jsonify({"message": "Student created", "id": student.id}), 201
    # GET
    students = Student.query.all()
    return jsonify(
        [
            {
                "id": s.id,
                "student_id": s.student_id,
                "name": s.name,
                "class_name": s.class_name,
                "email": s.email,
            }
            for s in students
        ]
    )


@api_bp.route("/students/<int:student_id>", methods=["GET", "PUT", "DELETE"])
@login_required
def api_student_detail(student_id):
    student = Student.query.get_or_404(student_id)
    if request.method == "GET":
        return jsonify(
            {
                "id": student.id,
                "student_id": student.student_id,
                "name": student.name,
                "class_name": student.class_name,
                "email": student.email,
            }
        )
    elif request.method == "PUT":
        data = request.get_json() or request.form
        student.student_id = data.get("student_id", student.student_id)
        student.name = data.get("name", student.name)
        student.class_name = data.get("class_name", student.class_name)
        student.email = data.get("email", student.email)
        db.session.commit()
        return jsonify({"message": "Student updated"})
    else:  # DELETE
        db.session.delete(student)
        db.session.commit()
        return jsonify({"message": "Student deleted"})


# API: 课程
@api_bp.route("/courses", methods=["GET", "POST"])
@login_required
def api_courses():
    if request.method == "POST":
        data = request.get_json() or request.form
        course = Course(
            code=data.get("code"), name=data.get("name"), description=data.get("description")
        )
        db.session.add(course)
        db.session.commit()
        return jsonify({"message": "Course created", "id": course.id}), 201
    # GET
    courses = Course.query.all()
    return jsonify(
        [
            {"id": c.id, "code": c.code, "name": c.name, "description": c.description}
            for c in courses
        ]
    )


@api_bp.route("/courses/<int:course_id>", methods=["GET", "PUT", "DELETE"])
@login_required
def api_course_detail(course_id):
    course = Course.query.get_or_404(course_id)
    if request.method == "GET":
        return jsonify(
            {
                "id": course.id,
                "code": course.code,
                "name": course.name,
                "description": course.description,
            }
        )
    elif request.method == "PUT":
        data = request.get_json() or request.form
        course.code = data.get("code", course.code)
        course.name = data.get("name", course.name)
        course.description = data.get("description", course.description)
        db.session.commit()
        return jsonify({"message": "Course updated"})
    else:  # DELETE
        db.session.delete(course)
        db.session.commit()
        return jsonify({"message": "Course deleted"})


# API: 成绩
@api_bp.route("/grades", methods=["GET", "POST"])
@login_required
def api_grades():
    if request.method == "POST":
        data = request.get_json() or request.form
        try:
            score = float(data.get("score"))
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid score"}), 400
        if not validate_score(score):
            return jsonify({"error": "Score must be between 0 and 100"}), 400
        grade = Grade(
            student_id=data.get("student_id"),
            course_id=data.get("course_id"),
            score=score,
            exam_type=data.get("exam_type", "final"),
        )
        db.session.add(grade)
        db.session.commit()
        return jsonify({"message": "Grade created", "id": grade.id}), 201
    # GET
    grades = Grade.query.all()
    return jsonify(
        [
            {
                "id": g.id,
                "student_id": g.student_id,
                "course_id": g.course_id,
                "score": g.score,
                "exam_type": g.exam_type,
                "created_at": g.created_at.isoformat(),
            }
            for g in grades
        ]
    )


@api_bp.route("/grades/<int:grade_id>", methods=["GET", "PUT", "DELETE"])
@login_required
def api_grade_detail(grade_id):
    grade = Grade.query.get_or_404(grade_id)
    if request.method == "GET":
        return jsonify(
            {
                "id": grade.id,
                "student_id": grade.student_id,
                "course_id": grade.course_id,
                "score": grade.score,
                "exam_type": grade.exam_type,
                "created_at": grade.created_at.isoformat(),
            }
        )
    elif request.method == "PUT":
        data = request.get_json() or request.form
        if "score" in data and not validate_score(data["score"]):
            return jsonify({"error": "Score must be between 0 and 100"}), 400
        grade.score = data.get("score", grade.score)
        grade.exam_type = data.get("exam_type", grade.exam_type)
        db.session.commit()
        return jsonify({"message": "Grade updated"})
    else:  # DELETE
        db.session.delete(grade)
        db.session.commit()
        return jsonify({"message": "Grade deleted"})


# API: 分析
@api_bp.route("/analysis/statistics", methods=["GET"])
@login_required
def api_analysis_statistics():
    course_id = request.args.get("course_id", type=int)
    class_name = request.args.get("class_name")
    query = Grade.query
    if course_id:
        query = query.filter_by(course_id=course_id)
    if class_name:
        query = query.join(Student).filter(Student.class_name == class_name)
    grades = query.all()
    stats = calculate_statistics(grades)
    exam_name = request.args.get("exam_name")
    subject_code = None
    if course_id:
        course = Course.query.get(course_id)
        subject_code = course.code if course else None
    distribution = get_grade_distribution(grades, exam_name=exam_name, subject_code=subject_code)
    return jsonify({"stats": stats, "distribution": distribution})


# 导入: 预览工作表列表，保存临时文件并返回 file_id
@api_bp.route("/import/preview", methods=["POST"])
@login_required
def api_import_preview():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400

    # 保存到上传目录
    upload_dir = current_app.config.get("UPLOAD_FOLDER", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    file_id = str(uuid.uuid4())
    # 统一使用 .xlsx 扩展名
    file_path = os.path.join(upload_dir, f"{file_id}.xlsx")
    f.save(file_path)

    try:
        # 读取工作表列表
        xls = pd.ExcelFile(file_path, engine="openpyxl")
        sheets = xls.sheet_names
    except Exception as e:
        # 清理坏文件
        try:
            os.remove(file_path)
        except Exception:
            pass
        return jsonify({"error": f"Failed to read excel: {e}"}), 400

    return jsonify({"file_id": file_id, "sheets": sheets})


# 导入: 根据选择的工作表执行导入
@api_bp.route("/import/grades", methods=["POST"])
@login_required
def api_import_grades():
    data = request.get_json() or request.form
    file_id = data.get("file_id")
    sheet_name = data.get("sheet_name")
    if not file_id or not sheet_name:
        return jsonify({"error": "file_id and sheet_name are required"}), 400

    upload_dir = current_app.config.get("UPLOAD_FOLDER", "uploads")
    file_path = os.path.join(upload_dir, f"{file_id}.xlsx")
    if not os.path.exists(file_path):
        return jsonify({"error": "Uploaded file not found or expired"}), 400

    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name, engine="openpyxl")
    except Exception as e:
        return jsonify({"error": f"Failed to read sheet: {e}"}), 400

    # 期望列（模板方式）：学号、姓名、班级、语文、数学、英语、科学、社会、道法，可选：考试类型
    # 兼容旧方式（含 课程代码/课程名称/成绩）
    template_cols = ["学号", "姓名", "班级", "年级", "语文", "数学", "英语", "科学", "社会", "道法"]
    legacy_required_cols = ["学号", "姓名", "班级", "课程代码", "课程名称", "成绩"]

    # 判断模板方式或旧方式
    is_template = all(col in df.columns for col in template_cols)
    if not is_template:
        # 非模板方式则要求旧字段存在
        for col in legacy_required_cols:
            if col not in df.columns:
                return jsonify({"error": f"Missing required column: {col}"}), 400

    created = 0
    updated = 0
    if is_template:
        # 处理考试类型与考试方案
        exam_type = normalize_exam_type(df.get("考试类型").iloc[0] if "考试类型" in df.columns else "regular")
        exam_name = str(df.get("考试名称").iloc[0] if "考试名称" in df.columns else "default").strip() or "default"
        ensure_default_exam_scheme(exam_type)

        # 为模板中的各学科准备/获取Course
        subject_courses = {}
        for col_name, code, name in SUBJECTS:
            course = Course.query.filter_by(code=code).first()
            if not course:
                course = Course(code=code, name=name)
                db.session.add(course)
                db.session.flush()
            subject_courses[col_name] = course

        # 逐行导入
        for _, row in df.iterrows():
            sid = str(row["学号"]).strip()
            student = Student.query.filter_by(student_id=sid).first()
            if not student:
                student = Student(
                    student_id=sid,
                    name=str(row.get("姓名") or "").strip(),
                    class_name=str(row.get("班级") or "").strip(),
                    grade_level=str(row.get("年级") or "").strip() or None,
                    email=None,
                )
                db.session.add(student)
                db.session.flush()
            else:
                # 更新年级信息（若存在）
                gl = str(row.get("年级") or "").strip()
                if gl:
                    student.grade_level = gl

            total_score = 0.0
            for col_name, code, _ in SUBJECTS:
                val = row.get(col_name)
                try:
                    score_val = float(val) if pd.notna(val) else None
                except Exception:
                    score_val = None
                if score_val is None:
                    continue
                course = subject_courses[col_name]
                grade = Grade.query.filter_by(student_id=student.id, course_id=course.id).first()
                if not grade:
                    grade = Grade(student=student, course=course, score=score_val, exam_type=exam_type, exam_name=exam_name)
                    db.session.add(grade)
                    created += 1
                else:
                    grade.score = score_val
                    grade.exam_type = exam_type
                    updated += 1
                total_score += score_val

            # 总分作为一个虚拟课程TOTAL写入（可选）
            total_code = TOTAL_SUBJECT[1]
            total_course = Course.query.filter_by(code=total_code).first()
            if not total_course:
                total_course = Course(code=total_code, name=TOTAL_SUBJECT[2])
                db.session.add(total_course)
                db.session.flush()
            grade_total = Grade.query.filter_by(student_id=student.id, course_id=total_course.id).first()
            if not grade_total:
                grade_total = Grade(student=student, course=total_course, score=total_score, exam_type=exam_type, exam_name=exam_name)
                db.session.add(grade_total)
                created += 1
            else:
                grade_total.score = total_score
                grade_total.exam_type = exam_type
                updated += 1
    else:
        # 兼容旧方式
        for _, row in df.iterrows():
            student = Student.query.filter_by(student_id=str(row["学号"]).strip()).first()
            if not student:
                student = Student(
                    student_id=str(row["学号"]).strip(),
                    name=str(row.get("姓名") or "").strip(),
                    class_name=str(row.get("班级") or "").strip(),
                    email=None,
                )
                db.session.add(student)
                db.session.flush()

            course_code = str(row["课程代码"]).strip()
            course = Course.query.filter_by(code=course_code).first()
            if not course:
                course = Course(code=course_code, name=str(row.get("课程名称") or "").strip())
                db.session.add(course)
                db.session.flush()

            try:
                score_val = float(row["成绩"])
            except Exception:
                score_val = None
            if score_val is None:
                continue

            exam_type = normalize_exam_type(row.get("考试类型") or "regular")
            exam_name = str(row.get("考试名称") or "default").strip() or "default"

            grade = Grade.query.filter_by(student_id=student.id, course_id=course.id).first()
            if not grade:
                grade = Grade(student=student, course=course, score=score_val, exam_type=exam_type, exam_name=exam_name)
                db.session.add(grade)
                created += 1
            else:
                grade.score = score_val
                grade.exam_type = exam_type
                updated += 1

    db.session.commit()

    # 导入完成后可清理临时文件
    try:
        os.remove(file_path)
    except Exception:
        pass

    return jsonify({"message": "Import finished", "created": created, "updated": updated})


@api_bp.route("/analysis/ranking", methods=["GET"])
@login_required
def api_analysis_ranking():
    course_id = request.args.get("course_id", type=int)
    class_name = request.args.get("class_name")
    grade_level = request.args.get("grade_level")
    exam_name = request.args.get("exam_name")
    rankings = get_student_ranking(course_id=course_id, class_name=class_name, grade_level=grade_level, exam_name=exam_name)
    return jsonify({"rankings": rankings})


@api_bp.route('/analysis/trends', methods=['GET'])
@login_required
def api_analysis_trends():
    """按考试名称时间序列统计每次考试的平均分、最高分、最低分、标准差，可按学科/年级/班级过滤"""
    subject_code = request.args.get('subject_code')
    grade_level = request.args.get('grade_level')
    class_name = request.args.get('class_name')
    q = Grade.query.join(Course).join(Student)
    if subject_code:
        q = q.filter(Course.code == subject_code)
    if grade_level:
        q = q.filter(Student.grade_level == grade_level)
    if class_name:
        q = q.filter(Student.class_name == class_name)
    # 聚合到 exam_name
    rows = q.with_entities(Grade.exam_name, Grade.score).all()
    from collections import defaultdict
    buckets = defaultdict(list)
    for exam_name, score in rows:
        buckets[exam_name or 'default'].append(float(score))
    import math
    out = []
    for exam_name, arr in buckets.items():
        if not arr: continue
        n = len(arr); s = sum(arr); mean = s/n
        var = sum((x-mean)**2 for x in arr)/n
        # 计算中位数与分位数
        arr_sorted = sorted(arr)
        def _median(a):
            m = len(a)
            mid = m // 2
            if m % 2 == 1:
                return a[mid]
            else:
                return (a[mid-1] + a[mid]) / 2.0
        def _percentile(a, p):
            if not a: return None
            k = (p/100.0) * (len(a)-1)
            f = math.floor(k); c = math.ceil(k)
            if f == c: return a[int(k)]
            d0 = a[int(f)] * (c - k)
            d1 = a[int(c)] * (k - f)
            return d0 + d1

        # percentile helper end
        med = _median(arr_sorted)
        p25 = _percentile(arr_sorted, 25)
        p75 = _percentile(arr_sorted, 75)
        out.append({
            'exam_name': exam_name,
            'count': n,
            'avg': round(mean,2),
            'max': max(arr),
            'min': min(arr),
            'std': round(math.sqrt(var),2),
            'median': round(med,2) if med is not None else None,
            'p25': round(p25,2) if p25 is not None else None,
            'p75': round(p75,2) if p75 is not None else None,
        })
    # 简单按 exam_name 排序（若 exam_name 可解析时间戳可在前端进一步排序）
    out.sort(key=lambda x: x['exam_name'])
    return jsonify({'trends': out})


@api_bp.route('/analysis/trends/export', methods=['GET'])
@login_required
def api_analysis_trends_export():
    """导出趋势数据为 CSV：exam_name, count, avg, max, min, std, median, p25, p75"""
    with current_app.test_request_context(query_string=request.query_string):
        res = api_analysis_trends()
        data = res.get_json() if hasattr(res, 'get_json') else res.json
    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['exam_name','count','avg','max','min','std','median','p25','p75'])
    for row in data.get('trends', []):
        writer.writerow([
            row.get('exam_name'), row.get('count'), row.get('avg'), row.get('max'),
            row.get('min'), row.get('std'), row.get('median'), row.get('p25'), row.get('p75')
        ])
    output.seek(0)
    return current_app.response_class(output.read(), mimetype='text/csv; charset=utf-8', headers={'Content-Disposition': 'attachment; filename=trends.csv'})


@api_bp.route('/analysis/class-compare', methods=['GET'])
@login_required
def api_analysis_class_compare():
    """按考试名称+学科维度，对各班的均分进行对比
    可选参数：
      - exam_name
      - subject_code（默认 TOTAL 时请显式传递）
      - grade_level（可选）
      - top_n（可选，>0 时返回前 N 个均分最高的班级）
      - min_count（可选，>0 时剔除样本数小于该阈值的班级）
      - sort_by（可选，avg|count，默认avg）
    """
    exam_name = request.args.get('exam_name')
    subject_code = request.args.get('subject_code')
    grade_level = request.args.get('grade_level')
    top_n = request.args.get('top_n', type=int)
    min_count = request.args.get('min_count', type=int)
    sort_by = (request.args.get('sort_by') or 'avg').lower()
    if sort_by not in ('avg','count'):
        sort_by = 'avg'
    q = Grade.query.join(Course).join(Student)
    if exam_name:
        q = q.filter(Grade.exam_name == exam_name)
    if subject_code:
        q = q.filter(Course.code == subject_code)
    if grade_level:
        q = q.filter(Student.grade_level == grade_level)
    rows = q.with_entities(Student.class_name, Grade.score).all()
    from collections import defaultdict
    import math
    agg = defaultdict(list)
    for cls, score in rows:
        agg[cls or '未知班级'].append(float(score))
    out = []
    for cls, arr in agg.items():
        if not arr: continue
        n = len(arr); mean = sum(arr)/n
        var = sum((x-mean)**2 for x in arr)/n
        meets = (min_count or 0) <= 0 or n >= int(min_count)
        out.append({'class_name': cls, 'avg': round(mean,2), 'count': n, 'std': round(math.sqrt(var),2), 'meets_threshold': bool(meets)})
    total_classes = len(out)
    below_threshold = sum(1 for o in out if not o['meets_threshold']) if (min_count and min_count > 0) else 0
    if sort_by == 'count':
        out.sort(key=lambda x: x['count'], reverse=True)
    else:
        out.sort(key=lambda x: x['avg'], reverse=True)
    if top_n and top_n > 0:
        out = out[:top_n]
    meta = {'min_count': int(min_count or 0), 'total': total_classes, 'below_threshold': below_threshold, 'filtered_out': below_threshold, 'returned': len(out)}
    return jsonify({'compare': out, 'meta': meta})

@api_bp.route('/analysis/distribution', methods=['GET'])
@login_required
def api_analysis_distribution():
    """按分数段生成直方图分布，可按考试/学科/年级/班级过滤
    params:
      - exam_name: 可选，指定考试名称
      - subject_code: 可选，学科代码（默认 TOTAL）
      - grade_level: 可选
      - class_name: 可选
      - bin_width: 可选，分箱宽度，默认 10
    """
    exam_name = request.args.get('exam_name')
    subject_code = request.args.get('subject_code') or 'TOTAL'
    grade_level = request.args.get('grade_level')
    class_name = request.args.get('class_name')
    binw_str = request.args.get('bin_width')
    bin_width = None  # None 表示自动
    if binw_str and binw_str.lower() != 'auto':
        try:
            bw = int(binw_str)
            if bw > 0:
                bin_width = bw
        except Exception:
            bin_width = None

    q = Grade.query.join(Course).join(Student)
    if exam_name:
        q = q.filter(Grade.exam_name == exam_name)
    if subject_code:
        q = q.filter(Course.code == subject_code)
    if grade_level:
        q = q.filter(Student.grade_level == grade_level)
    if class_name:
        q = q.filter(Student.class_name == class_name)

    scores = [float(s) for (s,) in q.with_entities(Grade.score).all()]
    if not scores:
        return jsonify({'bins': [], 'summary': {'count': 0}})

    import math
    smin = min(scores); smax = max(scores)
    # 自动计算 bin 宽度（Freedman–Diaconis; 退化到 Sturges）
    if not bin_width:
        arr = sorted(scores)
        n_s = len(arr)
        def percentile(a, p):
            k = (p/100.0) * (len(a)-1)
            f = math.floor(k); c = math.ceil(k)
            if f == c: return a[int(k)]
            return a[f]*(c-k) + a[c]*(k-f)
        try:
            iqr = percentile(arr, 75) - percentile(arr, 25)
            if iqr <= 0:
                raise ValueError('no iqr')
            bin_width = max(1, int(round(2 * iqr / (n_s ** (1/3)))))
        except Exception:
            # Sturges: k = ceil(log2(n)) + 1
            import math as _m
            k = max(1, int(_m.ceil(_m.log2(max(2, n_s))) + 1))
            bin_width = max(1, int(_m.ceil((smax - smin) / k))) or 10
    start = math.floor(smin / bin_width) * bin_width
    end = math.ceil(smax / bin_width) * bin_width
    if end == start:
        end = start + bin_width
    bins = []
    edges = list(range(int(start), int(end)+bin_width, bin_width))
    for i in range(len(edges)-1):
        bins.append({'start': edges[i], 'end': edges[i+1], 'count': 0, 'label': f"{edges[i]}-{edges[i+1]}"})
    # 计数（右开区间，最后一个包含右端点）
    for v in scores:
        idx = int((v - start) // bin_width)
        if idx < 0: idx = 0
        if idx >= len(bins): idx = len(bins)-1
        bins[idx]['count'] += 1

    n = len(scores); mean = sum(scores)/n
    var = sum((x-mean)**2 for x in scores)/n
    summary = {'count': n, 'avg': round(mean,2), 'max': smax, 'min': smin, 'std': round(math.sqrt(var),2), 'bin_width': int(bin_width)}
    # 追加比例与累计比例
    total = max(1, sum(b['count'] for b in bins))
    cum = 0
    for b in bins:
        b['percent'] = round(b['count'] * 100.0 / total, 2)
        cum += b['count']
        b['cdf'] = round(cum * 100.0 / total, 2)
    return jsonify({'bins': bins, 'summary': summary})

@api_bp.route('/analysis/distribution/export', methods=['GET'])
@login_required
def api_analysis_distribution_export():
    """导出直方图分布为 CSV：label,start,end,count + summary 行"""
    with current_app.test_request_context(query_string=request.query_string):
        res = api_analysis_distribution()
        data = res.get_json() if hasattr(res, 'get_json') else res.json
    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['label','start','end','count','percent','cdf'])
    for b in data.get('bins', []):
        writer.writerow([b.get('label'), b.get('start'), b.get('end'), b.get('count'), b.get('percent'), b.get('cdf')])
    # 空行 + summary
    writer.writerow([])
    s = data.get('summary') or {}
    writer.writerow(['summary', 'count', s.get('count'), 'avg', s.get('avg'), 'max', s.get('max'), 'min', s.get('min'), 'std', s.get('std'), 'bin_width', s.get('bin_width')])
    output.seek(0)
    return current_app.response_class(output.read(), mimetype='text/csv; charset=utf-8', headers={'Content-Disposition': 'attachment; filename=distribution.csv'})

@api_bp.route('/analysis/class-compare/export', methods=['GET'])
@login_required
def api_analysis_class_compare_export():
    """导出班级对比数据为 CSV：class_name, avg, count, std"""
    with current_app.test_request_context(query_string=request.query_string):
        res = api_analysis_class_compare()
        data = res.get_json() if hasattr(res, 'get_json') else res.json
    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['class_name','avg','count','std','meets_threshold'])
    for row in data.get('compare', []):
        writer.writerow([row.get('class_name'), row.get('avg'), row.get('count'), row.get('std'), row.get('meets_threshold')])
    output.seek(0)
    return current_app.response_class(output.read(), mimetype='text/csv; charset=utf-8', headers={'Content-Disposition': 'attachment; filename=class_compare.csv'})


@api_bp.route('/analysis/export-all', methods=['GET'])
@login_required
def api_analysis_export_all():
    """打包导出趋势、班级对比、分布直方图三份 CSV 为一个 ZIP
    接收与各自导出接口一致的查询参数：
      - 通用：subject_code, grade_level, class_name
      - 班级对比：exam_name, top_n（可选）
      - 分布：exam_name（可选）, bin_width（默认10）
    """
    from urllib.parse import urlencode
    import io, zipfile

    # 构造各自 querystring

@api_bp.route('/analysis/student-trend', methods=['GET'])
@login_required
def api_analysis_student_trend():
    sid = request.args.get('student_id')
    sid_int = request.args.get('id', type=int)
    subject_code = request.args.get('subject_code') or 'TOTAL'
    year_from = request.args.get('year_from', type=int)
    year_to = request.args.get('year_to', type=int)
    term = (request.args.get('term') or '').lower()  # 'spring' | 'fall' | ''
    exam_type = request.args.get('exam_type')  # optional
    # 找学生
    student = None
    if sid_int:
        student = Student.query.get_or_404(sid_int)
    elif sid:
        student = Student.query.filter_by(student_id=sid).first_or_404()
    else:
        return jsonify({'error': 'missing student id'}), 400
    # 查询该生该科多次考试
    q = Grade.query.join(Course).filter(Grade.student_id == student.id)
    if subject_code:
        q = q.filter(Course.code == subject_code)
    if exam_type:
        q = q.filter(Grade.exam_type == exam_type)
    rows = q.order_by(Grade.exam_name).all()
    # 过滤学年/学期（基于 exam_name 解析：YYYY 或 YYYY-.. / YYYYMMDD；学期关键词 上/下/春/秋/S/F）
    def parse_year_and_term(name: str):
        import re
        if not name: return None, None
        m1 = re.search(r'(\d{4})', name)
        y = int(m1.group(1)) if m1 else None
        t = None
        if re.search(r'(上|春|S)', name, flags=re.I):
            t = 'spring'
        elif re.search(r'(下|秋|F)', name, flags=re.I):
            t = 'fall'
        return y, t
    if year_from or year_to or term:
        rows = [g for g in rows if (
            (parse_year_and_term(g.exam_name)[0] is None or ((year_from is None or parse_year_and_term(g.exam_name)[0] >= year_from) and (year_to is None or parse_year_and_term(g.exam_name)[0] <= year_to))) and
            (not term or parse_year_and_term(g.exam_name)[1] == term)
        )]
    # 聚合 exam_name -> score
    from collections import defaultdict
    exams = defaultdict(list)
    for g in rows:
        exams[g.exam_name].append(g.score)
    # 计算班级/年级排名与均线（同一考试内）
    import math
    ranks = {}
    avg_map = {}
    for exam_name in exams.keys():
        q_cls = Grade.query.join(Student).join(Course).filter(Grade.exam_name==exam_name)
        if subject_code:
            q_cls = q_cls.filter(Course.code==subject_code)
        cls_rows = q_cls.with_entities(Student.student_id, Grade.score, Student.class_name, Student.grade_level).all()
        # 排序映射
        def rank_map(pairs):
            ps = sorted(pairs, key=lambda x: x[1], reverse=True)
            return { sid: i for i, (sid, _) in enumerate(ps, 1) }
        from collections import defaultdict
        by_class = defaultdict(list)
        by_grade = defaultdict(list)
        for sid0, score0, cls, gl in cls_rows:
            by_class[cls].append((sid0, float(score0)))
            by_grade[gl].append((sid0, float(score0)))
        class_rank = rank_map(by_class.get(student.class_name, []))
        grade_rank = rank_map(by_grade.get(student.grade_level, []))
        # 均线
        def avg_of(pairs):
            return round(sum(s for _, s in pairs)/len(pairs), 2) if pairs else None
        class_pairs = by_class.get(student.class_name, [])
        grade_pairs = by_grade.get(student.grade_level, [])
        avg_map[exam_name] = {
            'class_avg': avg_of(class_pairs),
            'grade_avg': avg_of(grade_pairs),
        }
        ranks[exam_name] = {
            'class_rank': class_rank.get(student.student_id),
            'grade_rank': grade_rank.get(student.student_id),
            'class_size': len(class_pairs),
            'grade_size': len(grade_pairs),
        }
    # 组装系列（含均线与百分位）
    def percentile(score_list, value):
        if not score_list: return None
        sorted_scores = sorted(score_list)
        import bisect
        idx = bisect.bisect_right(sorted_scores, value)
        return round(idx / len(sorted_scores) * 100.0, 2)
    series = []
    # 缓存用于百分位的集合（避免重复构建）
    class_sets = {}
    grade_sets = {}
    for exam_name, arr in exams.items():
        sc = float(sum(arr)/len(arr)) if arr else None
        am = avg_map.get(exam_name, {})
        # 准备集合
        if exam_name not in class_sets:
            # 重建与上面 ranks 使用的相同集合
            q_tmp = Grade.query.join(Student).join(Course).filter(Grade.exam_name==exam_name)
            if subject_code:
                q_tmp = q_tmp.filter(Course.code==subject_code)
            rows_tmp = q_tmp.with_entities(Student.class_name, Student.grade_level, Grade.score).all()
            c_scores = [float(s) for (cls, _gl, s) in rows_tmp if cls == student.class_name]
            g_scores = [float(s) for (_cls, gl, s) in rows_tmp if gl == student.grade_level]
            class_sets[exam_name] = c_scores
            grade_sets[exam_name] = g_scores
        cp = percentile(class_sets.get(exam_name, []), sc) if sc is not None else None
        gp = percentile(grade_sets.get(exam_name, []), sc) if sc is not None else None
        series.append({'exam_name': exam_name, 'score': sc, 'class_avg': am.get('class_avg'), 'grade_avg': am.get('grade_avg'), 'class_pct': cp, 'grade_pct': gp})
    # 计算环比/同比（按考试名字典序近似，yoy 以去年份前缀匹配）
    def base_token(name: str) -> str:
        import re
        return re.sub(r'^\s*\d{4}[-/年]?\s*', '', name or '').strip()
    series_sorted = sorted(series, key=lambda x: x['exam_name'])
    last_score = None
    seen_by_base = {}
    for item in series_sorted:
        sc = item.get('score')
        item['delta_prev'] = (sc - last_score) if (sc is not None and last_score is not None) else None
        last_score = sc if sc is not None else last_score
        bt = base_token(item['exam_name'])
        if bt in seen_by_base and sc is not None and seen_by_base[bt] is not None:
            item['delta_yoy'] = sc - seen_by_base[bt]
        else:
            item['delta_yoy'] = None
        if sc is not None:
            seen_by_base[bt] = sc

@api_bp.route('/analysis/student-trend/export', methods=['GET'])
@login_required
def api_analysis_student_trend_export():
    # 复用查询逻辑
    from flask import render_template
    r = api_analysis_student_trend()
    if isinstance(r, tuple):
        data, code = r
        if code != 200:
            return r
        payload = data.get_json()
    else:
        payload = r.get_json()
    fmt = (request.args.get('format') or 'csv').lower()
    if fmt != 'csv':
        fmt = 'csv'
    csv_text = render_template('student_analysis_export.csv.j2', series=payload['series'], ranks=payload['ranks'])
    return Response(csv_text, mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename=student-detail-{payload["student"]["student_id"]}-{payload["subject_code"]}.csv'})

    # 生成简单报告
    scores = [s['score'] for s in series_sorted if s['score'] is not None]
    trend = None
    if len(scores) >= 2:
        trend = 'up' if scores[-1] > scores[0] else ('down' if scores[-1] < scores[0] else 'flat')
    report = {
        'summary': {
            'exams': len(series_sorted),
            'avg': round(sum(scores)/len(scores),2) if scores else None,
            'min': min(scores) if scores else None,
            'max': max(scores) if scores else None,
            'latest': scores[-1] if scores else None,
            'trend': trend
        }
    }
    return jsonify({
        'student': { 'id': student.id, 'student_id': student.student_id, 'name': student.name, 'class_name': student.class_name, 'grade_level': student.grade_level },
        'subject_code': subject_code,
        'series': series_sorted,
        'ranks': ranks,
        'report': report
    })

    args = request.args
    trends_qs = urlencode({k: v for k, v in args.items() if k in ('subject_code','grade_level','class_name')})
    class_qs_dict = {k: v for k, v in args.items() if k in ('exam_name','subject_code','grade_level','top_n','min_count','sort_by')}
    class_qs = urlencode(class_qs_dict)
    dist_qs = urlencode({k: v for k, v in args.items() if k in ('exam_name','subject_code','grade_level','class_name','bin_width')})

    # 生成各 CSV 文本
    with current_app.test_request_context(query_string=trends_qs):
        trends_res = api_analysis_trends_export()
        trends_csv = trends_res.get_data(as_text=True)
    with current_app.test_request_context(query_string=class_qs):
        class_res = api_analysis_class_compare_export()
        class_csv = class_res.get_data(as_text=True)
    with current_app.test_request_context(query_string=dist_qs):
        dist_res = api_analysis_distribution_export()
        dist_csv = dist_res.get_data(as_text=True)

    # 打包 ZIP
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('trends.csv', trends_csv)
        zf.writestr('class_compare.csv', class_csv)
        zf.writestr('distribution.csv', dist_csv)
    buf.seek(0)
    return current_app.response_class(buf.read(), mimetype='application/zip', headers={'Content-Disposition': 'attachment; filename=analysis_exports.zip'})

    writer = csv.writer(output)
    writer.writerow(['class_name','avg','count','std'])
    for row in data.get('compare', []):
        writer.writerow([row.get('class_name'), row.get('avg'), row.get('count'), row.get('std')])
    output.seek(0)
    return current_app.response_class(output.read(), mimetype='text/csv; charset=utf-8', headers={'Content-Disposition': 'attachment; filename=class_compare.csv'})


# 等级规则：查询
@api_bp.route("/grade-bands", methods=["GET"])
@login_required
def api_grade_bands_get():
    exam_name = request.args.get("exam_name") or "default"
    rule_set_id = request.args.get("rule_set_id", type=int)
    if rule_set_id:
        # 从版本集读取
        s = GradeBandSet.query.get_or_404(rule_set_id)
        import json
        return jsonify(json.loads(s.rules_json))
    # 默认读取活跃规则
    rules = GradeBandRule.query.filter_by(exam_name=exam_name).all()
    data = []
    for r in rules:
        data.append({
            "id": r.id,
            "exam_name": r.exam_name,
            "subject_code": r.subject_code,
            "method": r.method,
            "a_min": r.a_min, "b_min": r.b_min, "c_min": r.c_min, "d_min": r.d_min,
            "a_pct": r.a_pct, "b_pct": r.b_pct, "c_pct": r.c_pct, "d_pct": r.d_pct, "e_pct": r.e_pct,
        })
    return jsonify(data)


# 等级规则：批量保存（覆盖写）
@api_bp.route("/grade-bands/bulk", methods=["PUT"])
@login_required
def api_grade_bands_bulk_put():
    payload = request.get_json(force=True)
    exam_name = payload.get("exam_name") or "default"
    items = payload.get("items") or []
    rule_set_id = payload.get("rule_set_id")
    # 基本校验
    for it in items:
        method = it.get("method")
        if method == 'range':
            a = it.get("a_min"); b = it.get("b_min"); c = it.get("c_min"); d = it.get("d_min")
            # 允许缺省，缺省时沿用默认 80/60/40/20
            # 若提供了必须满足顺序
            seq = [x for x in [a,b,c,d] if x is not None]
            if len(seq) == 4 and not (a >= b >= c >= d):
                return jsonify({"error": "Range thresholds must satisfy A>=B>=C>=D"}), 400
        elif method == 'percentile':
            ap, bp, cp, dp, ep = [it.get(k) for k in ["a_pct","b_pct","c_pct","d_pct","e_pct"]]
            if None in [ap,bp,cp,dp,ep]:
                return jsonify({"error": "Percentile requires all five percentages"}), 400
            total = ap + bp + cp + dp + ep
            if round(total) != 100:
                return jsonify({"error": "Percentile sums must be 100"}), 400
        else:
            return jsonify({"error": "Unknown method"}), 400

    # 若指定 rule_set_id，则保存快照至版本集；否则覆盖活跃规则
    import json
    if rule_set_id:
        s = GradeBandSet.query.get_or_404(rule_set_id)
        s.rules_json = json.dumps(items, ensure_ascii=False)
        db.session.commit()
        return jsonify({"message": "saved to set", "set_id": s.id, "count": len(items)})
    else:
        GradeBandRule.query.filter_by(exam_name=exam_name).delete()
        for it in items:
            rule = GradeBandRule(
                exam_name=exam_name,
                subject_code=it.get("subject_code"),
                method=it.get("method"),
                a_min=it.get("a_min"), b_min=it.get("b_min"), c_min=it.get("c_min"), d_min=it.get("d_min"),
                a_pct=it.get("a_pct"), b_pct=it.get("b_pct"), c_pct=it.get("c_pct"), d_pct=it.get("d_pct"), e_pct=it.get("e_pct"),
            )
            db.session.add(rule)
        db.session.commit()
        return jsonify({"message": "saved", "count": len(items)})


# 等级规则：预览（不落库）
@api_bp.route("/grade-bands/preview", methods=["POST"])
@login_required
def api_grade_bands_preview():
    payload = request.get_json(force=True)
    items = payload.get("items") or []
    course_id = payload.get("course_id")
    class_name = payload.get("class_name")
    # 构造一个临时的规则索引
    tmp_rules = {}
    for it in items:
        tmp_rules[(payload.get("exam_name") or "default", it.get("subject_code"))] = it

    # 准备数据集
    query = Grade.query
    if course_id:
        query = query.filter(Grade.course_id == course_id)
    if class_name:
        query = query.join(Student).filter(Student.class_name == class_name)
    grades = query.all()

    # 应用规则生成分布（支持 range 与 percentile）
    from collections import defaultdict
    by_key_scores = defaultdict(list)
    for g in grades:
        subject_code = g.course.code
        key = (g.exam_name or 'default', subject_code)
        by_key_scores[key].append(float(g.score))

    dist = defaultdict(int)
    total = 0
    for key, scores in by_key_scores.items():
        rule = tmp_rules.get(key)
        if not rule:
            continue
        n = len(scores)
        total += n
        if rule.get('method') == 'range':
            a = rule.get('a_min', 80); b = rule.get('b_min', 60); c = rule.get('c_min', 40); d = rule.get('d_min', 20)
            for s in scores:
                if s >= a: dist['A'] += 1
                elif s >= b: dist['B'] += 1
                elif s >= c: dist['C'] += 1
                elif s >= d: dist['D'] += 1
                else: dist['E'] += 1
        elif rule.get('method') == 'percentile':
            # 基于排名按百分比分桶（A->E），不依赖具体分数阈值
            ap, bp, cp, dp, ep = [rule.get(k, 0) for k in ['a_pct','b_pct','c_pct','d_pct','e_pct']]
            # 防御：归一化到100
            totp = (ap or 0)+(bp or 0)+(cp or 0)+(dp or 0)+(ep or 0)
            if not totp:
                continue
            from math import ceil
            scores_sorted = sorted(scores, reverse=True)
            nA = ceil(n * (ap/100.0))
            nB = ceil(n * (bp/100.0))
            nC = ceil(n * (cp/100.0))
            nD = ceil(n * (dp/100.0))
            # E 为剩余
            for i, _ in enumerate(scores_sorted, 1):
                if i <= nA: dist['A'] += 1
                elif i <= nA+nB: dist['B'] += 1
                elif i <= nA+nB+nC: dist['C'] += 1
                elif i <= nA+nB+nC+nD: dist['D'] += 1
                else: dist['E'] += 1
        else:
            continue
    return jsonify({"distribution": dict(dist), "total": total})


# 汇总 API
@api_bp.route('/summary', methods=['GET'])
@login_required
def api_summary_list():
    from sqlalchemy import desc
    def _multi(param_name: str):
        # 支持 ?param=a&param=b 或 ?param=a,b
        vals = request.args.getlist(param_name)
        out = []
        for v in vals:
            out.extend([s.strip() for s in v.split(',') if s.strip()])
        return out

    exam_names = _multi('exam_name')
    grade_levels = _multi('grade_level')
    class_names = _multi('class_name')
    subject_code = request.args.get('subject_code') or 'TOTAL'
    order_by = request.args.get('order_by') or 'score_desc'

    # 查询匹配的成绩（按考试名称与科目）
    q = Grade.query.join(Student).join(Course)
    if exam_names:
        q = q.filter(Grade.exam_name.in_(exam_names))
    if grade_levels:
        q = q.filter(Student.grade_level.in_(grade_levels))
    if class_names:
        q = q.filter(Student.class_name.in_(class_names))
    # 非管理员可见范围限制
    if not current_user.is_anonymous and current_user.role != 'admin':
        if current_user.allowed_grade_levels:
            allowed = [s.strip() for s in current_user.allowed_grade_levels.split(',') if s.strip()]
            if allowed:
                q = q.filter(Student.grade_level.in_(allowed))
        if current_user.allowed_class_names:
            allowed = [s.strip() for s in current_user.allowed_class_names.split(',') if s.strip()]
            if allowed:
                q = q.filter(Student.class_name.in_(allowed))
    if subject_code:
        q = q.filter(Course.code == subject_code)

    # 分页参数
    page = request.args.get('page', type=int) or 1
    page_size = min(max(request.args.get('page_size', type=int) or 50, 1), 1000)

    # 简化 COUNT：去除排序，仅对过滤后的结果进行计数
    total = q.with_entities(db.func.count()).scalar()
    rows = q.offset((page-1)*page_size).limit(page_size).all()

    # 慢请求 SQL 摘要（仅在 DEBUG 或 DIAG_SQL_LOG 开启时）
    try:
        if current_app.debug or current_app.config.get('DIAG_SQL_LOG', False):
            import logging, time
            threshold = current_app.config.get('SLOW_QUERY_MS', 500)
            # 仅粗略记录分页查询耗时
            # 如有需要可精细化到 COUNT/列表分开计时，这里以 rows 拉取为准
            # 由于我们没有显式计时开始点，简化处理：略过
            comp = q.statement.compile(dialect=db.engine.dialect, compile_kwargs={"literal_binds": True})
            sql_snippet = str(comp)
            if len(sql_snippet) > 300:
                sql_snippet = sql_snippet[:300] + '...'
            # 不知道实际耗时，只有在页面层或全局 after_request 记录；此处直接输出片段以便诊断
            logging.getLogger('slow').warning(f"SUMMARY SQL: {sql_snippet}")
    except Exception:
        pass
    items = []

    # 规则版本（发布的最新版本号），便于展示来源
    published_set = None
    rule_version = None
    if exam_names and len(exam_names) == 1:
        published_set = GradeBandSet.query.filter_by(exam_name=exam_names[0], status='published').order_by(GradeBandSet.version.desc()).first()
        if published_set:
            rule_version = published_set.version

    # 准备满分缓存 (exam_type, subject_code) -> max_score
    max_cache = {}

    # 计算班级/年级排名：需要同班/同年级的集合
    # 先聚合：key -> list of (student_id, score)
    from collections import defaultdict
    by_class = defaultdict(list)
    by_grade = defaultdict(list)
    for g in rows:
        by_class[g.student.class_name].append((g.student_id, g.score))
        by_grade[g.student.grade_level].append((g.student_id, g.score))

    # 排名映射
    def rank_map(pairs):
        # pairs: list[(student_id, score)]
        pairs_sorted = sorted(pairs, key=lambda x: x[1], reverse=True)
        rank = {}
        for i, (sid, _) in enumerate(pairs_sorted, 1):
            rank[sid] = i
        return rank

    class_rank_map = {k: rank_map(v) for k, v in by_class.items()}
    grade_rank_map = {k: rank_map(v) for k, v in by_grade.items()}

    from app.utils import grade_letter_for
    for g in rows:
        letter = grade_letter_for(g.exam_name or 'default', g.course.code, g.score)
        # 百分比（若配置了满分）
        perc = None
        key = (g.exam_type or 'regular', g.course.code)
        if key in max_cache:
            max_score = max_cache[key]
        else:
            s = ExamScheme.query.filter_by(exam_type=key[0], subject_code=key[1]).first()
            max_score = s.max_score if s else None
            max_cache[key] = max_score
        if max_score and max_score > 0:
            perc = round(float(g.score) / float(max_score) * 100.0, 2)

        items.append({
            'student_id': g.student.student_id,
            'name': g.student.name,
            'class_name': g.student.class_name,
            'grade_level': g.student.grade_level,
            'score': g.score,
            'percentage': perc,
            'letter': letter,
            'class_rank': class_rank_map.get(g.student.class_name, {}).get(g.student_id),
            'grade_rank': grade_rank_map.get(g.student.grade_level, {}).get(g.student_id),
            'rule_version': rule_version,
        })

    # 排序
    if order_by == 'score_desc':
        items.sort(key=lambda x: x['score'], reverse=True)
    elif order_by == 'score_asc':
        items.sort(key=lambda x: x['score'])
    elif order_by == 'class_rank':
        items.sort(key=lambda x: (x['class_name'] or '', x['class_rank'] or 1e9))
    elif order_by == 'grade_rank':
        items.sort(key=lambda x: (x['grade_level'] or '', x['grade_rank'] or 1e9))

    return jsonify({'items': items, 'total': total, 'page': page, 'page_size': page_size, 'rule_version': rule_version})


@api_bp.route('/summary/prefs', methods=['GET', 'PUT'])
@login_required
def api_summary_prefs():
    from app.models import UserPreference
    import json
    key = 'summary_prefs'
    if request.method == 'PUT':
        data = request.get_json(force=True)
        # 兼容新增字段：trend_chrono + trend_toggles
        if 'trend_chrono' not in data:
            data['trend_chrono'] = False
        if 'trend_toggles' not in data or not isinstance(data.get('trend_toggles'), dict):
            data['trend_toggles'] = {
                'avg': True, 'med': True, 'band': True, 'max': True, 'min': True
            }
        # 兼容新增字段：class compare 偏好
        if 'class_compare' not in data or not isinstance(data.get('class_compare'), dict):
            data['class_compare'] = {'only_meets': False, 'sort_by': 'avg', 'min_count': 0}
        else:
            if 'only_meets' not in data['class_compare']:
                data['class_compare']['only_meets'] = False
            if data['class_compare'].get('sort_by') not in ('avg','count'):
                data['class_compare']['sort_by'] = 'avg'
            if 'min_count' not in data['class_compare']:
                data['class_compare']['min_count'] = 0
            if 'export_only_meets' not in data['class_compare']:
                data['class_compare']['export_only_meets'] = False
        pref = UserPreference.query.filter_by(user_id=current_user.id, key=key).first()
        if not pref:
            pref = UserPreference(user_id=current_user.id, key=key, value='{}')
            db.session.add(pref)
        pref.value = json.dumps(data, ensure_ascii=False)
        db.session.commit()
        return jsonify({'message': 'ok'})
    # GET
    pref = UserPreference.query.filter_by(user_id=current_user.id, key=key).first()
    if not pref:
        # 迁移旧 key：summary_columns
        legacy = UserPreference.query.filter_by(user_id=current_user.id, key='summary_columns').first()
        base = {
            'letter': True, 'class_rank': True, 'grade_rank': True,
            'trend_chrono': False,
            'trend_toggles': {'avg': True, 'med': True, 'band': True, 'max': True, 'min': True},
            'class_compare': {'only_meets': False, 'sort_by': 'avg', 'min_count': 0, 'export_only_meets': False}
        }
        if legacy:
            try:
                lv = json.loads(legacy.value or '{}')
                for k in ['letter','class_rank','grade_rank']:
                    if k in lv:
                        base[k] = bool(lv[k])
            except Exception:
                pass
        # 持久化迁移结果
        pref = UserPreference(user_id=current_user.id, key=key, value=json.dumps(base, ensure_ascii=False))
        db.session.add(pref)
        db.session.commit()
        return jsonify(base)
    try:
        val = json.loads(pref.value)
        # 合并默认值，防止旧数据缺字段
        if 'trend_chrono' not in val:
            val['trend_chrono'] = False
        if 'trend_toggles' not in val or not isinstance(val.get('trend_toggles'), dict):
            val['trend_toggles'] = {'avg': True, 'med': True, 'band': True, 'max': True, 'min': True}
        else:
            for k in ['avg','med','band','max','min']:
                if k not in val['trend_toggles']:
                    val['trend_toggles'][k] = True
        if 'class_compare' not in val or not isinstance(val.get('class_compare'), dict):
            val['class_compare'] = {'only_meets': False, 'sort_by': 'avg', 'min_count': 0, 'export_only_meets': False}
        else:
            if 'min_count' not in val['class_compare']:
                val['class_compare']['min_count'] = 0
            if 'export_only_meets' not in val['class_compare']:
                val['class_compare']['export_only_meets'] = False
            if 'only_meets' not in val['class_compare']:
                val['class_compare']['only_meets'] = False
            if val['class_compare'].get('sort_by') not in ('avg','count'):
                val['class_compare']['sort_by'] = 'avg'
        return jsonify(val)
    except Exception:
        return jsonify({
            'letter': True, 'class_rank': True, 'grade_rank': True,
            'trend_chrono': False,
            'trend_toggles': {'avg': True, 'med': True, 'band': True, 'max': True, 'min': True},
            'class_compare': {'only_meets': False, 'sort_by': 'avg', 'min_count': 0, 'export_only_meets': False}
        })


@api_bp.route('/summary/export', methods=['GET'])
@login_required
def api_summary_export():
    # 复用过滤逻辑
    def _multi(param_name: str):
        vals = request.args.getlist(param_name)
        out = []
        for v in vals:
            out.extend([s.strip() for s in v.split(',') if s.strip()])
        return out

    exam_names = _multi('exam_name')
    grade_levels = _multi('grade_level')
    class_names = _multi('class_name')
    subject_code = request.args.get('subject_code') or 'TOTAL'
    fmt = request.args.get('format') or 'csv'

    q = Grade.query.join(Student).join(Course)
    if exam_names:
        q = q.filter(Grade.exam_name.in_(exam_names))
    if grade_levels:
        q = q.filter(Student.grade_level.in_(grade_levels))
    if class_names:
        q = q.filter(Student.class_name.in_(class_names))
    if subject_code:
        q = q.filter(Course.code == subject_code)
    # 非管理员可见范围限制
    if not current_user.is_anonymous and current_user.role != 'admin':
        if current_user.allowed_grade_levels:
            allowed = [s.strip() for s in current_user.allowed_grade_levels.split(',') if s.strip()]
            if allowed:
                q = q.filter(Student.grade_level.in_(allowed))
        if current_user.allowed_class_names:
            allowed = [s.strip() for s in current_user.allowed_class_names.split(',') if s.strip()]
            if allowed:
                q = q.filter(Student.class_name.in_(allowed))

    # scope: current_page | all
    scope = request.args.get('scope') or 'all'
    order_by = request.args.get('order_by') or 'score_desc'
    page = request.args.get('page', type=int) or 1
    page_size = min(max(request.args.get('page_size', type=int) or 50, 1), 1000)

    # 排序
    if order_by == 'score_desc':
        q = q.order_by(Grade.score.desc())
    elif order_by == 'score_asc':
        q = q.order_by(Grade.score.asc())

    if scope == 'current_page':
        q = q.offset((page-1)*page_size).limit(page_size)

    rows = q.all()

    # 计算班级/年级排名
    from collections import defaultdict
    by_class = defaultdict(list)
    by_grade = defaultdict(list)
    for g in rows:
        by_class[g.student.class_name].append((g.student_id, g.score))
        by_grade[g.student.grade_level].append((g.student_id, g.score))

    def rank_map(pairs):
        pairs_sorted = sorted(pairs, key=lambda x: x[1], reverse=True)
        rank = {}
        for i, (sid, _) in enumerate(pairs_sorted, 1):
            rank[sid] = i
        return rank

    class_rank_map = {k: rank_map(v) for k, v in by_class.items()}
    grade_rank_map = {k: rank_map(v) for k, v in by_grade.items()}

    # 规则版本（仅单考试名时）
    rule_version = None
    if exam_names and len(exam_names) == 1:
        published_set = GradeBandSet.query.filter_by(exam_name=exam_names[0], status='published').order_by(GradeBandSet.version.desc()).first()
        if published_set:
            rule_version = published_set.version

    # 百分比计算缓存
    max_cache = {}

    # 列选择
    columns_param = request.args.get('columns')
    selected_cols = [c.strip() for c in columns_param.split(',')] if columns_param else None

    # 内部字段与导出表头映射
    header_map = {
        'student_id': '学号',
        'name': '姓名',
        'class_name': '班级',
        'grade_level': '年级',
        'score': '分数',
        'percentage': '百分比',
        'letter': '等第',
        'class_rank': '班级排名',
        'grade_rank': '年级排名',
        'rule_version': '规则版本',
    }

    # 默认列
    default_cols = ['student_id','name','class_name','grade_level','score','letter']
    use_cols = [c for c in (selected_cols or default_cols) if c in header_map]

    # 组装数据
    from app.utils import grade_letter_for
    data_rows = []
    for g in rows:
        # 百分比
        perc = None
        key = (g.exam_type or 'regular', g.course.code)
        if key in max_cache:
            max_score = max_cache[key]
        else:
            s = ExamScheme.query.filter_by(exam_type=key[0], subject_code=key[1]).first()
            max_score = s.max_score if s else None
            max_cache[key] = max_score
        if max_score and max_score > 0:
            perc = round(float(g.score) / float(max_score) * 100.0, 2)

        rec = {
            'student_id': g.student.student_id,
            'name': g.student.name,
            'class_name': g.student.class_name,
            'grade_level': g.student.grade_level,
            'score': g.score,
            'percentage': perc,
            'letter': grade_letter_for(g.exam_name or 'default', g.course.code, g.score),
            'class_rank': class_rank_map.get(g.student.class_name, {}).get(g.student_id),
            'grade_rank': grade_rank_map.get(g.student.grade_level, {}).get(g.student_id),
            'rule_version': rule_version,
        }
        data_rows.append(rec)

    # 生成导出结构
    export_rows = []
    for rec in data_rows:
        row = { header_map[col]: rec.get(col, '') for col in use_cols }
        export_rows.append(row)

    # 组装文件名片段（包含考试、学科、年级、班级）
    def _safe_name(s: str) -> str:
        import re
        return re.sub(r'[^\w\-\u4e00-\u9fa5]+', '_', s)[:40]
    import datetime as _dt
    ts = _dt.datetime.now().strftime('%Y%m%d_%H%M%S')
    name_exam = '-'.join(exam_names) if exam_names else '全部考试'
    name_subject = subject_code or '全部学科'
    name_gl = '-'.join(grade_levels) if grade_levels else '全部年级'
    name_cl = '-'.join(class_names) if class_names else '全部班级'
    scope = request.args.get('scope') or 'all'
    order_by = request.args.get('order_by') or 'score_desc'
    base_name = f"{_safe_name(name_exam)}_{_safe_name(name_subject)}_{_safe_name(name_gl)}_{_safe_name(name_cl)}_{_safe_name(scope)}_{_safe_name(order_by)}_{ts}"

    if fmt == 'xlsx':
        # 仍保留同步导出
        try:
            from openpyxl import Workbook
            wb = Workbook(write_only=True)
            ws = wb.create_sheet()
            ws.append([header_map[c] for c in use_cols])
            for rec in data_rows:
                ws.append([rec.get(c, '') for c in use_cols])
            buf = io.BytesIO()
            wb.save(buf)
            buf.seek(0)
            return send_file(buf, as_attachment=True, download_name=f'{base_name}.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        except Exception:
            import pandas as pd
            buf = io.BytesIO()
            pd.DataFrame([{header_map[c]: r.get(c, '') for c in use_cols} for r in data_rows]).to_excel(buf, index=False)
            buf.seek(0)
            return send_file(buf, as_attachment=True, download_name=f'{base_name}.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    # 默认csv（流式写出，降低内存占用）
    import csv
    def generate_csv():
        yield '\ufeff'
        header = [header_map[c] for c in use_cols]
        sio = io.StringIO()
        writer = csv.writer(sio)
        writer.writerow(header)
        yield sio.getvalue()
        sio.seek(0); sio.truncate(0)
        for rec in data_rows:
            writer.writerow([rec.get(c, '') for c in use_cols])
            yield sio.getvalue()
            sio.seek(0); sio.truncate(0)
    return Response(stream_with_context(generate_csv()), mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename={base_name}.csv'})


# 导出异步化（轻量线程）
from threading import Thread
import uuid
import os

_export_tasks = {}

class ExportTask:
    def __init__(self, task_id, user_id, params):
        self.id = task_id
        self.user_id = user_id
        self.params = params
        self.status = 'pending'
        self.progress = 0
        self.file = None
        self.error = None
        self.created_at = dt.datetime.utcnow()
        self.finished_at = None

    def to_dict(self):
        import os as _os
        # 构造筛选摘要
        p = self.params or {}
        def _join(v):
            if isinstance(v, list):
                return ','.join(v)
            return str(v or '')
        summary = f"考试:{_join(p.get('exam_name') or p.get('exam_names'))} 学科:{p.get('subject_code') or ''} 年级:{_join(p.get('grade_level') or p.get('grade_levels'))} 班级:{_join(p.get('class_name') or p.get('class_names'))} 范围:{p.get('scope') or 'all'} 排序:{p.get('order_by') or 'score_desc'}"
        file_ready = bool(self.file and _os.path.isfile(self.file) and self.status=='completed')
        file_size = _os.path.getsize(self.file) if file_ready else None
        d = {
            'task_id': self.id,
            'status': self.status,
            'progress': self.progress,
            'file': self.file,
            'filename': _os.path.basename(self.file) if self.file else None,
            'file_ready': file_ready,
            'file_size': file_size,
            'error': self.error,
            'created_at': self.created_at.isoformat() + 'Z',
            'finished_at': self.finished_at.isoformat() + 'Z' if self.finished_at else None,
            'summary': summary,
            'params': p,
        }
        return d

@api_bp.route('/export/tasks', methods=['POST'])
@login_required
def api_export_task_create():
    # 接收与 /api/summary/export 相同的查询参数
    params = request.get_json(force=True) or {}
    user_id = current_user.id

    # 并发限制
    max_c = current_app.config.get('EXPORT_MAX_CONCURRENT_PER_USER', 2)
    running = ExportJob.query.filter(ExportJob.user_id==user_id, ExportJob.status.in_(['pending','running'])).count()
    if running >= max_c:
        return jsonify({'error':'too_many_tasks', 'message': f'已有 {running} 个导出任务在进行中（上限 {max_c}），请稍候再试'}), 429

    task_id = str(uuid.uuid4())
    _export_tasks[task_id] = ExportTask(task_id, user_id, params)
    # 持久化记录
    try:
        from json import dumps
        job = ExportJob(id=task_id, user_id=user_id, params=dumps(params, ensure_ascii=False), status='pending', progress=0)
        db.session.add(job); db.session.commit()
    except Exception:
        db.session.rollback()

    def worker(task_id, params, user_id):
        try:
            t = _export_tasks.get(task_id)
            if not t: return
            t.status = 'running'; t.progress = 10
            # 复用逻辑：构建查询，与同步导出一致
            with current_app.app_context():
                # 更新DB为running
                try:
                    job = ExportJob.query.get(task_id)
                    if job:
                        job.status = 'running'; job.progress = 10; db.session.commit()
                except Exception:
                    db.session.rollback()
                from copy import deepcopy
                args = deepcopy(params)
                # 将用户可见范围注入参数（按创建者）
                user = User.query.get(user_id)
                if user and user.role != 'admin':
                    if user.allowed_grade_levels and not args.get('grade_level'):
                        args['grade_level'] = user.allowed_grade_levels
                    if user.allowed_class_names and not args.get('class_name'):
                        args['class_name'] = user.allowed_class_names
                # 生成文件名与导出目录
                export_dir = current_app.config.get('EXPORT_DIR', 'exports')
                os.makedirs(export_dir, exist_ok=True)
                # 调用一个内部函数生成文件
                filepath = _build_export_file(args, export_dir)
                t.status = 'completed'; t.file = filepath; t.progress = 100; t.finished_at = dt.datetime.utcnow()
                try:
                    job = ExportJob.query.get(task_id)
                    if job:
                        job.status = 'completed'; job.progress = 100; job.file_path = filepath; job.finished_at = dt.datetime.utcnow()
                        db.session.commit()
                except Exception:
                    db.session.rollback()
        except Exception as e:
            t = _export_tasks.get(task_id)
            if t:
                t.status = 'failed'; t.error = str(e)
            try:
                job = ExportJob.query.get(task_id)
                if job:
                    job.status = 'failed'; job.error = str(e); job.finished_at = dt.datetime.utcnow()
                    db.session.commit()
            except Exception:
                db.session.rollback()
        try:
            t = _export_tasks.get(task_id)
            if not t: return
            t.status = 'running'; t.progress = 10
            # 复用逻辑：构建查询，与同步导出一致
            with current_app.app_context():
                from copy import deepcopy
                args = deepcopy(params)
                # 将用户可见范围注入参数
                if current_user.is_anonymous or current_user.role == 'admin':
                    pass
                else:
                    if current_user.allowed_grade_levels:
                        args['grade_level'] = args.get('grade_level') or current_user.allowed_grade_levels
                    if current_user.allowed_class_names:
                        args['class_name'] = args.get('class_name') or current_user.allowed_class_names
                # 生成文件名与导出目录
                export_dir = current_app.config.get('EXPORT_DIR', 'exports')
                os.makedirs(export_dir, exist_ok=True)
                # 调用一个内部函数生成文件
                filepath = _build_export_file(args, export_dir)
                t.status = 'completed'; t.file = filepath; t.progress = 100; t.finished_at = dt.datetime.utcnow()
                try:
                    job = ExportJob.query.get(task_id)
                    if job:
                        job.status = 'completed'; job.progress = 100; job.file_path = filepath; job.finished_at = dt.datetime.utcnow()
                        db.session.commit()
                except Exception:
                    db.session.rollback()
        except Exception as e:
            t = _export_tasks.get(task_id)
            if t:
                t.status = 'failed'; t.error = str(e)
            try:
                job = ExportJob.query.get(task_id)
                if job:
                    job.status = 'failed'; job.error = str(e); job.finished_at = dt.datetime.utcnow()
                    db.session.commit()
            except Exception:
                db.session.rollback()

    _cleanup_exports_once()
    Thread(target=worker, args=(task_id, params, user_id), daemon=True).start()
    return jsonify({ 'task_id': task_id })


@api_bp.route('/export/tasks/<task_id>', methods=['GET'])
@login_required
def api_export_task_status(task_id):
    t = _export_tasks.get(task_id)
    if not t:
        # 回退到持久化记录
        job = ExportJob.query.get(task_id)
        if not job:
            return jsonify({ 'error': 'not found' }), 404
        if current_user.role != 'admin' and job.user_id != current_user.id:
            return jsonify({ 'error': 'forbidden' }), 403
        from json import loads
        import os as _os
        p = loads(job.params)
        def _join(v):
            if isinstance(v, list):
                return ','.join(v)
            return str(v or '')
        summary = f"考试:{_join(p.get('exam_name') or p.get('exam_names'))} 学科:{p.get('subject_code') or ''} 年级:{_join(p.get('grade_level') or p.get('grade_levels'))} 班级:{_join(p.get('class_name') or p.get('class_names'))} 范围:{p.get('scope') or 'all'} 排序:{p.get('order_by') or 'score_desc'}"
        file_ready = bool(job.file_path and _os.path.isfile(job.file_path) and job.status=='completed')
        file_size = _os.path.getsize(job.file_path) if file_ready else None
        return jsonify({
            'task_id': job.id,
            'status': job.status,
            'progress': job.progress,
            'filename': _os.path.basename(job.file_path) if job.file_path else None,
            'file_ready': file_ready,
            'file_size': file_size,
            'created_at': job.created_at.isoformat()+'Z' if job.created_at else None,
            'finished_at': job.finished_at.isoformat()+'Z' if job.finished_at else None,
            'summary': summary,
            'params': p,
        })
    # 仅本人或管理员可查
    if current_user.role != 'admin' and t.user_id != current_user.id:
        return jsonify({ 'error': 'forbidden' }), 403
    return jsonify(t.to_dict())



import hmac, hashlib, base64, time

def _sign_download_token(task_id: str, user_id: int, ttl: int) -> str:
    secret = (current_app.config.get('SECRET_KEY') or 'secret').encode('utf-8')
    exp = int(time.time()) + int(ttl)
    payload = f"{task_id}.{user_id}.{exp}".encode('utf-8')
    sig = hmac.new(secret, payload, hashlib.sha256).digest()
    token = base64.urlsafe_b64encode(payload + b'.' + sig).decode('utf-8')
    return token


def _verify_download_token(token: str):
    try:
        raw = base64.urlsafe_b64decode(token.encode('utf-8'))
        parts = raw.split(b'.')
        if len(parts) != 4:
            return None
        task_id = parts[0].decode('utf-8')
        user_id = int(parts[1].decode('utf-8'))
        exp = int(parts[2].decode('utf-8'))
        sig = parts[3]
        secret = (current_app.config.get('SECRET_KEY') or 'secret').encode('utf-8')
        mac = hmac.new(secret, (parts[0]+b'.'+parts[1]+b'.'+parts[2]), hashlib.sha256).digest()
        if not hmac.compare_digest(mac, sig):
            return None
        if time.time() > exp:
            return None
        return { 'task_id': task_id, 'user_id': user_id, 'exp': exp }
    except Exception:
        return None


@api_bp.route('/export/tasks/<task_id>/signed-url', methods=['GET'])
@login_required
def api_export_task_signed_url(task_id):
    # 仅管理员或创建者可生成
    job = ExportJob.query.get(task_id)
    if not job:
        return jsonify({'error':'not found'}), 404
    if current_user.role != 'admin' and job.user_id != current_user.id:
        return jsonify({'error':'forbidden'}), 403
    ttl = current_app.config.get('DOWNLOAD_LINK_TTL_SECONDS', 3600)
    token = _sign_download_token(task_id, job.user_id, ttl)
    url = url_for('api.api_export_task_download_signed', token=token, _external=True)
    return jsonify({ 'url': url, 'ttl_seconds': ttl })


@api_bp.route('/export/download', methods=['GET'])
@login_required
def api_export_task_download_signed():
    token = request.args.get('token')
    data = _verify_download_token(token or '')
    if not data:
        return jsonify({'error':'invalid_or_expired'}), 400
    task_id = data['task_id']; user_id = data['user_id']
    # 校验 DB 与文件存在
    job = ExportJob.query.get(task_id)
    if not job:
        return jsonify({'error':'not found'}), 404
    if current_user.role != 'admin' and user_id != current_user.id:
        return jsonify({'error':'forbidden'}), 403
    if job.status != 'completed' or not job.file_path or not os.path.isfile(job.file_path):
        return jsonify({'error':'not ready'}), 400
    return send_file(job.file_path, as_attachment=True)

@api_bp.route('/export/tasks/<task_id>/download', methods=['GET'])
@login_required
def api_export_task_download(task_id):
    t = _export_tasks.get(task_id)
    if not t:
        # 回退到持久化
        job = ExportJob.query.get(task_id)
        if not job:
            return jsonify({ 'error': 'not found' }), 404
        if current_user.role != 'admin' and job.user_id != current_user.id:
            return jsonify({ 'error': 'forbidden' }), 403
        if job.status != 'completed' or not job.file_path or not os.path.isfile(job.file_path):
            return jsonify({ 'error': 'not ready' }), 400
        return send_file(job.file_path, as_attachment=True)
    if current_user.role != 'admin' and t.user_id != current_user.id:
        return jsonify({ 'error': 'forbidden' }), 403
    if t.status != 'completed':
        return jsonify({ 'error': 'not ready' }), 400
    return send_file(t.file, as_attachment=True)


@api_bp.route('/export/my-tasks', methods=['GET'])
@login_required
def api_export_my_tasks():
    page = request.args.get('page', type=int) or 1
    page_size = min(max(request.args.get('page_size', type=int) or 20, 1), 200)
    status = request.args.get('status')  # pending|running|completed|failed
    qstr = (request.args.get('q') or '').strip()
    q = ExportJob.query
    if current_user.role != 'admin':
        q = q.filter(ExportJob.user_id == current_user.id)
    if status:
        q = q.filter(ExportJob.status == status)
    if qstr:
        like = f"%{qstr}%"
        from sqlalchemy import or_
        q = q.filter(or_(ExportJob.id.ilike(like), ExportJob.file_path.ilike(like)))
    total = q.count()
    rows = q.order_by(ExportJob.created_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    def to_obj(j):
        from json import loads
        import os as _os
        p = loads(j.params)
        # 构造筛选摘要
        def _join(v):
            if isinstance(v, list):
                return ','.join(v)
            return str(v or '')
        summary = f"考试:{_join(p.get('exam_name') or p.get('exam_names'))} 学科:{p.get('subject_code') or ''} 年级:{_join(p.get('grade_level') or p.get('grade_levels'))} 班级:{_join(p.get('class_name') or p.get('class_names'))} 范围:{p.get('scope') or 'all'} 排序:{p.get('order_by') or 'score_desc'}"
        file_ready = bool(j.file_path and _os.path.isfile(j.file_path) and j.status=='completed')
        file_size = _os.path.getsize(j.file_path) if file_ready else None
        return {
            'task_id': j.id,
            'user_id': j.user_id,
            'status': j.status,
            'progress': j.progress,
            'filename': _os.path.basename(j.file_path) if j.file_path else None,
            'file_ready': file_ready,
            'file_size': file_size,
            'created_at': j.created_at.isoformat()+'Z' if j.created_at else None,
            'finished_at': j.finished_at.isoformat()+'Z' if j.finished_at else None,
            'summary': summary,
            'params': p,
        }
    return jsonify({ 'items': [to_obj(r) for r in rows], 'total': total, 'page': page, 'page_size': page_size })


@api_bp.route('/export/my-tasks/batch', methods=['DELETE'])
@login_required
def api_export_my_tasks_batch_delete():
    data = request.get_json(force=True) or {}
    ids = data.get('ids') or []
    status = data.get('status')
    q = ExportJob.query
    if current_user.role != 'admin':
        q = q.filter(ExportJob.user_id == current_user.id)
    if status:
        q = q.filter(ExportJob.status == status)
    elif ids:
        q = q.filter(ExportJob.id.in_(ids))
    else:
        return jsonify({'error':'no_target'}), 400
    rows = q.all()
    removed = 0
    for job in rows:
        try:
            if job.file_path and os.path.isfile(job.file_path):
                os.remove(job.file_path)
        except Exception:
            pass
        db.session.delete(job)
        removed += 1
        _export_tasks.pop(job.id, None)
    db.session.commit()
    return jsonify({'removed': removed})


# 简易清理任务：删除过期导出文件（在应用启动后首次调用时触发一次）
_last_cleanup = None

def _cleanup_exports_once():
    global _last_cleanup
    import time
    now = time.time()
    if _last_cleanup and now - _last_cleanup < 3600:
        return
    _last_cleanup = now
    try:
        export_dir = current_app.config.get('EXPORT_DIR', 'exports')
        days = current_app.config.get('EXPORT_RETENTION_DAYS', 7)
        cutoff = now - days*86400
        if os.path.isdir(export_dir):
            for name in os.listdir(export_dir):
                path = os.path.join(export_dir, name)
                try:
                    if os.path.isfile(path) and os.path.getmtime(path) < cutoff:
                        os.remove(path)
                except Exception:
                    pass
    except Exception:
        pass


@api_bp.route('/config/branding', methods=['GET'])
@login_required
def api_config_branding():
    # 简单返回可选品牌信息；未来可改为从数据库/配置文件读取
    base = {
        'school_name': current_app.config.get('BRAND_SCHOOL_NAME', '某某学校'),
        'school_name_full': current_app.config.get('BRAND_SCHOOL_NAME_FULL', None),
        'subtitle': current_app.config.get('BRAND_REPORT_SUBTITLE', '学业质量监测报告'),
        'cover_color': current_app.config.get('BRAND_REPORT_COVER_COLOR', '#0d6efd'),
        'header_text': current_app.config.get('BRAND_HEADER_TEXT', None),
        'footer_text': current_app.config.get('BRAND_FOOTER_TEXT', None),
        'logo_url': url_for('static', filename='logo.png', _external=False),
    }
    return jsonify(base)

    global _last_cleanup
    import time
    now = time.time()
    if _last_cleanup and now - _last_cleanup < 3600:
        return
    _last_cleanup = now
    try:
        export_dir = current_app.config.get('EXPORT_DIR', 'exports')
        days = current_app.config.get('EXPORT_RETENTION_DAYS', 7)
        cutoff = now - days*86400
        if os.path.isdir(export_dir):
            for name in os.listdir(export_dir):
                path = os.path.join(export_dir, name)
                try:
                    if os.path.isfile(path) and os.path.getmtime(path) < cutoff:
                        os.remove(path)
                except Exception:
                    pass
    except Exception:
        pass

# 删除任务与文件
@api_bp.route('/export/my-tasks/<task_id>', methods=['DELETE'])
@login_required
def api_export_task_delete(task_id):
    job = ExportJob.query.get(task_id)
    if not job:
        return jsonify({'error': 'not found'}), 404
    if current_user.role != 'admin' and job.user_id != current_user.id:
        return jsonify({'error': 'forbidden'}), 403
    try:
        if job.file_path and os.path.isfile(job.file_path):
            os.remove(job.file_path)
    except Exception:
        pass
    db.session.delete(job); db.session.commit()
    # 同时清理内存缓存
    if task_id in _export_tasks:
        _export_tasks.pop(task_id, None)
    return jsonify({'message': 'deleted'})

# 在任务创建时尝试触发一次清理


def _build_export_file(params: dict, export_dir: str) -> str:
    """按 /api/summary/export 的逻辑生成文件并返回路径"""
    # 复用参数解析
    def _multi_param(val):
        out = []
        if isinstance(val, list):
            for v in val:
                out.extend([s.strip() for s in str(v).split(',') if s.strip()])
        elif isinstance(val, str):
            out.extend([s.strip() for s in val.split(',') if s.strip()])
        return out

    exam_names = _multi_param(params.get('exam_name') or params.get('exam_names') or [])
    grade_levels = _multi_param(params.get('grade_level') or params.get('grade_levels') or [])
    class_names = _multi_param(params.get('class_name') or params.get('class_names') or [])
    subject_code = params.get('subject_code') or 'TOTAL'
    fmt = params.get('format') or 'csv'
    scope = params.get('scope') or 'all'
    order_by = params.get('order_by') or 'score_desc'

    # 组装查询（与 api_summary_export 一致的过滤）
    q = Grade.query.join(Student).join(Course)
    if exam_names:
        q = q.filter(Grade.exam_name.in_(exam_names))
    if grade_levels:
        q = q.filter(Student.grade_level.in_(grade_levels))
    if class_names:
        q = q.filter(Student.class_name.in_(class_names))
    if subject_code:
        q = q.filter(Course.code == subject_code)
    # 非管理员可见范围：后台任务默认使用当前用户上下文，这里省略，生产可改为传入用户ID按其限制

    # 排序
    if order_by == 'score_desc':
        q = q.order_by(Grade.score.desc())
    elif order_by == 'score_asc':
        q = q.order_by(Grade.score.asc())

    # 范围
    if scope == 'current_page':
        page = int(params.get('page') or 1)
        page_size = int(params.get('page_size') or 50)
        q = q.offset((page-1)*page_size).limit(page_size)

    rows = q.all()

    # 列控制
    columns_param = params.get('columns')
    selected_cols = [c.strip() for c in columns_param.split(',')] if columns_param else None
    header_map = {
        'student_id': '学号',
        'name': '姓名',
        'class_name': '班级',
        'grade_level': '年级',
        'score': '分数',
        'percentage': '百分比',
        'letter': '等第',
        'class_rank': '班级排名',
        'grade_rank': '年级排名',
        'rule_version': '规则版本',
    }
    default_cols = ['student_id','name','class_name','grade_level','score','letter']
    use_cols = [c for c in (selected_cols or default_cols) if c in header_map]

    # 计算辅助
    from app.utils import grade_letter_for
    max_cache = {}
    from collections import defaultdict
    by_class = defaultdict(list)
    by_grade = defaultdict(list)
    for g in rows:
        by_class[g.student.class_name].append((g.student_id, g.score))
        by_grade[g.student.grade_level].append((g.student_id, g.score))
    def rank_map(pairs):
        pairs_sorted = sorted(pairs, key=lambda x: x[1], reverse=True)
        return { sid: i for i, (sid, _) in enumerate(pairs_sorted, 1) }
    class_rank_map = {k: rank_map(v) for k, v in by_class.items()}
    grade_rank_map = {k: rank_map(v) for k, v in by_grade.items()}

    data_rows = []
    for g in rows:
        key = (g.exam_type or 'regular', g.course.code)
        if key in max_cache:
            max_score = max_cache[key]
        else:
            s = ExamScheme.query.filter_by(exam_type=key[0], subject_code=key[1]).first()
            max_score = s.max_score if s else None
            max_cache[key] = max_score
        perc = round(float(g.score)/float(max_score)*100.0,2) if (max_score and max_score>0) else None
        data_rows.append({
            'student_id': g.student.student_id,
            'name': g.student.name,
            'class_name': g.student.class_name,
            'grade_level': g.student.grade_level,
            'score': g.score,
            'percentage': perc,
            'letter': grade_letter_for(g.exam_name or 'default', g.course.code, g.score),
            'class_rank': class_rank_map.get(g.student.class_name, {}).get(g.student_id),
            'grade_rank': grade_rank_map.get(g.student.grade_level, {}).get(g.student_id),
            'rule_version': None,
        })

    # 文件名
    def _safe_name(s: str) -> str:
        import re
        return re.sub(r'[^\w\-\u4e00-\u9fa5]+', '_', s)[:40]
    import datetime as _dt
    ts = _dt.datetime.now().strftime('%Y%m%d_%H%M%S')
    name_exam = '-'.join(exam_names) if exam_names else '全部考试'
    name_subject = subject_code or '全部学科'
    name_gl = '-'.join(grade_levels) if grade_levels else '全部年级'
    name_cl = '-'.join(class_names) if class_names else '全部班级'
    base_name = f"{_safe_name(name_exam)}_{_safe_name(name_subject)}_{_safe_name(name_gl)}_{_safe_name(name_cl)}_{_safe_name(scope)}_{_safe_name(order_by)}_{ts}"

    # 写文件
    if fmt == 'xlsx':
        try:
            from openpyxl import Workbook
            wb = Workbook(write_only=True)
            ws = wb.create_sheet()
            ws.append([header_map[c] for c in use_cols])
            for rec in data_rows:
                ws.append([rec.get(c, '') for c in use_cols])
            filepath = os.path.join(export_dir, f"{base_name}.xlsx")
            wb.save(filepath)
            return filepath
        except Exception:
            import pandas as pd
            filepath = os.path.join(export_dir, f"{base_name}.xlsx")
            import pandas as pd
            import numpy as np
            import io as _io
            import json as _json
            # 防御性：如环境没有 pandas，则回退 csv
            try:
                pd.DataFrame([{header_map[c]: r.get(c, '') for c in use_cols} for r in data_rows]).to_excel(filepath, index=False)
                return filepath
            except Exception:
                fmt = 'csv'
    # csv
    import csv
    filepath = os.path.join(export_dir, f"{base_name}.csv")
    with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([header_map[c] for c in use_cols])
        for rec in data_rows:
            writer.writerow([rec.get(c, '') for c in use_cols])
    return filepath


@api_bp.route('/summary/options', methods=['GET'])
@login_required
def api_summary_options():
    # 枚举考试名称、年级、班级（应用非管理员可见范围）
    exam_q = db.session.query(Grade.exam_name).distinct()
    gl_q = db.session.query(Student.grade_level).distinct()
    cl_q = db.session.query(Student.class_name).distinct()

    if not current_user.is_anonymous and current_user.role != 'admin':
        if current_user.allowed_grade_levels:
            allowed = [s.strip() for s in current_user.allowed_grade_levels.split(',') if s.strip()]
            if allowed:
                gl_q = gl_q.filter(Student.grade_level.in_(allowed))
        if current_user.allowed_class_names:
            allowed = [s.strip() for s in current_user.allowed_class_names.split(',') if s.strip()]
            if allowed:
                cl_q = cl_q.filter(Student.class_name.in_(allowed))

    exam_names = sorted({ n[0] for n in exam_q.all() if n[0] })
    grade_levels = sorted({ n[0] for n in gl_q.all() if n[0] })
    class_names = sorted({ n[0] for n in cl_q.all() if n[0] })
    return jsonify({ 'exam_names': exam_names, 'grade_levels': grade_levels, 'class_names': class_names })


# 诊断 API（管理员）：构造典型查询，返回 EXPLAIN 计划与耗时
@api_bp.route('/diagnostics/run', methods=['POST'])
@login_required
def api_diagnostics_run():
    if current_user.role != 'admin':
        return jsonify({'error': 'forbidden'}), 403
    import time
    from sqlalchemy import text
    payload = request.get_json(force=True) or {}
    exam_names = payload.get('exam_names') or []
    grade_levels = payload.get('grade_levels') or []
    class_names = payload.get('class_names') or []
    subject_code = payload.get('subject_code') or 'TOTAL'
    order_by = payload.get('order_by') or 'score_desc'
    page = int(payload.get('page') or 1)
    page_size = int(payload.get('page_size') or 50)

    def build_q(base_q):
        q = base_q
        if exam_names:
            q = q.filter(Grade.exam_name.in_(exam_names))
        if grade_levels:
            q = q.filter(Student.grade_level.in_(grade_levels))
        if class_names:
            q = q.filter(Student.class_name.in_(class_names))
        if subject_code:
            q = q.filter(Course.code == subject_code)
        if order_by == 'score_desc':
            q = q.order_by(Grade.score.desc())
        elif order_by == 'score_asc':
            q = q.order_by(Grade.score.asc())
        return q

    base_q = Grade.query.join(Student).join(Course)
    list_q = build_q(base_q)

    # 计时：count、分页列表
    t0 = time.time()
    total = list_q.with_entities(db.func.count()).scalar()
    t_count = (time.time() - t0) * 1000

    t1 = time.time()
    page_rows = list_q.offset((page-1)*page_size).limit(page_size).all()
    t_page = (time.time() - t1) * 1000

    # EXPLAIN
    engine = db.engine
    dialect = engine.name  # 'sqlite', 'postgresql', 'mysql', ...
    compiled = list_q.statement.compile(dialect=engine.dialect, compile_kwargs={"literal_binds": True})
    sql = str(compiled)
    if dialect == 'sqlite':
        explain_sql = f"EXPLAIN QUERY PLAN {sql}"
    elif dialect == 'postgresql':
        explain_sql = f"EXPLAIN (FORMAT TEXT) {sql}"
    else:
        explain_sql = f"EXPLAIN {sql}"
    rows = engine.execute(text(explain_sql)).fetchall()
    plan = [" ".join([str(x) for x in r]) for r in rows]

    # 慢阈值日志（含 SQL 摘要）
    try:
        import logging
        threshold = current_app.config.get('SLOW_QUERY_MS', 500)
        if t_count > threshold or t_page > threshold:
            snippet = (sql or '')
            if len(snippet) > 300:
                snippet = snippet[:300] + '...'
            logging.getLogger('slow').warning(f"DIAG slow: count={t_count:.1f}ms page={t_page:.1f}ms SQL={snippet}")
    except Exception:
        pass

    return jsonify({
        'filters': {
            'exam_names': exam_names,
            'grade_levels': grade_levels,
            'class_names': class_names,
            'subject_code': subject_code,
            'order_by': order_by,
            'page': page,
            'page_size': page_size,
        },
        'count_ms': round(t_count, 2),
        'page_ms': round(t_page, 2),
        'plan': plan,
        'total': total,
        'page_rows': len(page_rows),
        'dialect': dialect,
        'sql': sql,
    })


# 诊断预设 CRUD（管理员）
@api_bp.route('/diagnostics/presets', methods=['GET'])
@login_required
def api_diag_presets_list():
    if current_user.role != 'admin':
        return jsonify({'error': 'forbidden'}), 403
    mine = DiagnosticPreset.query.filter_by(user_id=current_user.id).order_by(DiagnosticPreset.id.desc()).all()
    shared = DiagnosticPreset.query.filter_by(is_shared=True).order_by(DiagnosticPreset.id.desc()).all()
    import json
    def to_obj(p):
        return { 'id': p.id, 'name': p.name, 'group_name': p.group_name, 'is_shared': p.is_shared, 'payload': json.loads(p.payload) }
    return jsonify({ 'mine': [to_obj(p) for p in mine], 'shared': [to_obj(p) for p in shared] })


@api_bp.route('/diagnostics/presets', methods=['POST'])
@login_required
def api_diag_preset_create():
    if current_user.role != 'admin':
        return jsonify({'error': 'forbidden'}), 403
    data = request.get_json(force=True)
    name = (data.get('name') or '').strip()
    group_name = (data.get('group_name') or '').strip() or None
    is_shared = bool(data.get('is_shared') or False)
    payload = data.get('payload') or {}
    if not name:
        return jsonify({'error': 'name required'}), 400
    import json
    p = DiagnosticPreset(user_id=current_user.id, name=name, group_name=group_name, is_shared=is_shared, payload=json.dumps(payload, ensure_ascii=False))
    db.session.add(p); db.session.commit()
    return jsonify({'id': p.id, 'name': p.name})


@api_bp.route('/diagnostics/presets/<int:preset_id>', methods=['PUT'])
@login_required
def api_diag_preset_rename(preset_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'forbidden'}), 403
    data = request.get_json(force=True)
    name = (data.get('name') or '').strip()
    group_name = (data.get('group_name') or '').strip() or None
    is_shared = data.get('is_shared')
    p = DiagnosticPreset.query.filter_by(id=preset_id, user_id=current_user.id).first_or_404()
    if name:
        p.name = name
    if group_name is not None:
        p.group_name = group_name
    if is_shared is not None:
        p.is_shared = bool(is_shared)
    db.session.commit()
    return jsonify({'message':'renamed'})


@api_bp.route('/diagnostics/presets/<int:preset_id>', methods=['DELETE'])
@login_required
def api_diag_preset_delete(preset_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'forbidden'}), 403
    p = DiagnosticPreset.query.filter_by(id=preset_id, user_id=current_user.id).first_or_404()
    db.session.delete(p)
    db.session.commit()
    return jsonify({'message':'deleted'})


# 用户管理 API（管理员）
@api_bp.route('/users', methods=['GET'])
@login_required
def api_users_list():
    if current_user.role != 'admin':
        return jsonify({'error': 'forbidden'}), 403
    qstr = request.args.get('q', '').strip()
    page = request.args.get('page', type=int) or 1
    page_size = min(max(request.args.get('page_size', type=int) or 20, 1), 200)
    q = User.query
    if qstr:
        like = f"%{qstr}%"
        q = q.filter((User.username.ilike(like)) | (User.email.ilike(like)))
    # COUNT 微缓存：按筛选组合缓存短时间的 total
    try:
        from hashlib import md5
        import json, time
        ttl = current_app.config.get('SUMMARY_COUNT_TTL_SECONDS', 60)
        cache = getattr(current_app, '_summary_count_cache', None)
        if cache is None:
            cache = {}; current_app._summary_count_cache = cache
        key_payload = {
            'exam_names': sorted(exam_names),
            'grade_levels': sorted(grade_levels),
            'class_names': sorted(class_names),
            'subject_code': subject_code,
            'user_gl': sorted([s.strip() for s in (current_user.allowed_grade_levels or '').split(',') if s.strip()]) if (not current_user.is_anonymous and current_user.role!='admin') else [],
            'user_cl': sorted([s.strip() for s in (current_user.allowed_class_names or '').split(',') if s.strip()]) if (not current_user.is_anonymous and current_user.role!='admin') else [],
        }
        key = md5(json.dumps(key_payload, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()
        now = time.time()
        entry = cache.get(key)
        if entry and now - entry['ts'] < ttl:
            total = entry['total']
        else:
            total = q.with_entities(db.func.count()).scalar()
            cache[key] = {'total': total, 'ts': now}
    except Exception:
        total = q.with_entities(db.func.count()).scalar()
    users = q.order_by(User.id.asc()).offset((page-1)*page_size).limit(page_size).all()
    return jsonify({
        'items': [
            {
                'id': u.id,
                'username': u.username,
                'email': u.email,
                'role': u.role,
                'allowed_grade_levels': u.allowed_grade_levels or '',
                'allowed_class_names': u.allowed_class_names or '',
            } for u in users
        ],
        'total': total,
        'page': page,
        'page_size': page_size,
    })


@api_bp.route('/users/<int:user_id>', methods=['PUT'])
@login_required
def api_user_update(user_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'forbidden'}), 403
    u = User.query.get_or_404(user_id)
    data = request.get_json(force=True)
    # 仅允许更新可见范围与角色（可选）
    if 'allowed_grade_levels' in data:
        u.allowed_grade_levels = data.get('allowed_grade_levels')
    if 'allowed_class_names' in data:
        u.allowed_class_names = data.get('allowed_class_names')
    if 'role' in data:
        u.role = data.get('role')
    db.session.commit()
    return jsonify({'message': 'updated'})


@api_bp.route('/users/batch', methods=['PUT'])
@login_required
def api_users_batch_update():
    if current_user.role != 'admin':
        return jsonify({'error': 'forbidden'}), 403
    data = request.get_json(force=True)
    items = data.get('items') or []
    for it in items:
        u = User.query.get(it.get('id'))
        if not u:
            continue
        if 'role' in it and it.get('role'):
            u.role = it.get('role')
        if 'allowed_grade_levels' in it:
            u.allowed_grade_levels = it.get('allowed_grade_levels')
        if 'allowed_class_names' in it:
            u.allowed_class_names = it.get('allowed_class_names')
    db.session.commit()
    return jsonify({'message': 'batch updated', 'count': len(items)})


# 版本管理：列出/新建草稿/发布/回滚
@api_bp.route('/grade-bands/sets', methods=['GET', 'POST'])
@login_required
def api_band_sets():
    if request.method == 'POST':
        if not current_user.is_authenticated or current_user.role != 'admin':
            return jsonify({'error': 'forbidden'}), 403
        data = request.get_json(force=True)
        exam_name = data.get('exam_name') or 'default'
        note = data.get('note')
        import json
        # version = 当前该考试的最大版本+1（草稿态）
        max_ver = db.session.query(db.func.max(GradeBandSet.version)).filter_by(exam_name=exam_name).scalar() or 0
        s = GradeBandSet(exam_name=exam_name, version=max_ver+1, status='draft', note=note, rules_json=json.dumps([], ensure_ascii=False))
        db.session.add(s)
        db.session.commit()
        return jsonify({'id': s.id, 'version': s.version, 'status': s.status}), 201
    # GET
    exam_name = request.args.get('exam_name') or 'default'
    sets = GradeBandSet.query.filter_by(exam_name=exam_name).order_by(GradeBandSet.version.desc()).all()
    return jsonify([
        { 'id': s.id, 'exam_name': s.exam_name, 'version': s.version, 'status': s.status, 'note': s.note, 'created_at': s.created_at.isoformat(), 'published_at': (s.published_at.isoformat() if s.published_at else None) }
        for s in sets
    ])


@api_bp.route('/grade-bands/sets/<int:set_id>/publish', methods=['PUT'])
@login_required
def api_band_set_publish(set_id):
    if not current_user.is_authenticated or current_user.role != 'admin':
        return jsonify({'error': 'forbidden'}), 403
    s = GradeBandSet.query.get_or_404(set_id)
    import json, datetime as dt
    # 将快照覆盖到活跃规则
    items = json.loads(s.rules_json)
    GradeBandRule.query.filter_by(exam_name=s.exam_name).delete()
    for it in items:
        db.session.add(GradeBandRule(
            exam_name=s.exam_name,
            subject_code=it.get('subject_code'),
            method=it.get('method'),
            a_min=it.get('a_min'), b_min=it.get('b_min'), c_min=it.get('c_min'), d_min=it.get('d_min'),
            a_pct=it.get('a_pct'), b_pct=it.get('b_pct'), c_pct=it.get('c_pct'), d_pct=it.get('d_pct'), e_pct=it.get('e_pct'),
        ))
    s.status = 'published'
    s.published_at = dt.datetime.utcnow()
    db.session.commit()
    # 审计
    from app.models import AuditLog
    db.session.add(AuditLog(user_id=current_user.id, username=current_user.username, action='publish', resource=f'GradeBandSet:{s.id}', details=f'{s.exam_name} v{s.version}'))
    db.session.commit()
    return jsonify({'message': 'published'})


@api_bp.route('/grade-bands/sets/<int:set_id>/rollback', methods=['PUT'])
@login_required
def api_band_set_rollback(set_id):
    if not current_user.is_authenticated or current_user.role != 'admin':
        return jsonify({'error': 'forbidden'}), 403
    # 将历史版本复制为新的草稿
    src = GradeBandSet.query.get_or_404(set_id)
    import json
    max_ver = db.session.query(db.func.max(GradeBandSet.version)).filter_by(exam_name=src.exam_name).scalar() or 0
    s = GradeBandSet(
        exam_name=src.exam_name,
        version=max_ver+1,
        status='draft',
        note=f'Rollback from v{src.version}',
        rules_json=src.rules_json,
    )
    db.session.add(s)
    db.session.commit()
    return jsonify({'id': s.id, 'version': s.version, 'status': s.status})


@api_bp.route('/grade-bands/sets/<int:set_id>/export-json', methods=['GET'])
@login_required
def api_band_set_export_json(set_id):
    if not current_user.is_authenticated or current_user.role not in ['admin','teacher']:
        return jsonify({'error': 'forbidden'}), 403
    s = GradeBandSet.query.get_or_404(set_id)
    import json
    return jsonify({ 'exam_name': s.exam_name, 'version': s.version, 'items': json.loads(s.rules_json) })


@api_bp.route('/grade-bands/sets/<int:set_id>/import-json', methods=['POST'])
@login_required
def api_band_set_import_json(set_id):
    if not current_user.is_authenticated or current_user.role != 'admin':
        return jsonify({'error': 'forbidden'}), 403
    s = GradeBandSet.query.get_or_404(set_id)
    data = request.get_json(force=True)
    items = data.get('items') or []
    import json
    s.rules_json = json.dumps(items, ensure_ascii=False)
    db.session.commit()
    return jsonify({'message': 'imported', 'count': len(items)})


# ExamScheme CRUD
@api_bp.route("/exam-schemes", methods=["GET", "POST"])
@login_required
def api_exam_schemes():
    if request.method == "POST":
        data = request.get_json() or request.form
        exam_type = normalize_exam_type(data.get("exam_type"))
        subject_code = data.get("subject_code")
        subject_name = data.get("subject_name")
        max_score = float(data.get("max_score", 100))
        item = ExamScheme(
            exam_type=exam_type, subject_code=subject_code, subject_name=subject_name, max_score=max_score
        )
        db.session.add(item)
        db.session.commit()
        return jsonify({"id": item.id}), 201
    # GET
    exam_type = normalize_exam_type(request.args.get("exam_type") or "regular")
    items = ExamScheme.query.filter_by(exam_type=exam_type).all()
    return jsonify(
        [
            {
                "id": it.id,
                "exam_type": it.exam_type,
                "subject_code": it.subject_code,
                "subject_name": it.subject_name,
                "max_score": it.max_score,
            }
            for it in items
        ]
    )


@api_bp.route("/exam-schemes/<int:item_id>", methods=["PUT", "DELETE"])
@login_required
def api_exam_scheme_detail(item_id):
    item = ExamScheme.query.get_or_404(item_id)
    if request.method == "PUT":
        data = request.get_json() or request.form
        if "max_score" in data:
            item.max_score = float(data.get("max_score"))
        if "subject_name" in data:
            item.subject_name = data.get("subject_name")
        if "exam_type" in data:
            item.exam_type = normalize_exam_type(data.get("exam_type"))
        db.session.commit()
        return jsonify({"message": "updated"})
    db.session.delete(item)
    db.session.commit()
    return jsonify({"message": "deleted"})
