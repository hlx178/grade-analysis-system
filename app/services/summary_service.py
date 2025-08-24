from app.models import Course, Grade, Student, UserPreference


def get_summary_options(user):
    from app import db

    q = Grade.query.join(Student)
    if not user.is_anonymous and user.role != "admin":
        if user.allowed_grade_levels:
            allowed = [s.strip() for s in (user.allowed_grade_levels or "").split(",") if s.strip()]
            if allowed:
                q = q.filter(Student.grade_level.in_(allowed))
        if user.allowed_class_names:
            allowed = [s.strip() for s in (user.allowed_class_names or "").split(",") if s.strip()]
            if allowed:
                q = q.filter(Student.class_name.in_(allowed))

    exam_names = sorted([r[0] for r in q.with_entities(Grade.exam_name).distinct().all() if r[0]])
    grade_levels = sorted(
        [r[0] for r in q.with_entities(Student.grade_level).distinct().all() if r[0]]
    )
    class_names = sorted(
        [r[0] for r in q.with_entities(Student.class_name).distinct().all() if r[0]]
    )
    return {"exam_names": exam_names, "grade_levels": grade_levels, "class_names": class_names}


def get_summary_data(
    user, exam_names, grade_levels, class_names, subject_code, order_by, page, page_size
):
    from sqlalchemy import desc

    from app import db
    from app.models import Course, ExamScheme, Grade, GradeBandSet, Student
    from app.utils import grade_letter_for

    # 基础查询（不先按学科过滤，便于 TOTAL 计算）
    base_q = Grade.query.join(Student).join(Course)
    if exam_names:
        base_q = base_q.filter(Grade.exam_name.in_(exam_names))
    if grade_levels:
        base_q = base_q.filter(Student.grade_level.in_(grade_levels))
    if class_names:
        base_q = base_q.filter(Student.class_name.in_(class_names))
    if not user.is_anonymous and user.role != "admin":
        if user.allowed_grade_levels:
            allowed = [s.strip() for s in user.allowed_grade_levels.split(",") if s.strip()]
            if allowed:
                base_q = base_q.filter(Student.grade_level.in_(allowed))
        if user.allowed_class_names:
            allowed = [s.strip() for s in user.allowed_class_names.split(",") if s.strip()]
            if allowed:
                base_q = base_q.filter(Student.class_name.in_(allowed))

    items = []
    rule_version = None

    # 若只选择了一个考试，读取发布的规则版本号便于回显
    if exam_names and len(exam_names) == 1:
        published_set = (
            GradeBandSet.query.filter_by(exam_name=exam_names[0], status="published")
            .order_by(GradeBandSet.version.desc())
            .first()
        )
        if published_set:
            rule_version = published_set.version

    # TOTAL: 若无总分科目，按各科汇总生成“虚拟总分行”
    if (subject_code or '').upper() == 'TOTAL':
        rows = base_q.all()
        # 按 (exam_name, student.id) 聚合
        from collections import defaultdict
        agg = {}
        exam_type_by_exam = {}
        for g in rows:
            key = (g.exam_name or 'default', g.student_id)
            rec = agg.get(key)
            if not rec:
                rec = agg[key] = {
                    'total': 0.0,
                    'student': g.student,
                    'exam_name': g.exam_name or 'default',
                }
                if (g.exam_name or 'default') not in exam_type_by_exam:
                    exam_type_by_exam[g.exam_name or 'default'] = g.exam_type or 'regular'
            rec['total'] = float(rec['total']) + float(g.score or 0)
        # 计算班/年排名（按 exam_name 维度分别计算）
        by_class = defaultdict(list)
        by_grade = defaultdict(list)
        for (ex, sid), rec in agg.items():
            s = rec['student']
            by_class[(ex, s.class_name)].append((sid, rec['total']))
            by_grade[(ex, s.grade_level)].append((sid, rec['total']))
        def rank_map(pairs):
            ps = sorted(pairs, key=lambda x: x[1], reverse=True)
            return {sid: i for i, (sid, _v) in enumerate(ps, 1)}
        class_rank_map = {k: rank_map(v) for k, v in by_class.items()}
        grade_rank_map = {k: rank_map(v) for k, v in by_grade.items()}
        # 获取 TOTAL 的满分（按 exam_type 推断，默认 regular）
        max_cache = {}
        for (ex, sid), rec in agg.items():
            s = rec['student']
            total = rec['total']
            et = exam_type_by_exam.get(ex, 'regular') or 'regular'
            key = (et, 'TOTAL')
            if key in max_cache:
                max_score = max_cache[key]
            else:
                scheme = ExamScheme.query.filter_by(exam_type=et, subject_code='TOTAL').first()
                max_score = scheme.max_score if scheme else None
                max_cache[key] = max_score
            perc = round(float(total)/float(max_score)*100.0, 2) if max_score else None
            items.append({
                'student_id': s.student_id,
                'name': s.name,
                'class_name': s.class_name,
                'grade_level': s.grade_level,
                'exam_name': ex,
                'subject_code': 'TOTAL',
                'score': total,
                'percentage': perc,
                'letter': grade_letter_for(ex, 'TOTAL', total),
                'class_rank': class_rank_map.get((ex, s.class_name), {}).get(s.id),
                'grade_rank': grade_rank_map.get((ex, s.grade_level), {}).get(s.id),
                'rule_version': rule_version,
            })
        total_count = len(items)
        # 分页与排序
        if order_by == 'score_desc':
            items.sort(key=lambda x: x['score'], reverse=True)
        elif order_by == 'score_asc':
            items.sort(key=lambda x: x['score'])
        elif order_by == 'class_rank':
            items.sort(key=lambda x: (x['class_name'] or '', x['class_rank'] or 1e9))
        elif order_by == 'grade_rank':
            items.sort(key=lambda x: (x['grade_level'] or '', x['grade_rank'] or 1e9))
        start = max(0, (page-1)*page_size)
        end = start + page_size
        items = items[start:end]
        return {
            'items': items,
            'total': total_count,
            'page': page,
            'page_size': page_size,
            'rule_version': rule_version,
        }

    # 非 TOTAL：按指定学科直接取行
    q = base_q.filter(Course.code == subject_code) if subject_code else base_q
    # 统计总数
    total = db.session.query(db.func.count()).select_from(q.subquery()).scalar()
    rows = q.offset((page - 1) * page_size).limit(page_size).all()

    # 计算排名（同学科内、按班/年）
    from collections import defaultdict
    by_class = defaultdict(list)
    by_grade = defaultdict(list)
    for g in rows:
        by_class[g.student.class_name].append((g.student_id, g.score))
        by_grade[g.student.grade_level].append((g.student_id, g.score))
    def rank_map(pairs):
        pairs_sorted = sorted(pairs, key=lambda x: x[1], reverse=True)
        return {sid: i for i, (sid, _) in enumerate(pairs_sorted, 1)}
    class_rank_map = {k: rank_map(v) for k, v in by_class.items()}
    grade_rank_map = {k: rank_map(v) for k, v in by_grade.items()}

    # 规则版本与满分缓存
    max_cache = {}

    for g in rows:
        letter = grade_letter_for(g.exam_name or "default", g.course.code, g.score)
        perc = None
        key = (g.exam_type or "regular", g.course.code)
        if key in max_cache:
            max_score = max_cache[key]
        else:
            s = ExamScheme.query.filter_by(exam_type=key[0], subject_code=key[1]).first()
            max_score = s.max_score if s else None
            max_cache[key] = max_score
        if max_score and max_score > 0:
            perc = round(float(g.score) / float(max_score) * 100.0, 2)
        items.append({
            "student_id": g.student.student_id,
            "name": g.student.name,
            "class_name": g.student.class_name,
            "grade_level": g.student.grade_level,
            "exam_name": g.exam_name,
            "subject_code": g.course.code,
            "score": g.score,
            "percentage": perc,
            "letter": letter,
            "class_rank": class_rank_map.get(g.student.class_name, {}).get(g.student_id),
            "grade_rank": grade_rank_map.get(g.student.grade_level, {}).get(g.student_id),
            "rule_version": rule_version,
        })

    if order_by == "score_desc":
        items.sort(key=lambda x: x["score"], reverse=True)
    elif order_by == "score_asc":
        items.sort(key=lambda x: x["score"])
    elif order_by == "class_rank":
        items.sort(key=lambda x: (x["class_name"] or "", x["class_rank"] or 1e9))
    elif order_by == "grade_rank":
        items.sort(key=lambda x: (x["grade_level"] or "", x["grade_rank"] or 1e9))

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "rule_version": rule_version,
    }
