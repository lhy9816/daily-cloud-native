# Daily Cloud Native Briefing

每日云原生技术简报自动生成工具。从多个信息源收集云原生、Kubernetes、AI Infrastructure 相关动态，通过 LLM 智能分析生成每日简报，并推送到飞书。

## 功能特性

- **多源数据收集**: GitHub Trending、CNCF Blog、Kubernetes Blog、ArXiv 论文、技术博客、微信公众号
- **智能内容分析**: 使用 LLM 对内容进行分类、摘要和重要性评估
- **自动去重**: 基于历史记录避免重复推送
- **飞书推送**: 生成格式化的飞书卡片消息
- **GitHub 归档**: 自动将简报归档到 content 目录

## 数据来源

| 来源 | 类型 | 说明 |
|------|------|------|
| GitHub | Repository | 监控指定仓库动态和关键词 trending |
| CNCF Blog | RSS | CNCF 官方博客 |
| Kubernetes Blog | RSS | Kubernetes 官方博客 |
| ArXiv | API | 分布式系统、机器学习相关论文 |
| InfoQ / NewStack | RSS | 技术媒体文章 |
| 微信公众号 | RSSHub | 云原生相关公众号 |

## 快速开始

### 1. 安装依赖

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件：

```env
LLM_API_KEY=your_llm_api_key
GITHUB_TOKEN=your_github_token  # 可选，提高 API 限流
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
```

### 3. 运行

```bash
# 完整运行
python main.py

# 仅收集和分析，不推送（dry-run）
python main.py --dry-run

# 跳过特定收集器
python main.py --skip-wechat --skip-arxiv

# 使用自定义配置文件
python main.py --config myconfig.yaml
```

## 配置说明

编辑 `config.yaml` 自定义数据源和关键词：

```yaml
sources:
  github:
    keywords:
      - kubernetes
      - cloud-native
    watch_repos:
      - "kubernetes/kubernetes"
  arxiv:
    categories:
      - "cs.DC"
    keywords:
      - kubernetes
      - scheduling

llm:
  model: "glm-5"
  api_key: "${LLM_API_KEY}"
  base_url: "https://aiproxy.xin/cosphere/v1"

feishu:
  webhook_url: "${FEISHU_WEBHOOK_URL}"
```

## 项目结构

```
.
├── main.py              # 主入口
├── config.yaml          # 配置文件
├── config_loader.py     # 配置加载
├── models.py            # 数据模型
├── processor.py         # 内容处理和 LLM 分析
├── formatter.py         # 飞书卡片格式化
├── notifier.py          # 飞书推送
├── archiver.py          # GitHub 归档
├── collectors/          # 数据收集器
│   ├── base.py
│   ├── github.py
│   ├── cncf.py
│   ├── arxiv.py
│   ├── blogs.py
│   └── wechat.py
├── prompts/             # LLM 提示词模板
├── content/             # 生成的简报存档
├── data/                # 原始数据存储
└── logs/                # 运行日志
```

## 定时任务

### Windows (Task Scheduler)

使用 `run_daily.bat` 或配置计划任务每天早上 8 点运行。

### Linux (Cron)

```bash
0 8 * * * cd /path/to/daily-cloud-native && .venv/bin/python main.py >> logs/cron.log 2>&1
```

## License

MIT
