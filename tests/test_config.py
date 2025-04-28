"""
配置模块的单元测试
"""
import os
import sys
import unittest
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from llm_report_tool.utils.config import Config

class TestConfig(unittest.TestCase):
    """配置类的测试用例"""
    
    def test_config_initialization(self):
        """测试配置类初始化"""
        config = Config()
        
        # 测试基本属性
        self.assertIsInstance(config.base_dir, Path)
        self.assertIsInstance(config.data_dir, Path)
        self.assertIsInstance(config.reports_dir, Path)
        
        # 测试默认设置
        self.assertEqual(config.reddit_url, os.environ.get("REDDIT_URL", "https://www.reddit.com/r/LocalLLaMA/"))
        self.assertEqual(config.post_cleanup_hours, int(os.environ.get("POST_CLEANUP_HOURS", "48")))
        
        # 测试文件路径格式
        self.assertIn(config.current_date, config.reddit_posts_file.name)
        self.assertIn(config.current_date, config.cleaned_posts_file.name)
        self.assertIn(config.current_date, config.summaries_file.name)
        self.assertIn(config.current_date, config.report_file.name)

if __name__ == "__main__":
    unittest.main()