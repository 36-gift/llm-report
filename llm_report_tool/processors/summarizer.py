"""
Text summarization module that uses SiliconFlow API to generate summaries from cleaned data.
"""
import argparse
import json
import os
import random
import re
import time
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Union

import pandas as pd
import requests

from ..exceptions import APIError
from ..utils.config import config, logger


class TextSummarizer:
    """Text summarization class that uses DeepSeek API to generate summaries."""

    def __init__(
        self,
        input_file: Optional[Union[str, Path]] = None,
        output_file: Optional[Union[str, Path]] = None,
        api_key: Optional[str] = None,
    ):
        """
        初始化总结器

        Args:
            input_file: 输入文件路径，默认使用配置中的路径
            output_file: 输出文件路径，默认使用配置中的路径
            api_key: DeepSeek API密钥，默认从配置中获取
        """
        self.input_file = Path(input_file) if input_file else config.cleaned_posts_file
        self.output_file = Path(output_file) if output_file else config.summaries_file
        self.api_key = api_key or config.deepseek_api_key
        self.batch_size_min = config.summary_batch_size_min
        self.batch_size_max = config.summary_batch_size_max
        self.max_retries = 3  # 合理的重试次数
        self.base_url = "https://api.deepseek.com"  # Official DeepSeek API endpoint

        if not self.api_key:
            raise ValueError("未提供DeepSeek API密钥，请设置环境变量DEEPSEEK_API_KEY或通过参数提供")

        # 不再需要专门的API客户端，使用标准requests

        # API使用统计
        self.request_count = 0
        self.successful_requests = 0
        self.failed_requests = 0

        # API配置 - 使用官方DeepSeek模型
        self.model_name = "deepseek-chat"  # Official DeepSeek model
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        self.generation_config = {
            "temperature": config.temperature_summarizer,
            "max_tokens": 800,  # Sufficient for quality summaries while maintaining efficiency
            "top_p": 0.95,
        }

        logger.info(f"DeepSeek API 已初始化，temperature={config.temperature_summarizer}")

    def test_api_connectivity(self) -> bool:
        """
        Test API connectivity with a simple request

        Returns:
            True if API is accessible, False otherwise
        """
        try:
            logger.info("Testing API connectivity...")

            # Simple test message
            test_data = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 10,
                "temperature": 0.1,
            }

            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=test_data,
                timeout=20,  # Increased timeout based on testing
            )

            if response.status_code == 200:
                logger.info("✅ API connectivity test successful")
                return True
            elif response.status_code == 429:
                logger.warning("⚠️ API rate limit exceeded during connectivity test")
                return False
            elif response.status_code == 401:
                logger.error("❌ API authentication failed - check API key")
                return False
            else:
                logger.error(
                    f"❌ API connectivity test failed with status {response.status_code}: {response.text}"
                )
                return False

        except requests.exceptions.Timeout:
            logger.error("❌ API connectivity test timed out")
            return False
        except requests.exceptions.ConnectionError:
            logger.error("❌ API connectivity test failed - connection error")
            return False
        except Exception as e:
            logger.error(f"❌ API connectivity test failed with error: {e}")
            return False

    def check_rate_limits(self) -> bool:
        """
        Check API usage statistics (DeepSeek has no hard rate limits)

        Returns:
            Always True as DeepSeek doesn't impose strict rate limits
        """
        # DeepSeek API doesn't have strict rate limits, just track usage
        if self.successful_requests > 0 and self.successful_requests % 10 == 0:
            logger.info(f"📊 API使用统计: 成功 {self.successful_requests} 次，失败 {self.failed_requests} 次")

        return True  # DeepSeek allows unlimited requests

    def generate_prompt(self, post: Dict) -> str:
        """
        根据单个帖子生成提示词

        Args:
            post: 单个帖子字典，包含标题、内容和可选的图片URL

        Returns:
            用于生成摘要的提示词
        """
        title = post.get("post_title", "无标题")
        content = post.get("post_content", "无内容").strip()

        # 限制帖子的长度，避免超过token限制
        max_content_length = 1500  # 单个帖子可以适当增加长度
        if len(content) > max_content_length:
            content = content[:max_content_length] + "...(内容已截断)"

        post_details = f"标题：{title}\n内容：{content}"
        prompt_template = """
        请总结以下Reddit LLM相关帖子，要求：
        1. 使用中文，简洁清晰地概括核心信息
        2. 用(1)(2)(3)分点组织
        3. 忠实反映原文核心信息，不遗漏重要细节
        4. 保持技术术语原样

        帖子内容：
        {details}
        """

        return prompt_template.format(details=post_details)

    def _make_api_call_with_retry(
        self, prompt: str, log_identifier: str, max_retries: int = 3
    ) -> Optional[str]:
        """
        带重试机制的API调用

        Args:
            prompt: 提示词
            log_identifier: 用于日志记录的标识符 (例如：帖子索引或标题)

        Returns:
            API响应文本，失败时返回None
        """
        for attempt in range(max_retries):
            try:
                # Track request attempt
                self.request_count += 1
                logger.info(
                    f"📊 API请求计数: 总计 {self.request_count} 次 (成功 {self.successful_requests}, 失败 {self.failed_requests})"
                )

                if attempt > 0:
                    # Simpler backoff strategy for fewer retries
                    base_delay = 2 ** min(attempt - 1, 2)  # Cap at 4 seconds
                    jitter = random.uniform(0.8, 1.2)
                    delay = base_delay * jitter
                    logger.info(
                        f"第 {attempt+1}/{max_retries} 次尝试调用API，针对: {log_identifier}，等待 {delay:.1f} 秒..."
                    )
                    time.sleep(delay)

                # 构建请求数据
                data = {
                    "model": self.model_name,
                    "messages": [
                        {
                            "role": "system",
                            "content": "你是一位专业的文本摘要工具，擅长总结技术内容。请使用中文回复，提供准确、简洁的摘要，确保总结在300-400字之间。",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    **self.generation_config,
                }

                # 调用DeepSeek API
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=data,
                    timeout=30,  # DeepSeek支持长时间处理，最多30分钟
                )

                # 检查响应状态
                response.raise_for_status()
                response_data = response.json()

                if "choices" in response_data and len(response_data["choices"]) > 0:
                    content = response_data["choices"][0]["message"]["content"]
                    self.successful_requests += 1
                    if attempt > 0:
                        logger.info(f"✅ API调用成功 (第{attempt + 1}次尝试) 针对: {log_identifier}")
                    logger.info(f"成功获得API响应，长度：{len(content)} 字符")

                    # 记录总结长度信息（仅用于监控，不限制）
                    char_count = len(content.replace(" ", "").replace("\n", ""))
                    logger.info(f"总结字符数（不含空格和换行）：{char_count}")

                    return content
                else:
                    logger.warning(f"API返回了无效响应: {response_data}")
                    continue

            except requests.exceptions.Timeout:
                logger.warning(f"API调用超时 (尝试 {attempt + 1}/{max_retries}) 针对 {log_identifier}")
                if attempt == max_retries - 1:
                    logger.error(f"已达到最大重试次数，API调用超时，针对: {log_identifier}")
                continue

            except requests.exceptions.ConnectionError:
                logger.warning(f"网络连接错误 (尝试 {attempt + 1}/{max_retries}) 针对 {log_identifier}")
                if attempt == max_retries - 1:
                    logger.error(f"已达到最大重试次数，网络连接失败，针对: {log_identifier}")
                continue

            except requests.exceptions.HTTPError as http_err:
                status_code = http_err.response.status_code if http_err.response else "unknown"

                if status_code == 429:
                    # Rate limit exceeded - DeepSeek has no hard limits but may throttle under load
                    logger.warning(f"⚠️ API请求暂时受限 (429) 针对 {log_identifier}")
                    logger.info("DeepSeek API无严格速率限制，但高峰期可能暂时限流")
                    # Continue retrying for DeepSeek as limits are dynamic
                elif status_code == 401:
                    logger.error(f"❌ API认证失败 (401) 针对 {log_identifier}: 请检查API密钥")
                    return None  # Don't retry on auth errors
                elif status_code == 403:
                    logger.error(f"❌ API访问被拒绝 (403) 针对 {log_identifier}: 权限不足")
                    return None  # Don't retry on permission errors
                else:
                    logger.error(
                        f"HTTP错误 {status_code} (尝试 {attempt + 1}/{max_retries}) 针对 {log_identifier}: {http_err}"
                    )

                    # Don't retry on client errors (4xx except 429)
                    if http_err.response and 400 <= http_err.response.status_code < 500:
                        logger.error(f"客户端错误，停止重试，针对: {log_identifier}")
                        break

                    if attempt == max_retries - 1:
                        logger.error(f"已达到最大重试次数，HTTP错误持续，针对: {log_identifier}")
                continue

            except Exception as e:
                logger.error(
                    f"API调用出现未知错误 (尝试 {attempt + 1}/{max_retries}) 针对 {log_identifier}: {e}"
                )
                logger.debug(traceback.format_exc())
                if attempt == max_retries - 1:
                    logger.error(f"已达到最大重试次数，未知错误持续，针对: {log_identifier}")
                continue

        self.failed_requests += 1
        logger.error(f"达到最大重试次数 {max_retries}，无法获取 {log_identifier} 的响应")
        return None

    def summarize_posts(self) -> bool:
        """
        读取Excel文件，使用DeepSeek API批量处理生成摘要，并保存结果

        Returns:
            是否成功生成摘要
        """
        logger.info(f"开始处理摘要，从文件 {self.input_file} 读取...")

        # Test API connectivity first
        if not self.test_api_connectivity():
            logger.error("API连接测试失败，无法继续处理摘要")
            return False

        try:
            # 检查输入文件是否存在
            if not self.input_file.exists():
                logger.error(f"输入文件不存在: {self.input_file}")
                return False

            df = pd.read_excel(self.input_file)

            if len(df) == 0:
                logger.warning("输入文件不包含任何数据")
                return False

            logger.info(f"读取了 {len(df)} 条记录，开始生成摘要...")

            # 检查必要的列是否存在
            required_columns = ["post_title", "post_content"]
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                logger.error(f"输入数据缺少必要的列: {', '.join(missing_columns)}")
                return False

            # 将DataFrame转换为字典列表，便于处理
            records = df.to_dict("records")

            total_posts = len(records)
            summarized_count = 0
            failed_count = 0

            with open(self.output_file, "w", encoding="utf-8") as f:
                # 先写入文件头部信息
                f.write(f"# LLM 相关新闻日报摘要 ({self.input_file.stem})\n\n")
                f.write(f"基于 {total_posts} 条高质量 Reddit 帖子生成\n\n")

                for i, record in enumerate(records):
                    post_index = i + 1
                    post_title = record.get("post_title", "无标题")
                    post_url = record.get("post_url", "URL_Not_Found")  # 获取 URL
                    log_identifier = f"帖子 {post_index}/{total_posts} ('{post_title[:30]}...')"
                    logger.info(f"正在处理: {log_identifier}")

                    # Check rate limits before processing
                    if not self.check_rate_limits():
                        logger.error("达到速率限制，停止处理")
                        break

                    # 第一个帖子前不加空行，后续帖子前加三个空行以确保两行空白
                    if i > 0:
                        f.write("\n\n\n")  # Write three newlines

                    try:
                        prompt = self.generate_prompt(record)
                        response_text = self._make_api_call_with_retry(prompt, log_identifier)

                        if response_text:
                            # --- Post-processing --- START
                            cleaned_response_text = response_text.strip()
                            # (移除查找链接行的逻辑，因为现在由Python处理)
                            # link_pattern = r'\n*\s*\[原文链接\]\(.*\]\)?'
                            # match = re.search(link_pattern, cleaned_response_text, re.IGNORECASE)
                            # summary_body = cleaned_response_text
                            # link_line = ""
                            # if match:
                            #     link_start_index = match.start()
                            #     summary_body = cleaned_response_text[:link_start_index].rstrip()
                            #     link_line = cleaned_response_text[link_start_index:].strip()

                            # 直接清理整个返回文本中的多余换行
                            cleaned_summary_body = re.sub(
                                r"(\n\s*){2,}", "\n", cleaned_response_text
                            )

                            # (移除重构逻辑)
                            # final_text = cleaned_summary_body
                            # if link_line:
                            #     final_text += "\n" + link_line
                            final_text = cleaned_summary_body  # 清理后的文本即为最终摘要
                            # --- Post-processing --- END

                            # 写入标题 (后面依然是两个换行)
                            f.write(f"## {post_index}. {post_title}\n\n")
                            # 写入清理后的摘要内容
                            f.write(final_text)
                            # 在摘要后写入链接 (前面一个换行)
                            f.write(f"\n[原文链接]({post_url})")

                            f.flush()
                            logger.info(f"✓ 成功生成摘要 for {log_identifier}")
                            summarized_count += 1
                        else:
                            # API 调用失败
                            f.write(f"## {post_index}. {post_title}\n\n")
                            f.write(f"*摘要生成失败*\n\n")
                            f.write(f"\n[原文链接]({post_url})")
                            f.flush()
                            logger.error(f"无法生成摘要 for {log_identifier}")
                            failed_count += 1

                    except Exception as e:
                        # 其他错误
                        logger.error(f"处理 {log_identifier} 时发生意外错误: {e}")
                        logger.debug(traceback.format_exc())
                        f.write(f"## {post_index}. {post_title}\n\n")
                        f.write(f"*处理过程中发生错误，跳过此帖*\n\n")
                        f.write(f"\n[原文链接]({post_url})")
                        f.flush()
                        failed_count += 1
                        continue

                    # Reasonable delay between requests to be respectful to API
                    delay = random.uniform(1, 3)  # Short delay since DeepSeek has no rate limits
                    logger.info(f"⏳ 等待 {delay:.1f} 秒后处理下一个请求")
                    time.sleep(delay)

                # 循环结束后
                logger.info(
                    f"摘要生成完成: 成功 {summarized_count} 篇, 失败 {failed_count} 篇，共处理 {total_posts} 条帖子"
                )
                if summarized_count > 0:
                    return True
                else:
                    logger.error("未能成功生成任何摘要")
                    return False

        except Exception as e:
            logger.error(f"摘要生成失败: {e}")
            logger.error(traceback.format_exc())
            return False


def run(input_file: Optional[str] = None, output_file: Optional[str] = None) -> bool:
    """
    执行摘要生成的主函数

    Args:
        input_file: 可选的输入文件路径
        output_file: 可选的输出文件路径

    Returns:
        是否成功生成摘要
    """
    try:
        summarizer = TextSummarizer(input_file, output_file)
        return summarizer.summarize_posts()
    except Exception as e:
        logger.error(f"摘要生成模块出错: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="运行文本摘要生成器")
    parser.add_argument(
        "--input",
        type=str,
        help="指定输入的 Excel 文件路径 (例如：data/reddit_posts_2024-01-01.xlsx)。如果未指定，则使用 config.cleaned_posts_file",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="指定输出的摘要文件路径 (例如：data/my_summaries.txt)。如果未指定，则使用 config.summaries_file",
    )

    args = parser.parse_args()

    # 使用命令行参数调用 run 函数
    run(input_file=args.input, output_file=args.output)
