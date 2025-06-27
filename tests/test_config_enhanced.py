"""
Enhanced tests for the configuration module.
"""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from llm_report_tool.utils.config import Config


class TestConfig:
    """Test cases for the Config class."""

    def test_config_initialization(self, temp_dir):
        """Test basic configuration initialization."""
        with patch.object(Config, "__init__", lambda x: None):
            config = Config()
            config.base_dir = temp_dir
            config.data_dir = temp_dir / "data"
            config.reports_dir = temp_dir / "reports"

            assert isinstance(config.base_dir, Path)
            assert isinstance(config.data_dir, Path)
            assert isinstance(config.reports_dir, Path)

    def test_environment_variable_loading(self):
        """Test loading configuration from environment variables."""
        test_env = {
            "REDDIT_URL": "https://www.reddit.com/r/TestSubreddit/",
            "POST_CLEANUP_HOURS": "48",
            "LOG_LEVEL": "DEBUG",
            "STRUCTURED_LOGGING": "true",
        }

        with patch.dict(os.environ, test_env, clear=False):
            config = Config()

            assert config.reddit_url == test_env["REDDIT_URL"]
            assert config.post_cleanup_hours == int(test_env["POST_CLEANUP_HOURS"])
            assert config.log_level == test_env["LOG_LEVEL"]
            assert config.structured_logging is True

    def test_config_file_loading(self, temp_dir):
        """Test loading configuration from JSON file."""
        config_data = {
            "reddit_url": "https://www.reddit.com/r/ConfigTest/",
            "post_cleanup_hours": 72,
            "report_title": "Test Report",
            "temperature": {"summarizer": 0.5, "topic_extractor": 0.7},
        }

        config_file = temp_dir / "config.json"
        with open(config_file, "w") as f:
            json.dump(config_data, f)

        with patch.object(Config, "__init__", lambda x: None):
            config = Config()
            config.base_dir = temp_dir
            config._load_custom_config()

            assert config.reddit_url == config_data["reddit_url"]
            assert config.post_cleanup_hours == config_data["post_cleanup_hours"]
            assert config.report_title == config_data["report_title"]
            assert config.temperature_summarizer == config_data["temperature"]["summarizer"]

    def test_directory_creation(self, temp_dir):
        """Test that required directories are created."""
        with patch.object(Config, "__init__", lambda x: None):
            config = Config()
            config.base_dir = temp_dir
            config.data_dir = temp_dir / "data"
            config.reports_dir = temp_dir / "reports"

            # Simulate directory creation
            config.data_dir.mkdir(exist_ok=True)
            config.reports_dir.mkdir(exist_ok=True)

            assert config.data_dir.exists()
            assert config.reports_dir.exists()

    def test_debug_mode_setting(self):
        """Test debug mode configuration."""
        with patch.dict(os.environ, {"DEBUG": "true"}, clear=False):
            config = Config()
            assert config.debug is True
            assert config.log_level == "DEBUG"

    def test_missing_api_key_warning(self, caplog):
        """Test warning when API key is missing."""
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
            assert "未找到SILICONFLOW_API_KEY环境变量" in caplog.text

    def test_invalid_config_file_handling(self, temp_dir, caplog):
        """Test handling of invalid configuration files."""
        config_file = temp_dir / "config.json"
        with open(config_file, "w") as f:
            f.write("invalid json content")

        with patch.object(Config, "__init__", lambda x: None):
            config = Config()
            config.base_dir = temp_dir
            config._load_custom_config()

            assert "加载配置文件出错" in caplog.text
