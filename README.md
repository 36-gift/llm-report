# <center>📰 LLM 新闻日报自动生成工具 🤖</center>

<center>
<!-- Placeholder Badges -->
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white" alt="Python Version">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License">
  <!-- Add other relevant badges here, e.g., build status, coverage -->
</center>

---

## 📖 概述

本工具旨在自动化地从 Reddit 的特定版块（默认为 `r/LocalLLaMA`）抓取最新的关于大型语言模型（LLM）的讨论帖子，对内容进行清洗、摘要生成、智能分类，并最终生成一份结构化的日报（目前支持 PDF 格式），帮助用户快速了解 LLM 领域的最新动态和热点话题。

---

## 🌳 项目结构

```
llm_report/
├── .env.example          # 环境变量示例文件
├── .gitignore            # Git 忽略文件配置
├── config.json           # 默认配置文件
├── config.json.example   # 配置文件示例
├── data/                 # 存放生成的数据文件 (被 .gitignore 忽略)
│   ├── *.xlsx
│   ├── *.txt
│   └── *.json
├── drivers/              # (可选) 存放 WebDriver 二进制文件
├── llm_report_tool/      # 主要工具代码
│   ├── __init__.py
│   ├── main.py             # 主入口和工作流控制
│   ├── scrapers/         # 爬虫模块
│   │   └── reddit_scraper.py
│   ├── processors/       # 数据处理模块
│   │   ├── data_cleaner.py
│   │   ├── summarizer.py
│   │   ├── classifier.py       # (原 topic_extractor.py)
│   │   └── latex_report_generator.py
│   └── utils/            # 工具函数和配置
│       └── config.py
├── reports/              # 存放生成的报告和中间文件 (被 .gitignore 忽略)
│   ├── *.pdf
│   ├── *.tex
│   └── ... (其他 LaTeX 文件)
│   └── utils/            # 工具函数和配置
│       └── config.py
├── README.md             # 项目说明文件 (就是您正在看的这个)
├── pyproject.toml        # Poetry 配置和依赖管理
├── poetry.lock           # Poetry 锁定文件
├── tests/                # (可选) 单元测试和集成测试
└── verify_setup.py       # 用于检查环境设置的脚本
```

---

## ✨ 主要功能

- **🤖 自动抓取**: 使用 Selenium 和 Chrome/Chromedriver 从指定的 Reddit URL 抓取设定时间范围内（默认 24 小时）的帖子。
- **🧹 数据清洗**:
  - 移除明显空白或无效的帖子内容。
  - (可选) 使用 LLM API (**DeepSeek**) 对帖子内容进行质量评分，过滤低质量或不相关的帖子。
- **✍️ 内容摘要**: 使用 LLM API (**DeepSeek**) 为每个高质量帖子生成简洁明了的中文摘要。
- **🏷️ 智能分类**: 使用 LLM API (**DeepSeek**) 对生成的摘要进行内容分类（如"模型发布"、"性能评测"等）。
- **🔥 热点总结**:
  - (可选) 基于分类结果，识别当天讨论最多的分类，并生成分类热点总结。
  - (当前实现) 基于所有摘要内容，识别当天讨论频率最高的**核心概念**（如模型名称、技术术语），并生成概念热点总结。
- **📄 报告生成**: 将分类后的摘要和热点总结整合，生成专业的 **PDF** 格式日报（使用 **LaTeX**）。
- **🔧 高度可配置**: 支持通过 `config.json` 文件和环境变量自定义大部分行为（如 Reddit URL、API 密钥、时间范围、LLM 温度参数等）。
- **🧩 模块化设计**: 各个处理阶段（抓取、清洗、摘要、分类、报告）解耦，方便单独运行或跳过某些阶段。

---

## 🚀 技术栈

- **核心语言**: Python 3.10+
- **数据抓取**: Selenium, BeautifulSoup4, webdriver-manager
- **数据处理**: Pandas
- **LLM API**: DeepSeek API (用于内容分析、摘要、分类、概念提取)
- **报告生成**: PyLaTeX, XeLaTeX (_轻量化 TeX 环境，专为 macOS 优化_)
- **依赖管理**: Poetry, pyenv (_推荐用于 macOS 开发_)
- **配置管理**: python-dotenv, JSON

---

## ⚙️ 环境设置

本节介绍如何设置运行此工具所需的环境。

#### 1. 克隆仓库

```bash
git clone https://github.com/36-gift/llm_report.git
cd <repository-directory>
```

#### 2. 创建虚拟环境 (_推荐_)

推荐使用 `conda` 创建虚拟环境：

```bash
conda create -n llm_report python=3.10 -y
conda activate llm_report
```

_如果您不使用 `conda`，也可以使用 Python 内置的 `venv`：_

```bash
# python -m venv venv
# Windows: .\venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
```

#### 3. 安装依赖

推荐使用 Poetry 进行依赖管理：

```bash
# 安装 Poetry (如果尚未安装)
curl -sSL https://install.python-poetry.org | python3 -

# 安装项目依赖
poetry install
```

_或者使用传统方式（不推荐）:_
```bash
# 仅在无法使用 Poetry 时
pip install pandas requests beautifulsoup4 selenium webdriver-manager python-dotenv pylatex lxml numpy openai openpyxl
```

_注意: 这会自动安装 `webdriver-manager`，它会尝试下载合适的 ChromeDriver。_

#### 4. 设置环境变量

- **必需**: 创建一个 `.env` 文件（可从 `.env.example` 复制），并填入您的 **DeepSeek API 密钥**：
  ```dotenv
  # .env
  DEEPSEEK_API_KEY="your_deepseek_api_key_here"
  ```
- _(可选)_ 您也可以在 `.env` 文件中设置其他配置，如 `REDDIT_URL`, `POST_CLEANUP_HOURS` 等。

#### 5. 安装 XeLaTeX 环境 (_用于生成 PDF_)

为了生成 PDF 报告，您需要安装 **XeLaTeX**（比传统 LaTeX 更轻量，更适合 macOS）。

- **macOS** (推荐): 安装轻量版本
  ```bash
  # 使用 Homebrew 安装轻量版 TeX Live
  brew install --cask mactex-no-gui
  # 或者安装最小化版本
  brew install --cask basictex
  ```
  - **优势**: 更小的安装包（~100MB vs 4GB+），更快的编译速度
  - **验证**: `xelatex --version`

- **传统安装** (可选)
  - **Windows**: [TeX Live](https://www.tug.org/texlive/acquire-netinstall.html) - 选择 `scheme-basic` 即可
  - **macOS**: [MacTeX](https://www.tug.org/mactex/downloading.html) - 完整版本（较大）
  - **Linux**: 轻量化安装
    ```bash
    # Ubuntu/Debian
    sudo apt-get install texlive-xetex texlive-lang-chinese texlive-fonts-recommended
    # Fedora
    sudo dnf install texlive-xetex texlive-collection-langchinese
    ```

**验证安装**: 运行 `xelatex --version` 查看版本信息

**为什么选择 XeLaTeX?**
- 🚀 **更轻量**: 无需安装完整的 TeX Live（从 4GB+ 减少到 ~100MB）
- ⚡ **更快速**: 编译速度更快，特别适合 macOS
- 🌏 **更好的中文支持**: 原生支持 Unicode 和系统字体

---

## 🛠️ 使用方法

### 📊 **检查当前状态**

在开始之前，建议先检查当前工作流状态：

```bash
poetry run python main.py --status
```

这会显示已存在的文件和建议的恢复选项，帮助您决定从哪个阶段开始。

### 🔄 **智能恢复 (推荐)**

**最简单的方式** - 让系统自动检测应该从哪里继续：

```bash
poetry run python main.py --auto-resume
```

系统会：
- 🔍 自动扫描已存在的文件
- 🎯 确定最佳恢复点
- ⚡ 跳过已完成的阶段
- 🚀 从正确的位置继续执行

### 📈 **工作流程阶段详解**

LLM报告工具包含 **5个主要阶段**，每个阶段都可以独立跳过或恢复：

#### **阶段 1: 数据爬取** 🕷️
- **作用**: 从 Reddit 抓取 LLM 相关帖子
- **输出**: `data/reddit_posts_YYYY-MM-DD.xlsx`
- **恢复**: `poetry run python main.py --skip-scrape`

#### **阶段 2: 数据清洗** ✨
- **作用**: 分析帖子质量，过滤低质量内容
- **输入**: 原始帖子数据
- **输出**: `data/cleaned_reddit_posts_YYYY-MM-DD.xlsx`
- **恢复**: `poetry run python main.py --skip-scrape --skip-clean`

#### **阶段 3: 摘要生成** 📝
- **作用**: 使用 DeepSeek API 生成中文摘要
- **输入**: 清洗后的帖子数据
- **输出**: `data/summaries_YYYY-MM-DD.txt`
- **恢复**: `poetry run python main.py --resume-from-summary`

#### **阶段 4: 智能分类** 🧠
- **作用**: 按主题分类摘要，提取热点概念
- **输入**: 摘要文本文件
- **输出**: `data/classified_summaries_YYYY-MM-DD.json`
- **恢复**: `poetry run python main.py --skip-scrape --skip-clean --skip-summary`

#### **阶段 5: 报告生成** 📄
- **作用**: 生成专业的 PDF 格式日报
- **输入**: 分类后的数据
- **输出**: `reports/YYYY-MM-DD-llm-news-daily.pdf`
- **恢复**: `poetry run python main.py --resume-from-report`

### 🎮 **快速恢复命令**

| 想要从这里开始 | 使用这个命令 | 适用场景 |
|:-------------|:------------|:---------|
| **🔄 自动检测** | `poetry run python main.py --auto-resume` | ⭐ **推荐** - 让系统决定 |
| **📝 摘要生成** | `poetry run python main.py --resume-from-summary` | 已有清洗后的数据 |
| **📄 报告生成** | `poetry run python main.py --resume-from-report` | 已有分类后的数据 |
| **🧠 分类步骤** | `poetry run python main.py --skip-scrape --skip-clean --skip-summary` | 已有摘要文件 |
| **✨ 清洗步骤** | `poetry run python main.py --skip-scrape` | 已有原始数据 |

### 🎯 **特殊模式**

#### **演示模式** 🎪
无需真实数据和API密钥，使用示例数据快速体验：
```bash
poetry run python main.py --demo
```

#### **无API模式** 🔒
当没有API密钥时，使用基于规则的处理：
```bash
poetry run python main.py --no-api
```

#### **快速模式** ⚡
遇到API错误时自动跳过相关步骤：
```bash
poetry run python main.py --quick
```

### 🔧 **高级选项**

| 选项 | 描述 | 示例 |
|:-----|:-----|:-----|
| `--classifier-input-file` | 指定自定义摘要文件 | `--classifier-input-file data/summaries_2025-06-20.txt` |
| `--report-input-file` | 指定自定义分类数据 | `--report-input-file data/classified_summaries_2025-06-20.json` |
| `--reddit-url` | 更换数据源 | `--reddit-url https://www.reddit.com/r/MachineLearning/` |
| `--hours` | 限制时间范围 | `--hours 12` (最近12小时) |
| `--output-dir` | 自定义输出目录 | `--output-dir /path/to/custom/output` |
| `--verbose` | 详细日志 | `-v` 或 `--verbose` |

### 💡 **实用技巧**

1. **🔍 随时检查状态**:
   ```bash
   poetry run python main.py --status
   ```

2. **⚡ 跳过重复工作**:
   ```bash
   poetry run python main.py --auto-resume
   ```

3. **🎯 只生成新报告**:
   ```bash
   poetry run python main.py --resume-from-report
   ```

4. **🔄 重新处理特定日期**:
   ```bash
   poetry run python main.py --classifier-input-file data/summaries_2025-06-20.txt
   ```

5. **🎪 测试新功能**:
   ```bash
   poetry run python main.py --demo --verbose
   ```

---

## 🚀 **当前状态 & 最新更新**

### ✅ **系统状态概览** (2025-06-27)

**🎯 完全就绪** - 所有核心功能已实现并测试通过：

- **✅ DeepSeek API 集成**: 已从 SiliconFlow 成功迁移至官方 DeepSeek API
- **✅ 智能恢复系统**: 支持从任意阶段恢复，无需重新开始
- **✅ PDF 格式优化**: 修复了格式问题，现在生成美观的专业报告
- **✅ 路径结构优化**: 报告输出路径从 `llm_report_tool/reports/` 迁移至 `reports/`
- **✅ 错误处理增强**: 全面的错误恢复和重试机制
- **✅ 测试覆盖完整**: 40+ 测试用例确保系统稳定性

### 🔧 **技术架构亮点**

| 组件 | 状态 | 描述 |
|:-----|:-----|:-----|
| **🕷️ Reddit 爬虫** | ✅ 稳定 | 智能内容抓取，支持时间过滤 |
| **🧹 数据清洗器** | ✅ 增强 | DeepSeek API + 规则双重质量评分 |
| **📝 摘要生成器** | ✅ 优化 | DeepSeek-chat 模型，无速率限制 |
| **🧠 智能分类器** | ✅ 先进 | 自动主题分类 + 热点概念提取 |
| **📄 PDF 生成器** | ✅ 专业 | XeLaTeX 引擎，完美中文支持 |

### 🔄 **智能恢复特性**

系统会自动检测已完成的工作，建议最佳恢复点：

**当前数据状态**:
- ✅ **scraped_data**: reddit_posts_2025-06-27.xlsx 已存在
- ✅ **cleaned_data**: cleaned_reddit_posts_2025-06-27.xlsx 已存在
- ✅ **summaries**: summaries_2025-06-27.txt 已存在
- ✅ **classified_data**: classified_summaries_2025-06-27.json 已存在
- ✅ **pdf_report**: 2025-06-27-llm-news-daily.pdf 已存在

**💡 建议**: 所有文件已存在，可以直接使用 `--auto-resume` 或从任何阶段重新开始

### 🆕 **最新功能特性**

#### **🔄 智能恢复系统**
```bash
# 一键自动恢复
poetry run python main.py --auto-resume

# 检查当前状态
poetry run python main.py --status
```

#### **🎪 演示模式**
```bash
# 无需 API 密钥快速体验
poetry run python main.py --demo
```

#### **🔒 离线模式**
```bash
# 基于规则的处理，无需 API 调用
poetry run python main.py --no-api
```

#### **📊 状态监控**
```bash
# 实时查看工作流进度
poetry run python main.py --status --verbose
```

### 🛡️ **稳定性保证**

- **🔄 自动重试**: API 调用失败时智能重试
- **💾 增量处理**: 避免重复计算，节省时间和资源
- **🚫 故障隔离**: 单个阶段失败不影响其他阶段
- **📝 详细日志**: 完整的操作记录，便于问题诊断
- **⚡ 性能优化**: DeepSeek API 响应时间 2-5 秒

### 🔮 **使用建议**

1. **首次使用**: `poetry run python main.py --demo` (体验完整流程)
2. **日常使用**: `poetry run python main.py --auto-resume` (智能恢复)
3. **问题排查**: `poetry run python main.py --status --verbose` (详细诊断)
4. **自定义处理**: 使用 `--classifier-input-file` 等参数处理历史数据

---

## 📄 输出文件

默认情况下，工具会在 `data/` 和 `reports/` 目录下生成以下文件（文件名中的日期为执行日期）：

- `data/reddit_posts_YYYY-MM-DD.xlsx`: 📊 爬虫抓取的原始帖子数据。
- `data/cleaned_reddit_posts_YYYY-MM-DD.xlsx`: ✨ 经过清洗和质量评分后的帖子数据。
- `data/summaries_YYYY-MM-DD.txt`: 📝 为高质量帖子生成的摘要文本文件。
- `data/classified_summaries_YYYY-MM-DD.json`: 🧠 包含每个摘要的分类结果和提取的概念热点总结。
- `reports/YYYY-MM-DD-llm-news-daily.pdf`: 📰 **最终生成的 PDF 格式日报**。
- `reports/*.log`, `.aux`, `.tex`, etc.: ⚙️ LaTeX 编译过程中的中间文件（如果未被自动清理）。

---

## ⚙️ 配置 (`config.json`)

您可以通过修改项目根目录下的 `config.json` 文件来调整部分默认行为（环境变量会覆盖此文件中的设置）：

```json
{
  "reddit_url": "https://www.reddit.com/r/LocalLLaMA/",
  "post_cleanup_hours": 24,
  "report_title": "LLM 技术日报",
  "report_prefix": "llm-news-daily",
  "temperature": {
    "summarizer": 0.6,
    "topic_extractor": 0.8,
    "data_cleaner": 0.8
  }
}
```

- `reddit_url`: 默认爬取的 Reddit URL。
- `post_cleanup_hours`: 默认抓取的时间范围（小时）。
- `report_title`: PDF 报告的标题。
- `report_prefix`: PDF 报告文件名的前缀。
- `temperature`: 不同阶段调用 LLM API 时的温度参数。

---

## ⚠️ 免责声明

> - 本工具生成的摘要、分类和热点总结均由大型语言模型（DeepSeek API）自动生成，可能包含不准确、不完整或有偏见的信息。**请用户自行判断内容的准确性和可靠性**。
> - 本工具仅用于**学习和技术研究**目的。对于使用本工具抓取、处理或生成的内容，以及由此产生的任何后果，开发者不承担任何责任。
> - 请确保您有权访问和使用目标 Reddit 版块的内容，并遵守 **Reddit 的服务条款**。
> - 使用 API 可能产生费用，请查阅 **DeepSeek API** 的定价策略。

---

## 🙏 致谢

> - 感谢 **Reddit** <img src="https://img.shields.io/badge/Reddit-%23FF4500.svg?&style=flat-square&logo=reddit&logoColor=white" alt="Reddit Badge"/> 提供了丰富的信息来源。
> - 感谢 **DeepSeek** <img src="https://img.shields.io/badge/AI-DeepSeek-blueviolet?style=flat-square" alt="DeepSeek Badge"/> 提供了强大的 LLM API 支持。
> - 感谢 **Selenium** <img src="https://img.shields.io/badge/Selenium-%43B02A.svg?&style=flat-square&logo=selenium&logoColor=white" alt="Selenium Badge"/>, **BeautifulSoup4** <img src="https://img.shields.io/badge/BeautifulSoup4-%23C41515.svg?&style=flat-square&logo=python&logoColor=white" alt="BeautifulSoup4 Badge"/>, **Pandas** <img src="https://img.shields.io/badge/Pandas-%23150458.svg?&style=flat-square&logo=pandas&logoColor=white" alt="Pandas Badge"/>, **PyLaTeX** <img src="https://img.shields.io/badge/PyLaTeX-%233776AB.svg?&style=flat-square&logo=python&logoColor=white" alt="PyLaTeX Badge"/> 等开源库的开发者。
> - 感谢 **TeX Live** <img src="https://img.shields.io/badge/TeX-%23008080.svg?&style=flat-square&logo=tex&logoColor=white" alt="TeX Badge"/> 社区提供了优秀的 TeX 发行版。

---

希望这份 README 对您有所帮助！
