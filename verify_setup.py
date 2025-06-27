#!/usr/bin/env python
"""
环境设置验证工具
用于检查所有必要组件是否正确安装和配置
"""
import importlib
import logging
import os
import platform
import sys
from pathlib import Path

from dotenv import load_dotenv

# 初始化日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("verify_setup")


# 检查Python版本
def check_python_version():
    logger.info(f"检查Python版本...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        logger.error(f"❌ Python版本过低: {sys.version}")
        logger.error(f"   需要Python 3.10或更高版本")
        return False
    else:
        logger.info(f"✅ Python版本符合要求: {sys.version}")
        return True


# 检查必要的库
def check_required_packages():
    logger.info("检查必要的Python库...")
    required_packages = [
        "requests",
        "beautifulsoup4",
        "selenium",
        "webdriver_manager",
        "pandas",
        "openpyxl",
        "tqdm",
        "python-dotenv",
        "pylatex",
    ]

    all_installed = True
    # Map installation names to actual import names where they differ
    import_map = {"beautifulsoup4": "bs4", "python-docx": "docx", "python-dotenv": "dotenv"}
    for package in required_packages:
        import_name = import_map.get(package, package)  # Use mapped name or original if not mapped
        try:
            # 处理子模块的情况 (use import_name for check)
            if "." in import_name:
                main_package = import_name.split(".")[0]
                importlib.import_module(main_package)
            else:
                importlib.import_module(import_name)
            logger.info(f"✅ {package} 已正确安装")  # Log the original package name
        except ImportError:
            logger.error(f"❌ {package} 未安装或无法导入")
            all_installed = False

    return all_installed


# 检查API密钥
def check_api_key():
    logger.info("检查API密钥配置...")
    load_dotenv()

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        logger.error("❌ 未找到DEEPSEEK_API_KEY环境变量")
        logger.error("   请设置环境变量或创建.env文件")
        return False
    else:
        if api_key == "your_deepseek_api_key_here":
            logger.warning("⚠️ 检测到示例API密钥，请替换为真实的密钥")
            return False
        logger.info("✅ 已找到DEEPSEEK_API_KEY环境变量")
        return True


# 检查必要的文件和目录
def check_project_structure():
    logger.info("检查项目结构...")
    base_dir = Path(__file__).parent

    # 检查必要的文件和目录
    required_paths = [
        base_dir / "llm_report_tool" / "main.py",
        base_dir / "llm_report_tool" / "scrapers" / "reddit_scraper.py",
        base_dir / "llm_report_tool" / "processors" / "data_cleaner.py",
        base_dir / "llm_report_tool" / "processors" / "summarizer.py",
        base_dir / "pyproject.toml",  # Poetry 配置文件
        base_dir / "main.py",
    ]

    all_exists = True
    for path in required_paths:
        if path.exists():
            logger.info(f"✅ 找到 {path.relative_to(base_dir)}")
        else:
            logger.error(f"❌ 未找到 {path.relative_to(base_dir)}")
            all_exists = False

    # 确保目录存在
    for directory in ["data", "llm_report_tool/reports"]:
        dir_path = base_dir / directory
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"✅ 已创建目录 {directory}")

    return all_exists


# 检查Chrome浏览器
def check_chrome_browser():
    logger.info("检查Chrome浏览器...")

    # 根据操作系统检查Chrome是否安装
    system = platform.system()
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        # 尝试创建一个Chrome实例
        options = Options()
        options.add_argument("--headless")  # 无头模式
        options.add_argument("--log-level=3")  # 静默模式

        try:
            from selenium.webdriver.chrome.service import Service
            from webdriver_manager.chrome import ChromeDriverManager

            service = Service(ChromeDriverManager().install())
            browser = webdriver.Chrome(service=service, options=options)
            version = browser.capabilities["browserVersion"]
            browser.quit()

            logger.info(f"✅ 成功检测到Chrome浏览器, 版本: {version}")
            return True
        except Exception as e:
            logger.error(f"❌ 未能启动Chrome浏览器: {e}")
            if system == "Linux":
                logger.error("   在Linux系统上，你可能需要安装chromium-browser")
            return False
    except ImportError:
        logger.error("❌ 未能导入selenium或webdriver相关模块")
        return False


def main():
    logger.info("-" * 50)
    logger.info("开始验证LLM新闻日报工具的环境设置")
    logger.info("-" * 50)

    checks = [
        ("Python版本", check_python_version()),
        ("必要库安装", check_required_packages()),
        ("API密钥配置", check_api_key()),
        ("项目结构", check_project_structure()),
        ("Chrome浏览器", check_chrome_browser()),
    ]

    logger.info("-" * 50)
    logger.info("验证结果汇总:")

    all_passed = True
    for name, result in checks:
        status = "✅ 通过" if result else "❌ 失败"
        logger.info(f"{name}: {status}")
        if not result:
            all_passed = False

    logger.info("-" * 50)
    if all_passed:
        logger.info("🎉 恭喜！所有必要组件已正确安装和配置")
        logger.info("你可以通过运行 'python main.py' 来开始使用该工具")
    else:
        logger.error("⚠️ 存在一些问题需要解决")
        logger.error("请查看上面的错误信息并解决相关问题后再次运行此脚本")
        logger.error("更多帮助信息请参考 docs/installation.md")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
