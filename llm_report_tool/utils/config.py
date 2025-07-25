"""
Configuration management module for unified project configuration.
Supports loading configuration from environment variables and configuration files.
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# 首先尝试加载.env文件
load_dotenv()

# Import logging setup (will be configured later)
import logging

logger = logging.getLogger("llm_report")


class Config:
    """Configuration management class responsible for loading and managing project configuration."""

    def __init__(self) -> None:
        self.base_dir = Path(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        )
        self.data_dir = self.base_dir / "data"
        self.reports_dir = self.base_dir / "reports"

        # 确保目录存在
        self.data_dir.mkdir(exist_ok=True)
        self.reports_dir.mkdir(exist_ok=True)

        # 动态生成基于日期的文件名
        self.current_date = datetime.now().strftime("%Y-%m-%d")
        self.reddit_posts_file = self.data_dir / f"reddit_posts_{self.current_date}.xlsx"
        self.cleaned_posts_file = self.data_dir / f"cleaned_reddit_posts_{self.current_date}.xlsx"
        self.summaries_file = self.data_dir / f"summaries_{self.current_date}.txt"

        # 加载API密钥
        self.deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not self.deepseek_api_key:
            logger.warning("未找到DEEPSEEK_API_KEY环境变量，某些功能可能无法正常工作")

        # 日志配置
        self.log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
        self.log_to_file = os.environ.get("LOG_TO_FILE", "true").lower() in ("true", "t", "1")
        self.log_to_console = os.environ.get("LOG_TO_CONSOLE", "true").lower() in ("true", "t", "1")
        self.structured_logging = os.environ.get("STRUCTURED_LOGGING", "false").lower() in (
            "true",
            "t",
            "1",
        )

        # 从环境变量设置调试模式（向后兼容）
        self.debug = os.environ.get("DEBUG", "").lower() in ("true", "t", "1")
        if self.debug:
            self.log_level = "DEBUG"

        # 可配置参数
        self.reddit_url = os.environ.get("REDDIT_URL", "https://www.reddit.com/r/LocalLLaMA/")
        self.post_cleanup_hours = int(os.environ.get("POST_CLEANUP_HOURS", "24"))  # 默认1天(24小时)
        self.summary_batch_size_min = int(os.environ.get("SUMMARY_BATCH_MIN", "5"))
        self.summary_batch_size_max = int(os.environ.get("SUMMARY_BATCH_MAX", "10"))

        # LLM模型相关参数
        self.temperature_summarizer = float(os.environ.get("TEMPERATURE_SUMMARIZER", "0.6"))
        self.temperature_topic_extractor = float(
            os.environ.get("TEMPERATURE_TOPIC_EXTRACTOR", "0.8")
        )
        self.temperature_data_cleaner = float(os.environ.get("TEMPERATURE_DATA_CLEANER", "0.8"))

        # 报告相关配置
        self.report_title = "LLM技术日报"
        self.report_prefix = "llm-news-daily"

        # 尝试加载自定义配置文件
        self._load_custom_config()

    def _load_custom_config(self) -> None:
        """Load custom configuration from configuration file."""
        config_file = self.base_dir / "config.json"
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    custom_config = json.load(f)

                # 更新配置
                if "reddit_url" in custom_config:
                    self.reddit_url = custom_config["reddit_url"]
                if "post_cleanup_hours" in custom_config:
                    self.post_cleanup_hours = custom_config["post_cleanup_hours"]
                if "summary_batch_size" in custom_config:
                    self.summary_batch_size_min = custom_config["summary_batch_size"]["min"]
                    self.summary_batch_size_max = custom_config["summary_batch_size"]["max"]
                if "report_title" in custom_config:
                    self.report_title = custom_config["report_title"]
                if "report_prefix" in custom_config:
                    self.report_prefix = custom_config["report_prefix"]

                # 加载LLM模型相关参数
                if "temperature" in custom_config:
                    if "summarizer" in custom_config["temperature"]:
                        self.temperature_summarizer = custom_config["temperature"]["summarizer"]
                    if "topic_extractor" in custom_config["temperature"]:
                        self.temperature_topic_extractor = custom_config["temperature"][
                            "topic_extractor"
                        ]
                    if "data_cleaner" in custom_config["temperature"]:
                        self.temperature_data_cleaner = custom_config["temperature"]["data_cleaner"]

                logger.info(f"已从{config_file}加载自定义配置")
            except Exception as e:
                logger.error(f"加载配置文件出错: {e}")


# 全局配置实例
config = Config()
