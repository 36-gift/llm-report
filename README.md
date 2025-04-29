# LLM 新闻日报生成工具

![Python Version](https://img.shields.io/badge/python-3.10-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-beta-yellow)

> 自动化工具，用于爬取 Reddit 上的大语言模型（LLM）相关新闻，清洗数据，生成摘要，并输出格式化的日报文档。

<div align="center">
  <a href="#-功能特点">功能特点</a> •
  <a href="#-安装步骤">安装步骤</a> •
  <a href="#-使用方法">使用方法</a> •
  <a href="#-配置选项">配置选项</a> •
  <a href="#-常见问题">常见问题</a> •
  <a href="#-致谢">致谢</a> •
  <a href="#-免责声明">免责声明</a>
</div>

## 🌟 功能特点

- **🔍 自动爬取**: 使用 Selenium 自动爬取 Reddit 上关于大语言模型的最新帖子，支持按日期范围筛选
- **🤖 内容质量分析**: 使用 DeepSeek API 分析内容质量并添加质量评分，保留所有原始数据
- **🖼️ 图片内容支持**: 支持提取和存储帖子中的图片链接，完整保留图文内容
- **🤖 AI 摘要生成**: 利用 DeepSeek API 自动生成高质量摘要
- **📊 话题抽取与分类**: 使用 NLP 技术自动提取主题并对摘要进行分类
- **📝 PDF 报告生成**: 支持生成基于 LaTeX 的 PDF 报告
- **⚙️ 完全自动化**: 一条命令完成从爬取到报告生成的全流程
- **🔧 灵活配置**: 支持自定义 Reddit 来源、时间筛选和输出格式

## 📋 安装步骤

### 前置要求

- Python 3.10+
- Chrome 浏览器（用于 Selenium 爬虫）
- DeepSeek API 密钥
- LaTeX 环境（用于生成 PDF 报告）

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

3. 安装 spaCy 中文语言模型

```bash
# 确保已安装 spaCy
pip install spacy

# 下载中文语言模型
python -m spacy download zh_core_web_sm
```

4. 设置环境变量

```bash
# Windows (PowerShell)
$env:DEEPSEEK_API_KEY="your-api-key-here"

# Windows (CMD)
set DEEPSEEK_API_KEY=your-api-key-here

# Linux/macOS
export DEEPSEEK_API_KEY="your-api-key-here"
```

或者创建 `.env` 文件，内容参考 `.env.example`：

```
DEEPSEEK_API_KEY=your-api-key-here
REDDIT_URL=https://www.reddit.com/r/LocalLLaMA/
POST_CLEANUP_HOURS=168  # 7天=168小时
TEMPERATURE_SUMMARIZER=0.8
TEMPERATURE_TOPIC_EXTRACTOR=0.3
TEMPERATURE_DATA_CLEANER=0.8
```

5. 验证安装

```bash
python verify_setup.py
```

## 🚀 使用方法

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

# 跳过PDF报告生成
python run.py --no-pdf

# 设置Reddit版块URL
python run.py --reddit-url "https://www.reddit.com/r/MachineLearning/"

# 设置过滤时间（小时）
python run.py --hours 168  # 默认一周

# 指定输出目录
python run.py --output-dir "./output"

# 获取帮助
python run.py --help
```

## 📁 项目结构

```
llm_report/
├── llm_report_tool/          # 核心代码包
│   ├── scrapers/             # 爬虫模块
│   │   └── reddit_scraper.py # Reddit爬虫
│   ├── processors/           # 处理器模块
│   │   ├── data_cleaner.py   # 数据清洗
│   │   ├── summarizer.py     # 文本摘要
│   │   ├── topic_extractor.py # 主题抽取与分类
│   │   └── latex_report_generator.py # PDF报告生成
│   ├── utils/                # 工具模块
│   │   └── config.py         # 配置管理
│   └── main.py               # 主程序入口
├── data/                     # 数据存储目录
├── drivers/                  # WebDriver驱动程序目录
├── tests/                    # 测试代码
├── run.py                    # 启动脚本
├── verify_setup.py           # 环境验证脚本
├── requirements.txt          # 项目依赖
├── .env.example              # 环境变量示例
└── README.md                 # 项目说明
```

## ⚙️ 配置选项

你可以创建一个 `config.json` 文件来自定义配置：

```json
{
  "reddit_url": "https://www.reddit.com/r/LocalLLaMA/",
  "post_cleanup_hours": 168,
  "summary_batch_size": {
    "min": 5,
    "max": 10
  },
  "report_title": "LLM技术日报",
  "report_prefix": "llm-news-daily",
  "temperature": {
    "summarizer": 0.8,
    "topic_extractor": 0.3,
    "data_cleaner": 0.8
  }
}
```

### Temperature 参数说明

本项目中使用了三个不同的 temperature 参数，分别针对不同的处理模块：

- **summarizer (0.8)**: 摘要生成使用较高的 temperature，使文本更加流畅自然，富有表现力。
- **topic_extractor (0.8)**: 主题提取使用适中的 temperature，平衡主题分类的创造性和准确性。
- **data_cleaner (0.8)**: 内容质量分析使用适中的 temperature，提供平衡的质量评分。

所有模块现在统一使用 0.8 的 temperature 值，确保输出结果既有创造性又保持一致性。

## 📊 输出示例

生成的 PDF 报告将保存在 `llm_report_tool/reports/` 目录（或指定的输出目录）中：

- PDF 文档: `YYYY-MM-DD-llm-news-daily.pdf`

## 💡 常见问题

<details>
<summary><b>爬虫无法工作？</b></summary>
<p>
确保已安装最新版 Chrome 浏览器，且 webdriver-manager 能正确下载匹配的驱动。如遇到 ChromeDriver 版本不匹配问题，请尝试以下解决方案：

1. 手动下载匹配版本的 ChromeDriver 并放置在 `drivers` 目录中
2. 降级 Chrome 浏览器版本以匹配可用的 ChromeDriver
3. 设置环境变量跳过爬虫阶段：`python run.py --skip-scrape`
4. 在 Windows 系统下，如果遇到 "不是有效的 Win32 应用程序" 错误，尝试使用 WebDriver Manager 3.8.3 版本

```bash
pip install webdriver-manager==3.8.3
```

</p>
</details>

<details>
<summary><b>API 密钥错误？</b></summary>
<p>
检查是否正确设置了 `DEEPSEEK_API_KEY` 环境变量。可以在命令行中检查环境变量：

```bash
# Windows PowerShell
echo $env:DEEPSEEK_API_KEY

# Linux/macOS
echo $DEEPSEEK_API_KEY
```

如果输出为空，说明环境变量未设置。请参考安装步骤中的说明重新设置。

</p>
</details>

<details>
<summary><b>LaTeX PDF 生成失败？</b></summary>
<p>
确保已安装完整的 LaTeX 环境，包括必要的中文字体和 ctex 包。

对于 Windows 用户，推荐安装 TeXLive 或 MiKTeX。安装后，请确保安装了中文支持包，可通过 TeXLive 或 MiKTeX 的包管理器安装。

对于 Linux 用户：

```bash
sudo apt-get install texlive-full
```

对于 macOS 用户：

```bash
brew install --cask mactex
```

</p>
</details>

<details>
<summary><b>如何自定义报告格式？</b></summary>
<p>
修改 `llm_report_tool/processors/latex_report_generator.py` 文件，自定义报告的标题、章节结构、样式和排版等元素。
</p>
</details>

## 🔄 最新更新

- 移除 Word 报告生成功能，专注于 PDF 格式报告
- 使用 DeepSeek API 替代 Gemini API，提升摘要生成质量
- 增加全局温度参数配置，可针对不同模块单独设置 temperature
- 彻底改为日报，获取最近一天的所有相关新闻
- 增加分页获取功能，无限制获取一天内所有帖子
- 增强数据清洗功能，使用更严格的质量过滤机制
- 优化过滤逻辑，移除无关内容检测，专注于内容质量
- 增强 WebDriver 兼容性，添加多种备用方法
- 添加基于 API 的备用爬取方式，减少对 Selenium 的依赖
- 类型系统增强，修复各类型安全问题
- 添加主题抽取与分类功能，自动分析摘要内容
- 优化摘要长度控制，保持每篇在 300-400 字
- 修复 PDF 报告生成中的路径问题

## 🤝 贡献指南

欢迎提交 Pull Request 或 Issue！贡献前请参考以下步骤：

1. Fork 该仓库
2. 创建新分支：`git checkout -b feature/your-feature`
3. 提交您的更改：`git commit -am 'Add some feature'`
4. 推送到远程分支：`git push origin feature/your-feature`
5. 提交 Pull Request

## 🙏 致谢

本项目的开发离不开以下开源项目和服务的支持：

- [DeepSeek API](https://deepseek.com/) - 提供强大的文本生成和处理能力
- [NLTK](https://www.nltk.org/) - 自然语言处理工具包
- [scikit-learn](https://scikit-learn.org/) - 机器学习库，用于主题建模
- [Selenium](https://www.selenium.dev/) - 网页自动化工具
- [pandas](https://pandas.pydata.org/) - 数据处理库
- [PyLaTeX](https://github.com/JelteF/PyLaTeX) - Python LaTeX 文档生成
- [Reddit](https://www.reddit.com/) - 提供内容来源

特别感谢所有贡献者和提供反馈的用户，你们的支持是项目持续改进的动力。

## ⚠️ 免责声明

1. **内容合规性**：本工具仅用于技术学习与研究。用户应遵守相关法律法规，不得用于任何违法用途。使用过程中产生的任何法律责任由用户自行承担。

2. **数据来源**：本工具爬取的内容来自 Reddit 等公开平台，不保证内容的准确性、完整性或适用性。使用者应自行判断所获取信息的真实性和价值。

3. **版权声明**：使用本工具生成的报告可能包含来自第三方的内容。使用者应尊重原始内容的版权，在传播和使用时遵守相关版权法规。

4. **API 使用**：本工具依赖 DeepSeek 等第三方 API 服务。使用者需自行获取合法的 API 密钥，并遵守相关服务提供商的使用条款。

5. **免责声明**：开发者不对使用本工具产生的任何直接或间接损失负责，包括但不限于数据丢失、系统损坏或业务中断。

6. **隐私保护**：本工具不会收集用户个人信息。但用户在使用过程中可能向第三方 API 传输数据，请注意保护个人隐私。

使用本工具即表示您已阅读并同意上述免责声明的全部内容。

## 📄 许可证

[MIT](LICENSE)

---

<p align="center">
  <sub>Made with ❤️ by LLM Report Tool Team</sub>
</p>
