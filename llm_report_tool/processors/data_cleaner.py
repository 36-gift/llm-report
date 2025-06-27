"""
数据清洗模块，负责对爬取的原始数据进行API内容质量分析
"""
import json
import random
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union

import pandas as pd
import requests

from ..utils.config import config, logger


class DataCleaner:
    """数据清洗类，只进行API内容质量分析，不删除数据"""

    def __init__(
        self,
        input_file: Optional[Union[str, Path]] = None,
        output_file: Optional[Union[str, Path]] = None,
        api_key: Optional[str] = None,
    ):
        """
        初始化数据清洗器

        Args:
            input_file: 输入文件路径，默认使用配置文件中的路径
            output_file: 输出文件路径，默认使用配置文件中的路径
            api_key: SiliconFlow API密钥，默认从配置中获取
        """
        self.input_file = Path(input_file) if input_file else config.reddit_posts_file
        self.output_file = Path(output_file) if output_file else config.cleaned_posts_file
        self.api_key = api_key or config.deepseek_api_key
        self.base_url = "https://api.deepseek.com"

        # 初始化API相关配置
        self.api_available = False
        if self.api_key and self.api_key != "your_deepseek_api_key_here":
            self._setup_api_config()
            self.api_available = True
        else:
            logger.warning("API密钥未设置或为占位符，将使用基于规则的质量评分")

    def _setup_api_config(self) -> None:
        """初始化SiliconFlow API配置"""
        # 设置API头信息
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        # 使用DeepSeek模型进行质量评分
        self.model_name = "deepseek-chat"

    def _rule_based_quality_score(self, content: str) -> float:
        """
        基于规则的内容质量评分（当API不可用时使用）

        Args:
            content: 文本内容

        Returns:
            质量分数，0-1之间的浮点数
        """
        if not content or len(content.strip()) < 20:
            return 0.1

        # 基本质量指标
        score = 0.5  # 基础分数

        # 长度评分 (更长的内容通常更有价值)
        if len(content) > 100:
            score += 0.1
        if len(content) > 300:
            score += 0.1

        # LLM相关关键词评分
        llm_keywords = [
            "llm",
            "language model",
            "gpt",
            "claude",
            "deepseek",
            "anthropic",
            "openai",
            "machine learning",
            "ai",
            "artificial intelligence",
            "transformer",
            "bert",
            "neural network",
            "training",
            "inference",
            "benchmark",
            "evaluation",
            "performance",
            "reasoning",
            "chatbot",
            "fine-tuning",
            "prompt",
            "embeddings",
            "tokenizer",
            "model",
            "llama",
            "mistral",
            "gemini",
            "palm",
            "bard",
        ]

        content_lower = content.lower()
        keyword_count = sum(1 for keyword in llm_keywords if keyword in content_lower)

        if keyword_count >= 3:
            score += 0.2
        elif keyword_count >= 1:
            score += 0.1

        # 避免spam内容
        if content.count("http") > 3:  # 太多链接可能是spam
            score -= 0.1
        if len(content.split()) < 10:  # 太短的内容
            score -= 0.1

        return max(0.0, min(1.0, score))

    def _make_api_call_with_retry(self, prompt: str, max_retries: int = 10) -> Optional[float]:
        """
        Make API call with robust retry mechanism.

        Args:
            prompt: The prompt to send to the API
            max_retries: Maximum number of retry attempts

        Returns:
            Quality score from API, or None if all retries failed
        """
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    # Exponential backoff with jitter
                    base_delay = 2 ** min(attempt - 1, 6)  # Cap at 64 seconds
                    jitter = random.uniform(0.5, 1.5)
                    delay = base_delay * jitter
                    logger.info(f"API重试第 {attempt + 1}/{max_retries} 次，等待 {delay:.1f} 秒...")
                    time.sleep(delay)

                # Make the API call
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json={
                        "model": self.model_name,
                        "messages": [
                            {
                                "role": "system",
                                "content": "你是一个内容质量评估专家，精通AI和机器学习领域。"
                                "你的任务是评估文本内容的质量和相关性。请宽松评分，允许更多样化的内容。",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": config.temperature_data_cleaner,
                        "max_tokens": 10,
                    },
                    timeout=30,
                )

                # Check response status
                response.raise_for_status()
                response_data = response.json()

                if "choices" in response_data and len(response_data["choices"]) > 0:
                    # Parse the response
                    try:
                        raw_score = response_data["choices"][0]["message"]["content"].strip()
                        # Extract number
                        match = re.search(r"(\d+(\.\d+)?)", raw_score)
                        if match:
                            score = float(match.group(1))
                            # Ensure score is in 0-1 range
                            score = max(0.0, min(score, 1.0))
                            if attempt > 0:
                                logger.info(f"✅ API调用成功 (第{attempt + 1}次尝试)")
                            return score
                        else:
                            logger.warning(f"无法从API响应中提取分数: {raw_score}")
                            if attempt == 0:  # Only log this on first attempt
                                logger.warning("将在后续重试中继续尝试...")
                            continue
                    except (json.JSONDecodeError, KeyError, ValueError) as parse_error:
                        logger.warning(f"解析API响应时出错: {parse_error}")
                        if attempt == 0:
                            logger.warning("将在后续重试中继续尝试...")
                        continue
                else:
                    logger.warning("API返回了无效响应格式")
                    continue

            except requests.exceptions.Timeout:
                logger.warning(f"API调用超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt == max_retries - 1:
                    logger.error("已达到最大重试次数，API调用超时")
                continue

            except requests.exceptions.ConnectionError:
                logger.warning(f"网络连接错误 (尝试 {attempt + 1}/{max_retries})")
                if attempt == max_retries - 1:
                    logger.error("已达到最大重试次数，网络连接失败")
                continue

            except requests.exceptions.HTTPError as http_err:
                status_code = http_err.response.status_code if http_err.response else "unknown"
                logger.error(f"HTTP错误 {status_code} (尝试 {attempt + 1}/{max_retries}): {http_err}")

                # Don't retry on authentication errors (4xx)
                if http_err.response and 400 <= http_err.response.status_code < 500:
                    logger.error("认证或客户端错误，停止重试")
                    break

                if attempt == max_retries - 1:
                    logger.error("已达到最大重试次数，HTTP错误持续")
                continue

            except Exception as e:
                logger.error(f"API调用出现未知错误 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    logger.error("已达到最大重试次数，未知错误持续")
                continue

        # All retries failed
        logger.error(f"API调用失败，已重试 {max_retries} 次，将使用基于规则的评分作为备选方案")
        return None

    def _analyze_content_quality(self, content: str) -> float:
        """
        使用API分析内容质量并返回分数

        Args:
            content: 文本内容

        Returns:
            质量分数，0-1之间的浮点数
        """
        # 如果API不可用，使用基于规则的评分
        if not self.api_available:
            return self._rule_based_quality_score(content)

        # 构建提示词
        prompt = f"""请分析以下Reddit帖子的质量，考虑以下因素：
        - 内容相关性（与AI、机器学习、深度学习、LLM、语言模型相关）
        - 信息密度
        - 技术深度
        - 内容有用性
        - 写作质量

        文本：
        {content}

        仅返回0到1之间的质量分数，不需要解释。分数含义：
        - 0-0.3：低质量或不相关
        - 0.3-0.6：一般质量或部分相关
        - 0.6-1.0：高质量且相关
        """

        # 使用带重试机制的API调用
        api_score = self._make_api_call_with_retry(prompt, max_retries=10)

        if api_score is not None:
            return api_score
        else:
            # 所有API重试都失败，使用基于规则的评分作为最终备选方案
            logger.info("所有API重试失败，使用基于规则的评分作为最终备选方案")
            return self._rule_based_quality_score(content)

    def analyze_data(self) -> pd.DataFrame:
        """
        分析数据质量，添加质量分数，并清洗真正空白的内容

        Returns:
            带有质量分数的DataFrame，已清洗空白内容
        """
        logger.info(f"开始分析数据质量，从文件 {self.input_file} 读取...")

        try:
            df = pd.read_excel(self.input_file)
            record_count = len(df)
            logger.info(f"数据包含 {record_count} 条记录")

            # 检查数据格式和内容
            logger.info(f"数据列：{', '.join(df.columns)}")

            # 清洗真正空白的内容 (只检查 post_content)
            if "post_content" in df.columns:
                empty_text_mask = (
                    df["post_content"].isna()
                    | (df["post_content"] == "")
                    | (df["post_content"] == "内容未找到")
                )

                if empty_text_mask.any():
                    empty_count = empty_text_mask.sum()
                    logger.info(f"发现 {empty_count} 条空白内容（无有效文字），将被移除")
                    df = df[~empty_text_mask]
                    logger.info(f"清洗后保留 {len(df)} 条记录")

            # 创建一个新的quality_score列
            df["quality_score"] = 0.0

            # 进行内容质量评分
            logger.info("开始对内容进行质量评分...")
            for i, (idx, row) in enumerate(df.iterrows()):
                content = row["post_content"]

                try:
                    score = self._analyze_content_quality(content)
                    df.at[idx, "quality_score"] = score
                    logger.info(f"内容 {i+1}/{len(df)} 质量分数: {score:.2f}")
                except Exception as e:
                    logger.error(f"分析内容质量时出错: {str(e)}")
                    # 出错时给予中等分数
                    df.at[idx, "quality_score"] = 0.5

            # 根据质量分数筛选数据
            initial_count = len(df)
            # 使用较低的阈值以保留更多内容
            quality_threshold = 0.4 if not self.api_available else 0.50
            df = df[df["quality_score"] >= quality_threshold]
            filtered_count = len(df)
            removed_count = initial_count - filtered_count
            logger.info(
                f"质量评分完成。根据阈值 {quality_threshold} 进行筛选，保留 {filtered_count} 条记录，移除了 {removed_count} 条记录。"
            )

            # 保存筛选后的数据
            df.to_excel(self.output_file, index=False)
            logger.info(f"已将筛选后的高质量数据保存到 {self.output_file}")

            return df

        except Exception as e:
            logger.error(f"分析数据时出错: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return pd.DataFrame()


def run(input_file: Optional[str] = None, output_file: Optional[str] = None) -> bool:
    """
    执行数据质量分析的主函数

    Args:
        input_file: 可选的输入文件路径
        output_file: 可选的输出文件路径

    Returns:
        是否成功分析数据质量
    """
    try:
        cleaner = DataCleaner(input_file, output_file)
        df = cleaner.analyze_data()
        return not df.empty  # 只要成功分析数据就返回True
    except Exception as e:
        logger.error(f"运行数据分析器时出错: {e}")
        return False


if __name__ == "__main__":
    run()
