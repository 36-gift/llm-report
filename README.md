# LLM 新闻日报自动生成工具 (Windows 版)

<div align="center">
  <img src="https://img.shields.io/badge/Windows-10%2F11%20支持-blue?logo=windows&logoColor=white" alt="Windows Support">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white" alt="Python Version">
  <img src="https://img.shields.io/badge/DeepSeek-AI%20摘要-orange" alt="DeepSeek AI">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License">
</div>

## 📖 项目概述

LLM 新闻日报自动生成工具是一个专为 **Windows** 用户设计的自动化工具，能够从 Reddit 的 LLM 相关版块自动抓取最新讨论，使用 DeepSeek AI 进行内容分析和摘要生成，最终输出结构化的中文 PDF 日报。

### ✨ 核心功能

- **🤖 智能抓取**: 使用 Selenium + Chrome 自动从 Reddit 抓取 LLM 相关讨论
- **🧹 内容清洗**: 过滤低质量和无关内容，确保报告质量
- **✍️ AI 摘要**: 使用 DeepSeek API 生成准确的中文摘要
- **🏷️ 智能分类**: 自动将内容按主题分类（模型发布、性能评测等）
- **🔥 热点分析**: 识别当日讨论最多的技术热点
- **📄 PDF 报告**: 生成结构化的 PDF 日报

## 🚀 Windows 系统要求

- **Windows 10/11** (x64)
- **Python 3.10+**
- **Google Chrome 浏览器**
- **TeX Live** (用于 PDF 生成)

## 🛠️ 快速安装 (Windows)

### 1. 安装 Python

```powershell
# 从 Microsoft Store 安装 Python (推荐)
# 或下载: https://www.python.org/downloads/windows/

# 验证安装
python --version
pip --version
```

### 2. 安装项目

```bash
# 克隆项目
git clone https://github.com/36-gift/llm-report.git
cd llm-report

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
.\venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 安装 LaTeX (PDF 生成)

```powershell
# 下载并安装 TeX Live
# 访问: https://www.tug.org/texlive/acquire-netinstall.html
# 下载 install-tl-windows.exe 并运行

# 验证安装
xelatex --version
```

> 💡 **LaTeX 安装提示**:
>
> - 选择 `scheme-full` 获得完整功能
> - 安装时间较长 (约 1-2 小时)
> - 确保添加到 PATH 环境变量

### 4. 配置 API 密钥

```bash
# 复制配置文件
copy config.json.example config.json

# 创建环境变量文件
echo DEEPSEEK_API_KEY="your_api_key_here" > .env
```

> 💡 **获取 DeepSeek API 密钥**: 访问 [DeepSeek 官网](https://www.deepseek.com/) 注册并获取免费 API 密钥

### 5. 验证安装

```bash
# 检验环境设置
python verify_setup.py

# 运行演示模式
python main.py --demo
```

## 📊 使用指南

### 🎯 快速开始

```bash
# 激活虚拟环境 (每次使用前)
.\venv\Scripts\activate

# 完整运行流程
python main.py
```

### 📈 分步执行

```bash
# 步骤 1: 数据抓取
python main.py

# 步骤 2: 跳过抓取，从清洗开始
python main.py --skip-scrape

# 步骤 3: 跳过前面步骤，从摘要开始
python main.py --skip-scrape --skip-clean

# 步骤 4: 仅生成分类和报告
python main.py --skip-scrape --skip-clean --skip-summary

# 步骤 5: 仅生成 PDF 报告
python main.py --skip-scrape --skip-clean --skip-summary --skip-topic
```

### ⚙️ 常用参数

```bash
# 详细日志
python main.py --verbose

# 演示模式 (无需 API)
python main.py --demo

# 自定义时间范围
python main.py --hours 48

# 指定 Reddit 源
python main.py --reddit-url "https://www.reddit.com/r/LocalLLaMA"
```

## 📁 项目结构

```
llm-report/
├── main.py                    # 项目入口
├── requirements.txt           # Python 依赖
├── llm_report_tool/          # 核心工具包
│   ├── main.py              # 主工作流控制
│   │   └── reddit_scraper.py
│   ├── processors/          # 数据处理模块
│   │   ├── data_cleaner.py
│   │   ├── summarizer.py
│   │   ├── classifier.py
│   │   └── latex_report_generator.py
│   └── utils/               # 工具模块
│       └── config.py
├── data/                    # 生成的数据文件
├── reports/                 # 输出的 PDF 报告
└── config.json.example      # 配置文件模板
```

## 🔧 Windows 特定说明

### Chrome 浏览器设置

工具会自动下载和管理 Chrome 驱动程序：

- 确保已安装 Google Chrome
- 工具会自动匹配 Chrome 版本
- 无需手动配置驱动路径

### LaTeX 环境配置

```powershell
# 如果遇到中文字体问题
fc-cache -fv

# 验证 XeLaTeX 安装
where xelatex
```

### 常见问题解决

#### Python 路径问题

```powershell
# 如果 python 命令不可用
py --version

# 使用 py 命令替代 python
py main.py
```

#### 权限问题

```powershell
# 以管理员身份运行命令提示符
# 或在 PowerShell 中设置执行策略
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

#### 网络连接问题

```bash
# 如果遇到 SSL 证书问题
pip install --upgrade certifi
```

## 📊 输出文件

运行成功后，您将获得：

### 数据文件 (`data/` 目录)

- `reddit_posts_YYYY-MM-DD.xlsx` - 原始抓取数据
- `cleaned_reddit_posts_YYYY-MM-DD.xlsx` - 清洗后数据
- `summaries_YYYY-MM-DD.txt` - AI 生成摘要
- `classified_summaries_YYYY-MM-DD.json` - 分类结果

### PDF 报告 (`reports/` 目录)

- `YYYY-MM-DD-llm-news-daily.pdf` - 最终日报

## 🔄 更新和维护

```bash
# 更新项目依赖
pip install -r requirements.txt --upgrade

# 更新 Chrome 驱动
# 工具会自动处理，无需手动更新

# 清理临时文件
# Windows + R，输入 %temp%，删除临时目录内容
```

## 🎯 使用技巧

### 提高运行效率

- 使用 `--skip-*` 参数跳过已完成的步骤
- 批处理多天数据时使用 `--classifier-input-file`
- 定期清理 `data/` 目录中的旧文件

### 定时任务设置

```powershell
# 使用 Windows 任务计划程序
# 创建每日自动运行任务
schtasks /create /tn "LLM Daily Report" /tr "C:\path\to\llm-report\run_daily.bat" /sc daily /st 08:00
```

## 📝 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

## 🤝 贡献

欢迎提交 Issues 和 Pull Requests！

---

<div align="center">
  <p><strong>专为 Windows 用户打造的 LLM 新闻自动化工具</strong></p>
  <p>🪟 Windows 10/11 优化 | 🚀 一键式自动化 | �� 结构化报告</p>
</div>
