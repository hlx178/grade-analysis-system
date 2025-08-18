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
│   └── utils.py           # 工具函数
├── static/
│   ├── css/
│   ├── js/
│   └── images/
├── templates/
│   ├── base.html
│   ├── dashboard.html
│   └── ...
├── tests/
├── requirements.txt
├── config.py
├── run.py
└── README.md
```

## 快速开始

1. 克隆项目
```bash
git clone https://github.com/your-username/grade-analysis-system.git
cd grade-analysis-system
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 初始化数据库
```bash
python run.py init-db
```

4. 运行应用
```bash
python run.py
```

5. 访问 http://localhost:5000

## 开发状态

🚧 项目正在开发中...