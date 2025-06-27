# LLM 新闻日报自动生成工具 (macOS 版)

<div align="center">
  <img src="https://img.shields.io/badge/macOS-M4%20优化-blue?logo=apple&logoColor=white" alt="macOS Support">
  <img src="https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white" alt="Python Version">
  <img src="https://img.shields.io/badge/Poetry-依赖管理-green?logo=poetry&logoColor=white" alt="Poetry">
  <img src="https://img.shields.io/badge/DeepSeek-AI%20摘要-orange" alt="DeepSeek AI">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License">
</div>

## 📖 项目概述

LLM 新闻日报自动生成工具是一个专为 **macOS** 优化的自动化工具，能够从 Reddit 的 LLM 相关版块自动抓取最新讨论，使用 DeepSeek AI 进行内容分析和摘要生成，最终输出结构化的中文 PDF 日报。

### ✨ 核心功能

- **🤖 智能抓取**: 使用 Selenium 自动从 Reddit 抓取 LLM 相关讨论
- **🧹 内容清洗**: 过滤低质量和无关内容，确保报告质量
- **✍️ AI 摘要**: 使用 DeepSeek API 生成准确的中文摘要
- **🏷️ 智能分类**: 自动将内容按主题分类（模型发布、性能评测等）
- **🔥 热点分析**: 识别当日讨论最多的技术热点
- **📄 PDF 报告**: 生成专业格式的 PDF 日报

## 🚀 macOS 专门优化

### 系统要求

- **macOS 12.0+** (建议 macOS 14.0+ 以获得最佳性能)
- **Apple Silicon (M1/M2/M3/M4)** 或 **Intel 处理器**
- **Homebrew** 包管理器
- **Python 3.11+** (通过 pyenv 管理)

### 🛠️ 快速安装 (macOS)

#### 1. 安装系统依赖

```bash
# 安装 Homebrew (如果尚未安装)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安装 Python 版本管理器
brew install pyenv

# 安装 Poetry 依赖管理器
curl -sSL https://install.python-poetry.org | python3 -

# 安装轻量版 LaTeX (用于 PDF 生成)
brew install --cask basictex
```

#### 2. 设置 Python 环境

```bash
# 克隆项目
git clone https://github.com/36-gift/llm-report.git
cd llm-report

# 安装并设置 Python 3.11
pyenv install 3.11.12
pyenv local 3.11.12

# 配置 Poetry 环境
poetry env use python3.11
poetry install
```

#### 3. 配置 API 密钥

```bash
# 复制环境配置文件
cp config.json.example config.json

# 创建环境变量文件
echo 'DEEPSEEK_API_KEY="your_api_key_here"' > .env
```

> 💡 **获取 DeepSeek API 密钥**: 访问 [DeepSeek 官网](https://www.deepseek.com/) 注册并获取免费 API 密钥

#### 4. 验证安装

```bash
# 检验环境设置
poetry run python verify_setup.py

# 运行状态检查
poetry run python main.py --status
```

## 📊 使用指南

### 🎯 快速开始

```bash
# 自动检测并恢复工作流
poetry run python main.py --auto-resume
```

这个命令会自动：

- 🔍 检测已有的数据文件
- 🎯 确定最佳的恢复点
- ⚡ 跳过已完成的步骤
- 🚀 从正确位置继续执行

### 📈 工作流程

LLM 报告工具包含 **5 个主要阶段**：

#### 阶段 1: Reddit 数据抓取 🕷️

```bash
# 从多个 LLM subreddit 抓取帖子
poetry run python main.py
```

#### 阶段 2: 数据质量清洗 ✨

```bash
# 从清洗步骤开始
poetry run python main.py --skip-scrape
```

#### 阶段 3: AI 摘要生成 📝

```bash
# 从摘要步骤开始
poetry run python main.py --resume-from-summary
```

#### 阶段 4: 智能主题分类 🧠

```bash
# 从分类步骤开始
poetry run python main.py --skip-scrape --skip-clean --skip-summary
```

#### 阶段 5: PDF 报告生成 📄

```bash
# 仅生成报告
poetry run python main.py --resume-from-report
```

### ⚙️ 高级配置

#### 自定义 Reddit 源

```bash
# 指定特定的 subreddit
poetry run python main.py --reddit-url "https://www.reddit.com/r/LocalLLaMA"

# 设置时间范围 (小时)
poetry run python main.py --hours 48
```

#### 调试和开发

```bash
# 启用详细日志
poetry run python main.py --verbose

# 演示模式 (测试数据)
poetry run python main.py --demo

# 跳过 API 调用 (仅规则处理)
poetry run python main.py --no-api
```

## 📁 项目结构

```
llm-report/
├── main.py                    # 项目入口
├── llm_report_tool/          # 核心工具包
│   ├── main.py              # 主工作流控制
│   │   └── main.py
│   ├── scrapers/            # 爬虫模块
│   │   └── reddit_scraper.py
│   ├── processors/          # 数据处理模块
│   │   ├── data_cleaner.py
│   │   ├── summarizer.py
│   │   ├── classifier.py
│   │   └── latex_report_generator.py
│   └── utils/               # 工具模块
│       ├── config.py
│       ├── deepseek_client.py
│       └── rate_limiter.py
├── data/                    # 生成的数据文件
├── reports/                 # 输出的 PDF 报告
├── config.json.example      # 配置文件模板
└── pyproject.toml          # Poetry 项目配置
```

## 🔧 macOS 特定优化

### LaTeX 环境 (PDF 生成)

```bash
# 轻量版安装 (推荐)
brew install --cask basictex
sudo tlmgr update --self
sudo tlmgr install xetex collection-langchinese

# 验证安装
xelatex --version
```

### Chrome 驱动管理

工具会自动管理 Chrome 驱动程序，支持：

- Apple Silicon (M1/M2/M3/M4) 优化
- Intel macOS 兼容
- 自动驱动更新

### 性能优化建议

- **Apple Silicon**: 使用原生 ARM64 Python 以获得最佳性能
- **内存管理**: 建议至少 8GB RAM 用于大批量处理
- **并发设置**: M4 芯片建议使用 8-12 个并发线程

## 📊 输出示例

运行成功后，您将获得：

1. **数据文件** (`data/` 目录)

   - `reddit_posts_YYYY-MM-DD.xlsx` - 原始抓取数据
   - `cleaned_reddit_posts_YYYY-MM-DD.xlsx` - 清洗后数据
   - `summaries_YYYY-MM-DD.txt` - AI 生成摘要
   - `classified_summaries_YYYY-MM-DD.json` - 分类结果

2. **PDF 报告** (`reports/` 目录)
   - `YYYY-MM-DD-llm-news-daily.pdf` - 最终日报

## 🐛 常见问题 (macOS)

### Chrome 驱动问题

```bash
# 如果遇到权限问题
xattr -d com.apple.quarantine /path/to/chromedriver
```

### LaTeX 字体问题

```bash
# 更新字体缓存
fc-cache -fv
```

### 网络连接问题

```bash
# 如果遇到 SSL 证书问题
pip install --upgrade certifi
```

## 🔄 更新和维护

```bash
# 更新项目依赖
poetry update

# 更新 Chrome 驱动
poetry run python -c "from webdriver_manager.chrome import ChromeDriverManager; ChromeDriverManager().install()"

# 清理缓存和临时文件
poetry run python -c "import tempfile, shutil; shutil.rmtree(tempfile.gettempdir(), ignore_errors=True)"
```

## 📝 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

## 🤝 贡献

欢迎提交 Issues 和 Pull Requests！

---

<div align="center">
  <p><strong>专为 macOS 用户打造的 LLM 新闻自动化工具</strong></p>
  <p>🍎 针对 Apple Silicon 优化 | 🚀 一键式自动化 | �� 专业级报告</p>
</div>
