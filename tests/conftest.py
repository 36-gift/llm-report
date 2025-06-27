"""
Pytest configuration and fixtures for LLM Report Tool tests.
"""
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Set test environment variables
os.environ["DEEPSEEK_API_KEY"] = "test_key"
os.environ["LOG_LEVEL"] = "DEBUG"
os.environ["LOG_TO_FILE"] = "false"


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def mock_config(temp_dir):
    """Mock configuration for tests."""
    from llm_report_tool.utils.config import Config

    config = Config()
    config.base_dir = temp_dir
    config.data_dir = temp_dir / "data"
    config.reports_dir = temp_dir / "reports"
    config.data_dir.mkdir(exist_ok=True)
    config.reports_dir.mkdir(exist_ok=True)
    config.deepseek_api_key = "test_key"
    config.reddit_url = "https://www.reddit.com/r/LocalLLaMA/"

    return config


@pytest.fixture
def sample_reddit_posts():
    """Sample Reddit post data for testing."""
    return [
        {
            "title": "New LLM model released",
            "content": "This is a sample post about a new language model.",
            "url": "https://www.reddit.com/r/LocalLLaMA/comments/123/test1/",
            "date": "2024-01-15",
            "score": 100,
            "comments": 25,
        },
        {
            "title": "Performance comparison",
            "content": "Comparing different models on various benchmarks.",
            "url": "https://www.reddit.com/r/LocalLLaMA/comments/124/test2/",
            "date": "2024-01-14",
            "score": 85,
            "comments": 15,
        },
    ]


@pytest.fixture
def sample_summaries():
    """Sample summary data for testing."""
    return [
        {
            "title": "New LLM model released",
            "summary": "A new language model was released with improved performance.",
            "url": "https://www.reddit.com/r/LocalLLaMA/comments/123/test1/",
            "category": "model_release",
        },
        {
            "title": "Performance comparison",
            "summary": "Researchers compared different models on benchmarks.",
            "url": "https://www.reddit.com/r/LocalLLaMA/comments/124/test2/",
            "category": "research",
        },
    ]


@pytest.fixture
def mock_deepseek_api():
    """Mock DeepSeek API responses."""
    mock_response = Mock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "This is a test response from the API."}}]
    }
    mock_response.status_code = 200

    with patch("requests.post", return_value=mock_response):
        yield mock_response


@pytest.fixture
def mock_selenium_driver():
    """Mock Selenium WebDriver for testing."""
    mock_driver = Mock()
    mock_driver.page_source = """
    <html>
        <body>
            <article class="w-full m-0">
                <a slot="full-post-link" href="/r/LocalLLaMA/comments/123/test1/">Test Post</a>
                <faceplate-timeago ts="2024-01-15T10:00:00Z"></faceplate-timeago>
            </article>
        </body>
    </html>
    """

    with patch("selenium.webdriver.Chrome", return_value=mock_driver):
        yield mock_driver
