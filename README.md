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

## 开发状态

🚧 项目正在开发中...