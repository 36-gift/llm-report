# <center>📰 LLM 新闻日报自动生成工具 🤖</center>

<!-- Placeholder Badges -->
<p align="center">
  ![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
  ![License](https://img.shields.io/badge/License-MIT-green)
  <!-- Add other relevant badges here, e.g., build status, coverage -->
</p>

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
│   ├── reports/            # 存放生成的报告和中间文件 (被 .gitignore 忽略)
│   │   ├── *.pdf
│   │   ├── *.tex
│   │   └── ... (其他 LaTeX 文件)
│   └── utils/            # 工具函数和配置
│       └── config.py
├── README.md             # 项目说明文件 (就是您正在看的这个)
├── requirements.txt      # Python 依赖列表
├── tests/                # (可选) 单元测试和集成测试
└── verify_setup.py       # (可能) 用于检查环境设置的脚本
```

---

## ✨ 主要功能

- **🤖 自动抓取**: 从指定的 Reddit URL 抓取设定时间范围内（默认 24 小时）的帖子。
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
- **数据抓取**: Selenium, Requests, BeautifulSoup4
- **数据处理**: Pandas
- **LLM API**: DeepSeek API (用于内容分析、摘要、分类、概念提取)
- **报告生成**: PyLaTeX, XeLaTeX (_需要本地安装 TeX 发行版_)
- **依赖管理**: pip, `requirements.txt`
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

_确保您的 `conda` 环境已激活_

```bash
pip install -r requirements.txt
```

_注意: 这会自动安装 `webdriver-manager`，它会尝试下载合适的 ChromeDriver。_

#### 4. 设置环境变量

- **必需**: 创建一个 `.env` 文件（可从 `.env.example` 复制），并填入您的 **DeepSeek API 密钥**：
  ```dotenv
  # .env
  DEEPSEEK_API_KEY="your_deepseek_api_key_here"
  ```
- _(可选)_ 您也可以在 `.env` 文件中设置其他配置，如 `REDDIT_URL`, `POST_CLEANUP_HOURS` 等。

#### 5. 安装 LaTeX 环境 (_用于生成 PDF_)

为了生成 PDF 报告，您需要在本地安装一个 **TeX 发行版**。

- **Windows**: 推荐安装 [**MiKTeX**](https://miktex.org/download)。
  - 安装后，请务必打开 **MiKTeX Console** -> **Packages**，搜索并安装 `xeCJK` 宏包（这是中文支持的关键）。
- **macOS**: 推荐安装 [**MacTeX**](https://www.tug.org/mactex/downloading.html) (包含了 TeX Live 和所需工具)。
- **Linux**: 可以通过包管理器安装 **TeX Live**。
  - Debian/Ubuntu: `sudo apt-get update && sudo apt-get install texlive-xetex texlive-lang-chinese` (或者 `texlive-full` 如果您不介意大小)
  - Fedora: `sudo dnf install texlive-scheme-basic texlive-xetex texlive-collection-langchinese` (或者 `texlive-scheme-full`)
  - _请根据您的发行版调整包名。_
- **验证**: 安装完成后，尝试在终端运行 `xelatex --version`，如果成功显示版本信息，则表示安装基本成功。

---

## 🛠️ 使用方法

通过运行项目根目录下的 `main.py` 脚本来启动整个工作流程。支持多种命令行参数来控制执行过程：

```bash
python main.py [选项]
```

#### **常用选项**

| 选项                      | 缩写 | 描述                                                                         |
| :------------------------ | :--- | :--------------------------------------------------------------------------- |
| `--skip-scrape`           |      | 🚫 跳过 Reddit 爬取阶段。                                                    |
| `--skip-clean`            |      | 🚫 跳过数据清洗和质量分析阶段。                                              |
| `--skip-summary`          |      | 🚫 跳过摘要生成阶段。                                                        |
| `--skip-topic`            |      | 🚫 跳过智能分类和热点总结阶段。                                              |
| `--no-pdf`                |      | 🚫 不生成最终的 PDF 报告。                                                   |
| `--classifier-input-file` |      | 📝 指定分类器使用的输入摘要文件路径 (例如 `data/summaries_YYYY-MM-DD.txt`)。 |
| `--reddit-url`            |      | 🌐 指定要爬取的 Reddit 版块 URL。                                            |
| `--hours`                 |      | ⏰ 指定抓取多少小时内的帖子 (例如 `12`)。                                    |
| `--output-dir`            |      | 📁 指定所有输出文件的根目录。                                                |
| `--verbose`               | `-v` | 📢 启用更详细的日志输出。                                                    |

#### **示例**

- **🚀 完整运行**:
  ```bash
  python main.py
  ```
- **⏩ 跳过抓取和清洗，从摘要开始**:
  ```bash
  python main.py --skip-scrape --skip-clean
  ```
- **📑 仅运行分类和报告生成 (使用指定日期的摘要)**:
  ```bash
  python main.py --skip-scrape --skip-clean --skip-summary --classifier-input-file data/summaries_2025-04-29.txt
  ```

---

## 📄 输出文件

默认情况下，工具会在 `data/` 和 `llm_report_tool/reports/` 目录下生成以下文件（文件名中的日期为执行日期）：

- `data/reddit_posts_YYYY-MM-DD.xlsx`: 📊 爬虫抓取的原始帖子数据。
- `data/cleaned_reddit_posts_YYYY-MM-DD.xlsx`: ✨ 经过清洗和质量评分后的帖子数据。
- `data/summaries_YYYY-MM-DD.txt`: 📝 为高质量帖子生成的摘要文本文件。
- `data/classified_summaries_YYYY-MM-DD.json`: 🧠 包含每个摘要的分类结果和提取的概念热点总结。
- `llm_report_tool/reports/YYYY-MM-DD-llm-news-daily.pdf`: 📰 **最终生成的 PDF 格式日报**。
- `llm_report_tool/reports/*.log`, `.aux`, `.tex`, etc.: ⚙️ LaTeX 编译过程中的中间文件（如果未被自动清理）。

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

> - 感谢 **Reddit** 提供了丰富的信息来源。
> - 感谢 **DeepSeek** 提供了强大的 LLM API 支持。
> - 感谢 **Selenium**, **Requests**, **BeautifulSoup4**, **Pandas**, **PyLaTeX** 等开源库的开发者。
> - 感谢 **MiKTeX/TeX Live** 社区提供了优秀的 TeX 发行版。

---

希望这份 README 对您有所帮助！
