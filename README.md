# LLM 新闻日报生成工具

![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

自动化工具，用于爬取 Reddit 上的大语言模型（LLM）相关新闻，清洗数据，生成摘要，并输出格式化的日报文档。

## 功能特点

- **自动爬取**: 使用 Selenium 自动爬取 Reddit 上关于大语言模型的最新帖子
- **智能筛选**: 去除无效内容，过滤过期信息
- **AI 摘要生成**: 利用 Google 的 Gemini API 自动生成高质量摘要
- **格式化报告**: 将摘要转换为结构良好的 Word 文档
- **完全自动化**: 一条命令完成从爬取到报告生成的全流程
- **灵活配置**: 支持自定义 Reddit 来源、时间筛选和输出格式

## 安装步骤

### 前置要求

- Python 3.10 或更高版本
- Chrome 浏览器（用于 Selenium 爬虫）
- Google Gemini API 密钥

### 安装过程

1. 克隆仓库

```bash
git clone https://github.com/36-gift/llm_report.git
cd llm_report
```

2. 安装依赖

```bash
pip install -r requirements.txt
```

3. 设置环境变量

```bash
# Windows (PowerShell)
$env:GEMINI_API_KEY="your-api-key-here"

# Windows (CMD)
set GEMINI_API_KEY=your-api-key-here

# Linux/macOS
export GEMINI_API_KEY="your-api-key-here"
```

或者创建`.env`文件，内容如下：

```
GEMINI_API_KEY=your-api-key-here
```

## 使用方法

### 基本用法

运行完整工作流程：

```bash
python run.py
```

### 高级选项

```bash
# 显示详细日志
python run.py --verbose

# 跳过爬虫阶段，使用已有数据
python run.py --skip-scrape

# 设置Reddit版块URL
python run.py --reddit-url "https://www.reddit.com/r/MachineLearning/"

# 设置过滤时间（小时）
python run.py --hours 72

# 指定输出目录
python run.py --output-dir "./output"

# 获取帮助
python run.py --help
```

## 项目结构

```
llm_report/
├── llm_report_tool/          # 核心代码包
│   ├── scrapers/             # 爬虫模块
│   │   └── reddit_scraper.py # Reddit爬虫
│   ├── processors/           # 处理器模块
│   │   ├── data_cleaner.py   # 数据清洗
│   │   ├── summarizer.py     # 文本摘要
│   │   └── report_generator.py # 报告生成
│   ├── utils/                # 工具模块
│   │   └── config.py         # 配置管理
│   └── main.py               # 主程序入口
├── data/                     # 数据存储目录
├── docs/                     # 文档目录
├── tests/                    # 测试代码
├── run.py                    # 启动脚本
├── requirements.txt          # 项目依赖
├── config.json.example       # 配置文件示例
└── README.md                 # 项目说明
```

## 配置选项

你可以创建一个`config.json`文件来自定义配置：

```json
{
  "reddit_url": "https://www.reddit.com/r/LocalLLaMA/",
  "post_cleanup_hours": 48,
  "summary_batch_size": {
    "min": 5,
    "max": 10
  }
}
```

## 输出示例

生成的报告将保存在`llm_report_tool/reports/`目录（或指定的输出目录）中，文件名格式为`YYYY-MM-DD-llm-news.docx`。

## 常见问题

### 爬虫无法工作？

确保已安装最新版 Chrome 浏览器，且 webdriver-manager 能正确下载匹配的驱动。

### API 密钥错误？

检查是否正确设置了`GEMINI_API_KEY`环境变量。

### 如何自定义报告格式？

修改`llm_report_tool/processors/report_generator.py`文件中的文档生成部分。

## 贡献指南

欢迎提交 Pull Request 或 Issue！

## 许可证

[MIT](LICENSE)
