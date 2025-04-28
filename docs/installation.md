# 安装与设置指南

本文档提供了详细的安装步骤和环境配置指南。

## 系统要求

- Python 3.10 或更高版本
- Chrome 浏览器（用于 Selenium 爬虫）
- 网络连接（用于爬取 Reddit 和调用 Gemini API）
- Google Gemini API 密钥

## 详细安装步骤

### 1. Python 环境设置

首先，确保你已经安装了 Python 3.10 或更高版本：

```bash
python --version
```

推荐使用虚拟环境隔离项目依赖：

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境（Windows）
venv\Scripts\activate

# 激活虚拟环境（Linux/macOS）
source venv/bin/activate
```

### 2. 获取项目代码

克隆或下载本项目：

```bash
git clone https://github.com/36-gift/llm_report.git
cd llm_report
```

### 3. 安装依赖

安装所有必需的 Python 包：

```bash
pip install -r requirements.txt
```

### 4. Chrome 浏览器和 WebDriver

确保已安装最新版的 Chrome 浏览器。WebDriver 会由程序自动下载和管理。

### 5. 配置密钥和设置

1. 复制环境变量示例文件：

   ```bash
   copy .env.example .env
   ```

2. 编辑`.env`文件，添加你的 Gemini API 密钥：

   ```
   GEMINI_API_KEY=your_api_key_here
   ```

3. (可选) 复制配置文件示例：

   ```bash
   copy config.json.example config.json
   ```

4. 根据需要编辑`config.json`文件。

### 6. 验证安装

运行验证脚本以确认所有组件都已正确安装：

```bash
python verify_setup.py
```

如果一切正常，你应该看到确认信息。

## 故障排除

### 浏览器驱动问题

如果遇到 Chrome 驱动相关错误，尝试手动下载与你的 Chrome 版本匹配的驱动：

1. 访问 https://chromedriver.chromium.org/downloads
2. 下载与你 Chrome 版本匹配的驱动
3. 将驱动放在项目根目录或添加到系统 PATH 中

### API 密钥问题

确保你已经:

1. 在 https://aistudio.google.com/ 注册并获取了有效的 API 密钥
2. 正确设置了环境变量
3. 检查 API 密钥的使用配额和权限

## 云端部署

如需在服务器上部署，需要一些额外步骤：

### Linux 服务器上的无头 Chrome

在无 GUI 的 Linux 环境中，需要安装以下依赖：

```bash
sudo apt update
sudo apt install -y chromium-browser xvfb
```

并确保添加以下 Chrome 选项：

```python
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
```

### Docker 部署

项目目前不包含 Docker 配置，如有需要，可以参考以下 Dockerfile 模板：

```dockerfile
FROM python:3.10-slim

# 安装Chrome和其他依赖
RUN apt-get update && apt-get install -y \
    chromium \
    wget \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制项目文件
COPY . .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 设置环境变量
ENV PYTHONPATH=/app

# 入口命令
ENTRYPOINT ["python", "run.py"]
```
