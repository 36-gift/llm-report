"""
文本总结模块，使用DeepSeek API对清洗后的数据进行摘要生成
"""
import os
import random
import pandas as pd
import time
import traceback
import json
import requests
from typing import Optional, Union, List, Dict
from pathlib import Path
from ..utils.config import config, logger
import argparse
import re

class TextSummarizer:
    """文本总结类，使用DeepSeek API生成摘要"""
    
    def __init__(self, 
                 input_file: Optional[Union[str, Path]] = None,
                 output_file: Optional[Union[str, Path]] = None,
                 api_key: Optional[str] = None):
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
        self.max_retries = 3  # 添加重试次数
        self.base_url = "https://api.deepseek.com/v1"
        
        if not self.api_key:
            raise ValueError("未提供DeepSeek API密钥，请设置环境变量DEEPSEEK_API_KEY或通过参数提供")
        
        # 初始化API配置
        self._setup_api_config()
    
    def _setup_api_config(self) -> None:
        """初始化DeepSeek API配置"""
        try:
            # 生成配置
            self.generation_config = {
                "temperature": config.temperature_summarizer,
                "top_p": 0.95,
                "max_tokens": 4096,
                "stream": False
            }
            
            # 设置API头信息
            self.headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            # 使用deepseek-chat模型
            self.model_name = "deepseek-chat"
            
            logger.info(f"DeepSeek API 已初始化，使用模型：{self.model_name}，temperature={self.generation_config['temperature']}")
        except Exception as e:
            logger.error(f"初始化DeepSeek API时出错: {e}")
            logger.error(traceback.format_exc())
            raise
    
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
        我将提供一些来自Reddit的LLM（大语言模型）相关帖子的内容，请对这些帖子进行总结。

        要求：
        1. 总结必须专注于我提供的这些帖子。
        2. 请直接生成该帖子的总结内容，使用分点（例如：(1), (2)...）或编号列表组织，确保每个分点之间只用一个换行符分隔，不要添加额外的空行。不要在你的回复中包含帖子编号和标题。
        3. 每个帖子总结长度在400-500字之间。
        4. 总结应基于帖子原文，忠实反映其核心信息，不要添加不存在的事件。
        5. 如果内容中有技术术语或专有名词，请保持原样。
        6. 使用简洁清晰的中文表述。
        7. 充分提炼帖子的核心信息点，每个帖子的总结合理分点。

        以下是需要总结的帖子内容：
        
        {details}
        """
        
        return prompt_template.format(details=post_details)
    
    def _make_api_call_with_retry(self, prompt: str, log_identifier: str) -> Optional[str]:
        """
        带重试机制的API调用
        
        Args:
            prompt: 提示词
            log_identifier: 用于日志记录的标识符 (例如：帖子索引或标题)
            
        Returns:
            API响应文本，失败时返回None
        """
        for attempt in range(self.max_retries):
            try:
                # 记录当前尝试次数
                if attempt > 0:
                    logger.info(f"第 {attempt+1}/{self.max_retries} 次尝试调用API，针对: {log_identifier}")
                
                # 构建请求数据
                data = {
                    "model": self.model_name,
                    "messages": [
                        {"role": "system", "content": "你是一位专业的文本摘要工具，擅长总结技术内容。请使用中文回复，提供准确、简洁的摘要，确保总结在300-400字之间。"},
                        {"role": "user", "content": prompt}
                    ],
                    **self.generation_config
                }
                
                # 调用API
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=data,
                    timeout=60  # 设置60秒超时
                )
                
                # 检查响应状态
                response.raise_for_status()
                response_data = response.json()
                
                if "choices" in response_data and len(response_data["choices"]) > 0:
                    content = response_data["choices"][0]["message"]["content"]
                    logger.info(f"成功获得API响应，长度：{len(content)} 字符")
                    
                    # 检查总结长度是否符合要求
                    char_count = len(content.replace(" ", "").replace("\n", ""))
                    logger.info(f"总结字符数（不含空格和换行）：{char_count}")
                    
                    if char_count < 250 or char_count > 500:
                        logger.warning(f"总结长度不在理想范围内：{char_count}字符")
                    
                    return content
                else:
                    logger.warning(f"API返回了无效响应: {response_data}")
            except Exception as e:
                logger.error(f"API调用出错 (尝试 {attempt+1}/{self.max_retries}) 针对 {log_identifier}: {e}")
                logger.debug(traceback.format_exc())
                
                if attempt < self.max_retries - 1:
                    # 指数退避策略
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    logger.info(f"等待 {wait_time:.2f} 秒后重试...")
                    time.sleep(wait_time)
            
        logger.error(f"达到最大重试次数 {self.max_retries}，无法获取 {log_identifier} 的响应")
        return None
    
    def summarize_posts(self) -> bool:
        """
        读取Excel文件，使用DeepSeek API批量处理生成摘要，并保存结果
        
        Returns:
            是否成功生成摘要
        """
        logger.info(f"开始处理摘要，从文件 {self.input_file} 读取...")
        
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
            required_columns = ['post_title', 'post_content']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                logger.error(f"输入数据缺少必要的列: {', '.join(missing_columns)}")
                return False
            
            # 将DataFrame转换为字典列表，便于处理
            records = df.to_dict('records')
            
            total_posts = len(records)
            summarized_count = 0
            failed_count = 0
            
            with open(self.output_file, "w", encoding="utf-8") as f:
                # 先写入文件头部信息
                f.write(f"# LLM 相关新闻日报摘要 ({self.input_file.stem})\n\n")
                f.write(f"基于 {total_posts} 条高质量 Reddit 帖子生成\n\n")
                
                for i, record in enumerate(records):
                    post_index = i + 1
                    post_title = record.get('post_title', '无标题')
                    post_url = record.get('post_url', 'URL_Not_Found') # 获取 URL
                    log_identifier = f"帖子 {post_index}/{total_posts} ('{post_title[:30]}...')"
                    logger.info(f"正在处理: {log_identifier}")
                    
                    # 第一个帖子前不加空行，后续帖子前加三个空行以确保两行空白
                    if i > 0:
                        f.write("\n\n\n") # Write three newlines
                        
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
                            cleaned_summary_body = re.sub(r'(\n\s*){2,}', '\n', cleaned_response_text)
                            
                            # (移除重构逻辑)
                            # final_text = cleaned_summary_body
                            # if link_line: 
                            #     final_text += "\n" + link_line
                            final_text = cleaned_summary_body # 清理后的文本即为最终摘要
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
                    
                    time.sleep(random.uniform(0.5, 1.5))
                    
                # 循环结束后
                logger.info(f"摘要生成完成: 成功 {summarized_count} 篇, 失败 {failed_count} 篇，共处理 {total_posts} 条帖子")
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
        help="指定输入的 Excel 文件路径 (例如：data/reddit_posts_2024-01-01.xlsx)。如果未指定，则使用 config.cleaned_posts_file"
    )
    parser.add_argument(
        "--output", 
        type=str, 
        help="指定输出的摘要文件路径 (例如：data/my_summaries.txt)。如果未指定，则使用 config.summaries_file"
    )

    args = parser.parse_args()

    # 使用命令行参数调用 run 函数
    run(input_file=args.input, output_file=args.output)