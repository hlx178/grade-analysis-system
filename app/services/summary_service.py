from flask_login import current_user
from app import db
from app.models import Grade, Student, Course, UserPreference

def get_summary_options(user):
    q = Grade.query.join(Student)
    if not user.is_anonymous and user.role != 'admin':
        if user.allowed_grade_levels:
            allowed = [s.strip() for s in (user.allowed_grade_levels or '').split(',') if s.strip()]
            if allowed:
                q = q.filter(Student.grade_level.in_(allowed))
        if user.allowed_class_names:
            allowed = [s.strip() for s in (user.allowed_class_names or '').split(',') if s.strip()]
            if allowed:
                q = q.filter(Student.class_name.in_(allowed))
    
    exam_names = sorted([r[0] for r in q.with_entities(Grade.exam_name).distinct().all() if r[0]])
    grade_levels = sorted([r[0] for r in q.with_entities(Student.grade_level).distinct().all() if r[0]])
    class_names = sorted([r[0] for r in q.with_entities(Student.class_name).distinct().all() if r[0]])
    return {
        'exam_names': exam_names,
        'grade_levels': grade_levels,
        'class_names': class_names
    }

def get_summary_data(user, exam_names, grade_levels, class_names, subject_code, order_by, page, page_size):
    from sqlalchemy import desc
    from flask import current_app, jsonify
    from app.models import Grade, Student, Course, ExamScheme, GradeBandSet
    from app.utils import grade_letter_for, _cache_nsver

    q = Grade.query.join(Student).join(Course)
    if exam_names:
        q = q.filter(Grade.exam_name.in_(exam_names))
    if grade_levels:
        q = q.filter(Student.grade_level.in_(grade_levels))
    if class_names:
        q = q.filter(Student.class_name.in_(class_names))
    if not user.is_anonymous and user.role != 'admin':
        if user.allowed_grade_levels:
            allowed = [s.strip() for s in user.allowed_grade_levels.split(',') if s.strip()]
            if allowed:
                q = q.filter(Student.grade_level.in_(allowed))
        if user.allowed_class_names:
            allowed = [s.strip() for s in user.allowed_class_names.split(',') if s.strip()]
            if allowed:
                q = q.filter(Student.class_name.in_(allowed))
    if subject_code:
        q = q.filter(Course.code == subject_code)

    total = q.with_entities(db.func.count()).scalar()
    rows = q.offset((page - 1) * page_size).limit(page_size).all()

    published_set = None
    rule_version = None
    if exam_names and len(exam_names) == 1:
        published_set = GradeBandSet.query.filter_by(exam_name=exam_names[0], status='published').order_by(GradeBandSet.version.desc()).first()
        if published_set:
            rule_version = published_set.version

    max_cache = {}
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

    items = []
    for g in rows:
        letter = grade_letter_for(g.exam_name or 'default', g.course.code, g.score)
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
            'exam_name': g.exam_name,
            'subject_code': g.course.code,
            'score': g.score,
            'percentage': perc,
            'letter': letter,
            'class_rank': class_rank_map.get(g.student.class_name, {}).get(g.student_id),
            'grade_rank': grade_rank_map.get(g.student.grade_level, {}).get(g.student_id),
            'rule_version': rule_version,
        })

    if order_by == 'score_desc':
        items.sort(key=lambda x: x['score'], reverse=True)
    elif order_by == 'score_asc':
        items.sort(key=lambda x: x['score'])
    elif order_by == 'class_rank':
        items.sort(key=lambda x: (x['class_name'] or '', x['class_rank'] or 1e9))
    elif order_by == 'grade_rank':
        items.sort(key=lambda x: (x['grade_level'] or '', x['grade_rank'] or 1e9))

    return {'items': items, 'total': total, 'page': page, 'page_size': page_size, 'rule_version': rule_version}

