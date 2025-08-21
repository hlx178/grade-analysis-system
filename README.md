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


> 如果在本机安装依赖时遇到“metadata-generation-failed”，可先尝试：
>
> - 升级打包工具链：`python -m pip install --upgrade pip setuptools wheel`
> - 优先安装二进制轮子：`python -m pip install --prefer-binary -r requirements.txt`
> - Linux: 安装构建工具 `sudo apt-get update && sudo apt-get install -y build-essential`；如与图形库相关，再装 `libjpeg-dev zlib1g-dev pkg-config libfreetype6-dev`
> - macOS: `xcode-select --install`；Apple Silicon 建议 Python 3.11/3.12
> - Windows: 使用 64 位 Python，若触发 C/C++ 扩展编译，需安装 Build Tools；优先 `--prefer-binary`
>
> 也可直接使用 Docker 运行（见下文 Docker 使用），避免本地依赖问题。

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

> 注：本仓库已配置 GitHub Actions 在 push 到 main 时自动构建并推送 Docker 镜像到 GHCR（以及可选 Docker Hub）。如需 Docker Hub 推送，请在仓库 Secrets 中配置 DOCKERHUB_USERNAME、DOCKERHUB_TOKEN、DOCKERHUB_REPO。

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
docker pull ghcr.io/hlx178/grade-analysis:latest
```

- 运行容器：

```bash
# SQLite 单容器快速跑（不依赖外部 PG/Redis）
docker run --name gas \
  -p 8000:8000 \
  -e FLASK_CONFIG=production \
  -e DATABASE_URL=sqlite:////app/data/grade_analysis.db \
  -e ADMIN_INITIAL_PASSWORD=123456 \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/exports:/app/exports \
  -v $(pwd)/data:/app/data \
  ghcr.io/hlx178/grade-analysis-system:latest

# 连接外部 Postgres + Redis（示例）
# export DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/gas
# export REDIS_URL=redis://host:6379/0
# docker run --name gas -p 8000:8000 \
#   -e FLASK_CONFIG=production \
#   -e DATABASE_URL="$DATABASE_URL" \
#   -e REDIS_URL="$REDIS_URL" \
#   -e ADMIN_INITIAL_PASSWORD=123456 \
#   -v $(pwd)/uploads:/app/uploads \
#   -v $(pwd)/exports:/app/exports \
#   ghcr.io/hlx178/grade-analysis-system:latest
```

## 缓存与指标

- Redis 缓存（可选）：设置 REDIS_URL 后启用
  - /api/summary：
    - total 计数缓存 TTL：SUMMARY_COUNT_TTL_SECONDS（默认 60）
    - 列表缓存 TTL：SUMMARY_LIST_TTL_SECONDS（默认 60）
  - /api/analysis/statistics：ANALYSIS_TTL_SECONDS（默认 60）
- 自动失效：
  - 成绩新增/更新/删除、导入完成后，自动 bump 命名空间 version（summary/analysis），老的缓存 key 不再命中
  - 等级规则发布/回滚/导入后，同样 bump summary/analysis
- Prometheus 指标（/metrics）：
  - gas_cache_hits_total{bucket="summary_list|summary_count|analysis_stats"}
  - gas_cache_misses_total{bucket="..."}
  - 导出复用缓存：
    - 同步导出 /api/summary/export 在 scope=current_page 时复用 summary 列表缓存
    - 异步导出 /export/tasks 内部在 scope=current_page 时同样复用缓存
  - 指标补充：
    - gas_cache_hits_total{bucket="export_list"}
    - gas_cache_misses_total{bucket="export_list"}


### Compose 变体对比与环境变量

- dev（docker-compose.dev.yml）
  - 适合本地开发：内置 PG + Redis + App 构建
  - 可通过 `$env:DEV_PORT=8010` 或 `scripts/dev.ps1 -Port 8010` 指定端口
  - 关键环境变量：
    - DATABASE_URL=postgresql+psycopg2://gas:gas_pass@db:5432/gas
    - REDIS_URL=redis://redis:6379/0
    - SUMMARY_COUNT_TTL_SECONDS / SUMMARY_LIST_TTL_SECONDS / ANALYSIS_TTL_SECONDS
- postgres（docker-compose.postgres.yml）
  - 拉取已构建镜像，内置 PG + Redis
  - 与 dev 相同的缓存变量已加入 environment
- caddy / nginx（反代网关）
  - 通过内置 Caddy 或 Nginx 反向代理到 App 容器
  - 同样包含缓存 TTL 环境变量，确保行为一致

> 生产建议：将上述变量配置到你的部署系统（K8s Deployment env 或 Ansible inventory），并明确 SECRET_KEY、ADMIN_INITIAL_PASSWORD、EXPORT_RETENTION_DAYS 等。

### K8s 部署参考（片段）

示例仅展示与缓存/就绪探针相关的关键位；请按需合并完整 Deployment/Service/Ingress。

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: gas
spec:
  replicas: 2
  selector:
    matchLabels: { app: gas }
  template:
    metadata:
      labels: { app: gas }
    spec:
      containers:
        - name: app
          image: ghcr.io/hlx178/grade-analysis-system:latest
          ports:
            - containerPort: 8000
          env:
            - name: FLASK_CONFIG
              value: production
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: gas-secrets
                  key: database_url
            - name: REDIS_URL
              valueFrom:
                secretKeyRef:
                  name: gas-secrets
                  key: redis_url
            - name: SUMMARY_COUNT_TTL_SECONDS
              value: "60"
            - name: SUMMARY_LIST_TTL_SECONDS
              value: "60"
            - name: ANALYSIS_TTL_SECONDS
              value: "60"
            - name: EXPORT_RETENTION_DAYS
              value: "7"
          readinessProbe:
            httpGet:
              path: /ready
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
            timeoutSeconds: 2
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 15
            timeoutSeconds: 2
```

### 性能与调优建议

- 缓存 TTL：
  - 以 30–120 秒为宜；导入高峰期可适当降低 TTL，避免短期旧值
  - 命名空间失效已接入（成绩/规则变更自动 bump），一般无需手动清理
- Redis 连接：
  - REDIS_URL 建议专用 DB（如 db=0），避免与其他应用冲突
  - 部署高可用可用 Redis Sentinel/Cluster
- Gunicorn：
  - 进程/线程数按 CPU 与场景调优，如 `-w 2 -k gthread --threads 8`
  - I/O 为主场景可适当增加线程数
- Postgres：
  - 对高并发 count 场景，考虑使用近似行数统计或物化统计表；当前我们已做微缓存
- 指标观测：
  - 关注 gas_http_requests_total、gas_http_request_duration_seconds
  - 关注 gas_cache_hits_total / gas_cache_misses_total；命中率长期偏低则考虑延长 TTL 或增加缓存覆盖


## 部署参考与清单

- 生产清单：docs/deploy/PRODUCTION_CHECKLIST.md
- Helm values 示例：docs/deploy/HELM_VALUES.example.yaml
- GitHub Actions 部署示例（Compose）：docs/deploy/GHACTION_DEPLOY_EXAMPLE.md

- 初始化数据库与管理员（脚本法，容器内执行 Python 脚本）：

```bash
# 初始化数据库
# 若镜像未包含 Flask CLI，可使用我们提供的脚本法（见下文）；或在容器内运行 Python 脚本进行初始化

# 创建管理员
# 参见下面“初始化脚本法”示例
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
    image: ghcr.io/hlx178/grade-analysis:latest
    container_name: gas
    ports:
      - "8000:8000"
    environment:
      - FLASK_CONFIG=production\n      - DATABASE_URL=sqlite:////app/data/grade_analysis.db
      - EXPORT_RETENTION_DAYS=7
      - EXPORT_MAX_CONCURRENT_PER_USER=2
      - DOWNLOAD_LINK_TTL_SECONDS=3600
    volumes:
      - ./uploads:/app/uploads
      - ./exports:/app/exports\n      - ./data:/app/data
    restart: unless-stopped
- 健康检查
  - /health：应用进程存活探针（200 ok）
  - /ready：就绪探针，包含数据库可用性检查（200 ready / 503 not_ready）

```

- 访问 http://localhost:8000

说明：镜像由 GitHub Actions 在 push 到 main 时自动构建并推送到 GHCR（ghcr.io/hlx178/grade-analysis:latest）。首次出现于 Packages 页面时，可将可见性设为 Public 以便公开拉取。

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


## 数据库迁移（Alembic）

- 初始化（已加入基础配置）：
  - alembic.ini 与 migrations/ 已存在
- 生成迁移（示例）：

```bash
# 在 FLASK_CONFIG=production 或开发环境下，确保应用可导入
alembic revision -m "init schema"
# 执行迁移
alembic upgrade head
```

- 提示：生产环境建议采用 Alembic 管理 schema 演进；当前测试仍使用 create_all 方式初始化


## 开发状态

## 生产环境最佳实践清单（建议）

- 配置与密钥
  - 使用 .env 文件或容器环境变量提供 SECRET_KEY、DATABASE_URL 等
  - 不要将真实密钥提交到仓库；参考 .env.example
- 日志与监控
  - 通过容器 stdout/stderr 输出应用与 Gunicorn 日志，宿主机/平台负责采集
  - 关注慢日志（SLOW_QUERY_MS）与健康/就绪状态；可集成 Prometheus/Grafana（见后续）
- 备份策略
  - 数据库：定期备份（Postgres 建议 pg_dump），保留多份（含异地）
  - 文件：exports/ 与 uploads/ 定期归档到对象存储或 NAS
- 存储与清理
  - EXPORT_RETENTION_DAYS 控制导出文件保留期；结合“批量删除已完成任务”释放空间
  - 磁盘水位监控，READY_DISK_FREE_MB 设定合理阈值
- 安全加固
  - 反向代理层开启 HTTPS（Caddy/Nginx）并启用 HSTS
  - 只对内网暴露应用容器端口，通过反代对外
  - 容器以非 root 用户运行（Dockerfile 已设置 appuser）
  - 最小权限挂载卷（只读/可写分离）
- 资源配额与伸缩
  - 在编排平台设置 CPU/内存 limits 与 requests
  - 并发导出上限（EXPORT_MAX_CONCURRENT_PER_USER）按机器规格调优
- 灰度与回滚
  - 使用 tag 发布版本镜像（vX.Y.Z），回退时直接切换 tag
  - 保留近期版本镜像与备份



## 监控与可观测（Prometheus + Grafana）

- 组件：cAdvisor（容器指标）、node-exporter（主机指标）、blackbox-exporter（HTTP 探针）、Prometheus、Grafana
- 启动：

```bash
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
# 访问 Grafana: http://localhost:3000 （默认密码 admin / admin）
# 访问 Prometheus: http://localhost:9090
# cAdvisor: http://localhost:8080
```

- 已预置：
  - Prometheus 抓取 cAdvisor/node/blackbox 与自身
  - Blackbox 探针检查 http://app:8000/health 与 /ready
  - Grafana 预置 Prometheus 数据源与简单仪表盘（GAS App Health）

- 生产建议：
  - 给 Grafana 管理员设置强密码（GF_SECURITY_ADMIN_PASSWORD）
  - 将监控对外访问限制在内网或 VPN

🚧 项目正在持续演进，欢迎反馈与贡献。

## 备份与恢复脚本样例

- 数据库（Postgres）
  - 备份：scripts/backup_postgres.sh [输出目录]
  - 恢复：scripts/restore_postgres.sh <dump.sql.gz>
  - 默认连接容器名 gas-db，数据库 gas，用户 gas，密码 gas_pass（可通过环境变量覆盖）

- 文件目录（uploads/ 与 exports/）
  - 备份：scripts/backup_files.sh [输出目录]
  - 恢复：scripts/restore_files.sh <files-*.tar.gz>

注意：请将备份文件异地保存并定期校验恢复流程。
