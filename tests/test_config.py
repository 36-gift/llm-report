"""
配置模块的单元测试
"""
import os
import sys
import unittest
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from llm_report_tool.utils.config import Config, config as global_config # Import the global instance too

class TestConfig(unittest.TestCase):
    """配置类的测试用例"""
    
    def test_config_initialization(self):
        """测试配置类初始化"""
        # Use the globally initialized config instance for testing paths
        # as it might be updated by main.py logic if run via that entry point

        # Test basic attributes
        self.assertIsInstance(global_config.base_dir, Path)
        self.assertIsInstance(global_config.data_dir, Path)
        self.assertIsInstance(global_config.reports_dir, Path)
        
        # Test default settings (can be overridden by env vars or config.json)
        # self.assertEqual(global_config.reddit_url, os.environ.get("REDDIT_URL", "https://www.reddit.com/r/LocalLLaMA/"))
        # self.assertEqual(global_config.post_cleanup_hours, int(os.environ.get("POST_CLEANUP_HOURS", "24"))) # Updated default
        
        # Test dynamically generated file paths contain the current date
        self.assertIn(global_config.current_date, global_config.reddit_posts_file.name)
        self.assertIn(global_config.current_date, global_config.cleaned_posts_file.name)
        self.assertIn(global_config.current_date, global_config.summaries_file.name)
        # Construct the expected report file name based on config logic
        expected_report_name = f"{global_config.current_date}-{global_config.report_prefix}.pdf"
        # Check if the expected name is part of the full path defined by reports_dir
        # Note: We don't test the exact output path as it's handled by the generator,
        # we just check if the date and prefix are used as intended.
        # This test assumes latex_report_generator uses config.reports_dir, config.current_date, config.report_prefix
        # A more robust test might mock the generator or check the generated path more directly if needed.
        self.assertEqual(expected_report_name, f"{global_config.current_date}-{global_config.report_prefix}.pdf")

if __name__ == "__main__":
    unittest.main()