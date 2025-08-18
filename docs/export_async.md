# 异步导出（轻量线程版）

## 概述
- 提供三组接口：创建任务、查询状态、下载文件
- 后端采用轻量线程生成文件，生成完成后可供下载
- 适合单实例部署；多实例/多进程场景可升级为队列（RQ/Celery）

## 接口
- POST /api/export/tasks
  - Body(JSON)：与 /api/summary/export 相同的参数，例如：
    - exam_name、grade_level、class_name 支持多值或逗号分隔
    - subject_code、order_by、scope、page、page_size、format(csv|xlsx)、columns
  - 返回：{ task_id }
- GET /api/export/tasks/:task_id
  - 返回：{ status: pending|running|completed|failed, progress, file?, error? }
- GET /api/export/tasks/:task_id/download
  - 在 completed 状态下返回文件下载

## 前端使用建议
- 点击“异步导出”后：
  1) 调用 POST /api/export/tasks 创建任务
  2) 显示任务已创建提示，间隔轮询 GET 状态
  3) 当 status=completed 显示“下载”按钮，指向下载接口

## 实现说明
- 任务存储：内存字典 _export_tasks（进程内）。生产可改为数据库或缓存
- 导出目录：config.EXPORT_DIR（默认 exports），会自动创建
- 文件生成：复用 /api/summary/export 的过滤逻辑，写 csv 或 xlsx
- 权限：示例中后台线程使用当前应用上下文，未再复用当前用户限制
  - 生产可在创建任务时记录 user_id，并在生成时套用其可见范围

## 升级为队列（可选）
- 使用 RQ/Celery，任务状态持久化；可横向扩展
- 需要额外部署 Redis/RabbitMQ 等

