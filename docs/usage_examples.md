# LLM 新闻日报生成工具 - 使用示例

本文档提供了一些常见的使用场景和示例，帮助你充分利用这个工具。

## 基础用法

### 生成今日报告

最简单的方式是直接运行主脚本：

```bash
python run.py
```

这将按照默认配置执行完整的工作流程：爬取 Reddit、清洗数据、生成摘要、创建报告。

### 查看帮助信息

```bash
python run.py --help
```

## 进阶用法

### 跳过特定步骤

如果你已经有了爬取的数据，想重新生成报告：

```bash
python run.py --skip-scrape --skip-clean
```

### 自定义数据源

监控其他 Reddit 社区：

```bash
python run.py --reddit-url "https://www.reddit.com/r/MachineLearning/"
```

### 调整时间窗口

获取最近 72 小时的新闻：

```bash
python run.py --hours 72
```

### 指定输出位置

将报告保存到特定目录：

```bash
python run.py --output-dir "D:\My Reports\LLM News"
```

### 启用详细日志

```bash
python run.py --verbose
```

## 脚本集成示例

### 定时任务（Windows 任务调度器）

创建一个批处理文件 `generate_report.bat`：

```batch
@echo off
cd /d "D:\Projects\llm_report"
set GEMINI_API_KEY=your_api_key_here
python run.py --output-dir "D:\Reports\%date:~0,4%-%date:~5,2%-%date:~8,2%"
```

然后在 Windows 任务调度器中设置每日运行。

### 作为模块导入

你也可以在自己的 Python 脚本中导入和使用此工具：

```python
# 导入需要的模块
from llm_report_tool.scrapers.reddit_scraper import RedditScraper
from llm_report_tool.processors.data_cleaner import DataCleaner
from llm_report_tool.processors.summarizer import TextSummarizer
from llm_report_tool.processors.report_generator import ReportGenerator

# 设置你的API密钥
import os
os.environ["GEMINI_API_KEY"] = "your_api_key_here"

# 爬取数据
scraper = RedditScraper("https://www.reddit.com/r/LocalLLaMA/")
df = scraper.scrape_posts()

# 清洗数据
cleaner = DataCleaner()
cleaned_df = cleaner.clean_data()

# 生成摘要
summarizer = TextSummarizer()
summarizer.summarize_posts()

# 创建报告
generator = ReportGenerator()
generator.generate_docx_report()
```

## 自定义报告模板

如果你想自定义报告格式，可以修改 `report_generator.py` 文件中的 `generate_docx_report` 方法。

例如，添加公司标志：

```python
def generate_docx_report(self):
    # ...现有代码...

    # 添加公司标志
    doc.add_picture("path/to/logo.png", width=Inches(2))

    # ...继续其他代码...
```

## 扩展新的内容源

如果你想添加其他数据源，可以参考现有的 `reddit_scraper.py` 实现新的爬虫，例如：

```python
# twitter_scraper.py 示例框架
class TwitterScraper:
    def __init__(self, query):
        self.query = query

    def scrape_tweets(self):
        # 实现Twitter爬虫逻辑
        pass
```

然后在主流程中集成这个新的爬虫。
