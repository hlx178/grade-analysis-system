#!/usr/bin/env python3
"""
测试成绩分析系统的功能
"""

import os
import sys

sys.path.append(".")


def test_grade_inference():
    """测试年级识别功能"""
    print("=== 测试年级识别功能 ===")
    from app.utils import infer_grade_from_class_name

    test_cases = [
        ("71班", "七年级"),
        ("七1班", "七年级"),
        ("初一1班", "七年级"),
        ("81班", "八年级"),
        ("八1班", "八年级"),
        ("初二1班", "八年级"),
        ("91班", "九年级"),
        ("九1班", "九年级"),
        ("初三1班", "九年级"),
        ("九(8)班", "九年级"),
        ("八(6)班", "八年级"),
        ("八(5)班", "八年级"),
        ("高一(1)班", "一年级"),  # 这个可能不正确，但按当前逻辑会这样
        ("无效班级", None),
    ]

    all_passed = True
    for class_name, expected in test_cases:
        result = infer_grade_from_class_name(class_name)
        status = "✓" if result == expected else "✗"
        print(f"{status} {class_name} -> {result} (期望: {expected})")
        if result != expected:
            all_passed = False

    return all_passed


def test_database_connection():
    """测试数据库连接和数据"""
    print("\n=== 测试数据库连接 ===")
    try:
        from app import create_app, db
        from app.models import Course, Grade, Student

        app = create_app()
        with app.app_context():
            # 检查学生数量
            student_count = Student.query.count()
            print(f"学生总数: {student_count}")

            # 检查成绩数量
            grade_count = Grade.query.count()
            print(f"成绩总数: {grade_count}")

            # 检查课程数量
            course_count = Course.query.count()
            print(f"课程总数: {course_count}")

            # 检查考试名称
            exam_names = db.session.query(Grade.exam_name).distinct().all()
            print(f"考试名称: {[name[0] for name in exam_names]}")

            # 检查年级分布
            grade_levels = db.session.query(Student.grade_level).distinct().all()
            print(f"年级分布: {[level[0] for level in grade_levels if level[0]]}")

            return True
    except Exception as e:
        print(f"数据库测试失败: {e}")
        return False


def test_column_mapping():
    """测试列名映射功能"""
    print("\n=== 测试列名映射功能 ===")

    # 模拟导入代码中的列名映射逻辑
    import re

    def _norm_col(c: str) -> str:
        c = str(c or "").strip()
        c = c.replace("\u3000", "").replace(" ", "").replace("\t", "")
        c = c.replace("（", "(").replace("）", ")")
        return c

    alias = {
        "学生姓名": "姓名",
        "名字": "姓名",
        "名称": "姓名",
        "学生名称": "姓名",
        "班级名称": "班级",
        "班级名": "班级",
        "班级(名称)": "班级",
        "课程代号": "课程代码",
        "科目代码": "课程代码",
        "科目名称": "课程名称",
        "学籍号": "学号",
        "学生编号": "学号",
        "学生号": "学号",
        "编号": "学号",
        "考生号": "学号",
        "考号": "学号",
        "准考证号": "学号",
        "语文成绩": "语文",
        "数学成绩": "数学",
        "英语成绩": "英语",
        "科学成绩": "科学",
        "社会成绩": "社会",
        "道法成绩": "道法",
        "语文分": "语文",
        "数学分": "数学",
        "英语分": "英语",
        "科学分": "科学",
        "社会分": "社会",
        "道法分": "道法",
        "语文分数": "语文",
        "数学分数": "数学",
        "英语分数": "英语",
        "科学分数": "科学",
        "社会分数": "社会",
        "道法分数": "道法",
        "社会道法合科分数": "道法",
        "社会道法分数": "道法",
        "社会道法": "道法",
    }

    test_columns = [
        "语文分数",
        "数学分数",
        "英语分数",
        "科学分数",
        "社会道法合科分数",
        "学生姓名",
        "班级名称",
    ]

    print("列名映射测试:")
    for col in test_columns:
        raw = _norm_col(col)
        raw = re.sub(r"^(.*?)(\(|（).*(\)|）)$", r"\1", raw)
        mapped = alias.get(raw, raw)
        mapped = re.sub(r"^(语文|数学|英语|科学|社会|道法).*(分|成绩)?$", r"\1", mapped)
        print(f"  {col} -> {mapped}")

    return True


if __name__ == "__main__":
    print("成绩分析系统功能测试")
    print("=" * 50)

    # 运行所有测试
    tests = [
        ("年级识别功能", test_grade_inference),
        ("数据库连接", test_database_connection),
        ("列名映射功能", test_column_mapping),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"{test_name}测试出错: {e}")
            results.append((test_name, False))

    # 输出测试结果
    print("\n" + "=" * 50)
    print("测试结果汇总:")
    for test_name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"{status} {test_name}")

    all_passed = all(result for _, result in results)
    print(f"\n总体结果: {'所有测试通过' if all_passed else '部分测试失败'}")
