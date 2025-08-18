# 性能 Profiling 与索引建议（初稿）

此文档记录当前系统在“成绩汇总/导出”等核心路径上的查询特征、索引现状与建议。

## 关键接口与查询特征

- /api/summary
  - 典型过滤：exam_name(多选)、grade_level(多选)、class_name(多选)、subject_code
  - 排序：score desc/asc，或按班级/年级排名（排名在内存聚合）
  - 分页：page/page_size
- /api/summary/export
  - 与 /api/summary 相同过滤，scope=all|current_page
  - 对 all 情况：全量导出，排序为 score desc/asc
- /api/summary/options
  - 枚举 exam_name（Grade 表）、grade_level/class_name（Student 表）

## 现有（含新增）索引

- Student:
  - class_name (index)
  - grade_level (index)
- Grade:
  - (student_id, course_id) (index)
  - (course_id, exam_type) (index)
  - (course_id, exam_name) (index)
  - (course_id, exam_name, score) (index) [新增]
  - (exam_name) (index) [新增]

> 说明：按“考试+学科+按分数排序”的模式查询时，(course_id, exam_name, score) 能有效支持过滤与排序。

## 建议与下一步

1. 针对常用路径的 EXPLAIN（真实数据或样本数据）
   - summary 列表（多选 exam_name/grade/class + 特定 subject_code + 排序 + 分页）
   - export 全量（同过滤 + score desc/asc）
   - 记录是否命中 (course_id, exam_name, score) 的索引范围扫描；观察回表/排序代价

2. 候选索引（按业务热点择优）
   - Grade(exam_name, course_id)：若无排序时列表也需加速过滤，且score排序不频繁
   - Grade(exam_name, course_id, student_id)：若需要频繁按学生聚合/去重
   - Grade(student_id, exam_name)：若学生成绩按考试查询频繁

3. COUNT 优化
   - 对于复杂过滤 + 排序的分页，total 计数可采用简化 COUNT（去掉 ORDER BY），或做缓存/延迟加载，减少总耗时

4. 导出优化
   - CSV：后端考虑使用生成器流式写出，分批提交，避免全量数据一次性驻留内存
   - XLSX：openpyxl write_only 模式生成大文件

5. 监控与阈值
   - 在日志中采集查询耗时与行数（影响范围小）
   - 设置慢查询阈值（例如 >500ms）输出 EXPLAIN 片段到调试日志，便于分析

## 结论

- 目前的索引已覆盖最常用的“考试+学科+分数排序”路径
- 后续将按实际数据规模与查询模式，逐步引入专用索引，并在导出/分页上考虑流式与 COUNT 优化，以保障在大数据量场景下的稳定性与响应速度

