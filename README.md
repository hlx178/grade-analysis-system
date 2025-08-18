# 成绩分析系统 (Grade Analysis System)

一个基于Python Flask的学生成绩管理和分析系统，提供成绩录入、统计分析、可视化图表等功能。

## 功能特性

- 📊 **成绩管理**: 学生成绩的录入、修改、删除
- 📈 **统计分析**: 平均分、最高分、最低分、排名等统计
- 📉 **可视化图表**: 成绩分布图、趋势分析图
- 👥 **多角色支持**: 管理员、教师、学生不同权限
- 📋 **报告生成**: 自动生成分析报告
- 🔍 **数据筛选**: 按班级、科目、时间等条件筛选

## 技术栈

- **后端**: Python Flask
- **前端**: HTML5, CSS3, JavaScript, Chart.js
- **数据库**: SQLite
- **样式框架**: Bootstrap 5

## 项目结构

```
grade-analysis-system/
├── app/
│   ├── __init__.py
│   ├── models.py          # 数据模型
│   ├── routes.py          # 路由和API
│   ├── utils.py           # 工具函数
│   └── templates/         # 模板（Flask默认位置）
│       ├── base.html
│       ├── dashboard.html
│       ├── students.html
│       ├── courses.html
│       ├── grades.html
│       └── login.html
├── tests/                 # 测试用例
├── .github/workflows/ci.yml  # GitHub Actions CI
├── requirements.txt       # 运行时依赖
├── requirements-dev.txt   # 开发依赖（black/isort/flake8）
├── pyproject.toml         # 工具配置（black/isort/pytest）
├── .flake8                # flake8 配置
├── config.py
├── run.py
└── README.md
```

## 快速开始

1. 克隆项目
```bash
git clone https://github.com/hlx178/grade-analysis-system.git
cd grade-analysis-system
```

2. 创建并激活虚拟环境（推荐）
- macOS/Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
```
- Windows PowerShell
```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. 安装依赖
```bash
pip install -r requirements.txt
```

4. 初始化数据库
```bash
python run.py init-db
```

5. 运行应用
```bash
python run.py
```

6. 访问 http://localhost:5000

## 本地开发与测试

- 运行测试
```bash
pytest -q
```

- 代码规范检查
```bash
black --check .
isort --check-only .
flake8
```

- 自动格式化
```bash
black .
isort .
```

## CI 状态

GitHub Actions 会在每次推送时自动运行 lint 和测试。你可以在仓库的 Actions 标签页查看状态与日志。

## 导入与模板

- 推荐模板（多学科一张表，支持多工作表）：
  - 学号、姓名、班级、语文、数学、英语、科学、社会、道法（可选：考试类型、考试名称）
  - 总分由系统自动生成（写入虚拟课程 TOTAL）
  - 上传后先调用 /api/import/preview 获取工作表列表，再携带 file_id + sheet_name 调用 /api/import/grades 导入
  - 支持“常规考试/模拟考试”（internal: regular/mock）

## 考试方案配置（满分）

- 页面：/exam-schemes，可按考试类型配置各学科及总分满分
- 模型：ExamScheme(exam_type, subject_code, subject_name, max_score)
- 首次使用某考试类型会自动生成默认方案（各科100，总分=学科数×100）

## 等级规则配置（A-E）

- 页面：/grade-bands（单页管理所有学科，含 TOTAL）
- 两种方法（按考试名称 exam_name + 学科 subject_code 生效）：
  1) range：按分数段阈值设置 A_min/B_min/C_min/D_min（E为其余）
  2) percentile：按百分比设置 A/B/C/D/E（总和需为100）
- 默认阈值（用于未配置或回退场景）：80/60/40/20
- API：
  - GET /api/grade-bands?exam_name=期末 拉取规则
  - PUT /api/grade-bands/bulk 批量保存（带校验）
  - POST /api/grade-bands/preview 预览当前表单规则对选定课程/班级的分布
- 页面增强：
  - 一键“应用到所有学科”（以首行作为模板）
  - 百分比法实时合计提示（合计达到100%为绿色）

## 仪表盘分析

- 页面：/（仪表盘）
- 新增“考试名称”选择器；传 exam_name 到 /api/analysis/statistics
- 分布优先规则：range > percentile；都无时按默认阈值 80/60/40/20 计算

## 成绩汇总（/summary）

- 功能
  - 筛选：考试名称（多选）、年级（多选）、班级（多选）、学科/总分
  - 排序：分数升降序、班级排名、年级排名
  - 列显示偏好：分数、百分比（基于 ExamScheme）、等第（基于等级规则）、班级/年级排名、规则版本（基于最新发布的 GradeBandSet）
  - 分页：page/page_size，服务端分页
  - 导出：CSV/XLSX，支持“按当前列偏好导出”
- API
  - GET /api/summary?exam_name=&grade_level=&class_name=&subject_code=&order_by=&page=&page_size=
  - GET /api/summary/options：返回 exam_names、grade_levels、class_names
  - GET /api/summary/export?…&format=csv|xlsx[&columns=student_id,name,…]
  - GET/PUT /api/summary/prefs：按用户保存/读取列显示偏好
- 注意
  - 多选参数支持多值或逗号分隔
  - percentage 需 ExamScheme 配置对应学科/总分的满分
  - rule_version 仅在选择单个考试名称时返回
  - 非管理员也可访问汇总与偏好（权限策略可按需配置）

## CI 状态

GitHub Actions 会在每次推送时自动运行 lint 和测试。你可以在仓库的 Actions 标签页查看状态与日志。


## Docker 使用

- 拉取镜像（GHCR）：

```bash
# 可将包设为 Public 后无需登录
# 登录（如为私有包）：
# echo $GH_PAT | docker login ghcr.io -u <your_github_username> --password-stdin

# 拉取
docker pull ghcr.io/hlx178/grade-analysis-system:latest
```

- 运行容器：

```bash
docker run --name gas \
  -p 8000:8000 \
  -e FLASK_CONFIG=production \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/exports:/app/exports \
  ghcr.io/hlx178/grade-analysis-system:latest
```

- 初始化数据库与管理员（可进入容器执行）：

```bash
# 初始化数据库
docker exec -it gas flask init-db

# 创建管理员
docker exec -it gas flask create-admin
```

- 常用环境变量：
  - FLASK_CONFIG=production
  - EXPORT_DIR=/app/exports（默认）
  - EXPORT_RETENTION_DAYS=7
  - EXPORT_MAX_CONCURRENT_PER_USER=2
  - DOWNLOAD_LINK_TTL_SECONDS=3600

### docker-compose 示例

```yaml
version: '3.9'
services:
  app:
    image: ghcr.io/hlx178/grade-analysis-system:latest
    container_name: gas
    ports:
      - "8000:8000"
    environment:
      - FLASK_CONFIG=production
      - EXPORT_RETENTION_DAYS=7
      - EXPORT_MAX_CONCURRENT_PER_USER=2
      - DOWNLOAD_LINK_TTL_SECONDS=3600
    volumes:
      - ./uploads:/app/uploads
      - ./exports:/app/exports
    restart: unless-stopped
- 健康检查
  - /health：应用进程存活探针（200 ok）
  - /ready：就绪探针，包含数据库可用性检查（200 ready / 503 not_ready）

```

- 访问 http://localhost:8000

说明：镜像由 GitHub Actions 在 push 到 main 时自动构建并推送到 GHCR（ghcr.io/hlx178/grade-analysis-system:latest）。首次出现于 Packages 页面时，可将可见性设为 Public 以便公开拉取。

## 发布版本指南（打 tag）

- 打版本 tag（如 v1.0.0）并推送：

```bash
git tag v1.0.0
git push origin v1.0.0
```

- 工作流会自动构建并推送 multi-arch 镜像到 GHCR：
  - ghcr.io/hlx178/grade-analysis-system:v1.0.0
  - main 分支继续构建 latest 与 sha-<短哈希>

- 查看构建状态：
  - GitHub 仓库 → Actions → 选择最新的“Build and Push Docker image to GHCR”工作流

- 回滚/切换版本：

```bash
docker pull ghcr.io/hlx178/grade-analysis-system:v1.0.0
# 使用 v1.0.0 运行
```

## 反向代理与 HTTPS（Caddy）

- 使用 docker-compose.caddy.yml 与 Caddyfile：

```bash
# 修改 Caddyfile 中的域名为你的实际域名（示例：gas.example.edu.cn）
# 可选修改全局 email，用于自动申请/续期证书

# 启动
docker compose -f docker-compose.caddy.yml up -d
```

- 说明
  - Caddy 将自动申请并续期 Let’s Encrypt 证书，默认监听 80/443
  - 反向代理至 app 服务的 8000 端口
  - 可在 Caddyfile 中添加更多路由、Header、限流等


- 可见性（首次）：
  - 前往仓库 Packages → 容器包 → Settings，将可见性切换为 Public（如果需要公开拉取）


## Nginx 反向代理示例

- 使用 docker-compose.nginx.yml 与 nginx.conf：

```bash
# 启动
docker compose -f docker-compose.nginx.yml up -d
```

- 如需 HTTPS，请将证书挂载并在 nginx.conf 中添加 443 server 块配置（ssl_certificate/ssl_certificate_key）。

## 使用 Postgres 外置数据库

- 使用 docker-compose.postgres.yml：

```bash
# 启动（将自动拉起 Postgres 并在健康后启动应用）
docker compose -f docker-compose.postgres.yml up -d
```

- 连接串由环境变量 DATABASE_URL 指定（已经在 compose 中设置）：
  - postgresql+psycopg2://gas:gas_pass@db:5432/gas

- 注意事项：
  - 首次运行会初始化空库，请按 README 的“初始化数据库与管理员”步骤在容器内执行 flask init-db 和 create-admin
  - 如需数据迁移，可后续接入 Alembic


## 开发状态

🚧 项目正在持续演进，欢迎反馈与贡献。