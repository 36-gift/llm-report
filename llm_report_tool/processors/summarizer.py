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
    
    def generate_prompt(self, posts: List[Dict]) -> str:
        """
        根据帖子列表生成提示词
        
        Args:
            posts: 帖子列表，每个帖子包含标题和内容
            
        Returns:
            用于生成摘要的提示词
        """
        messages = []
        for i, post in enumerate(posts):
            title = post.get("post_title", "无标题")
            content = post.get("post_content", "无内容").strip()
            
            # 获取图片信息（如果有）
            image_info = ""
            if "post_images" in post and post["post_images"]:
                images = post["post_images"]
                if isinstance(images, str) and images.strip():
                    image_urls = images.split("; ")
                    num_images = len(image_urls)
                    if num_images > 0:
                        image_info = f"\n图片信息：该帖子包含{num_images}张图片"
                        # 添加图片URL和潜在内容提示
                        image_info += "\n图片URL（请分析图片可能包含的信息）："
                        for j, url in enumerate(image_urls[:5]):  # 最多添加5张图片URL
                            image_info += f"\n- {url}"
                            # 根据图片URL判断内容类型
                            if "chart" in url.lower() or "graph" in url.lower():
                                image_info += "（可能包含数据图表或性能统计）"
                            elif "screenshot" in url.lower():
                                image_info += "（可能是界面截图或代码截图）"
                            elif "diagram" in url.lower() or "architecture" in url.lower():
                                image_info += "（可能是系统架构图或流程图）"
                        if num_images > 5:
                            image_info += f"\n...(以及其他{num_images-5}张图片)"
            
            # 限制每个帖子的长度，避免超过token限制
            max_content_length = 1000
            if len(content) > max_content_length:
                content = content[:max_content_length] + "...(内容已截断)"
                
            messages.append(f"帖子{i+1}:\n标题：{title}\n内容：{content}{image_info}")
        
        batch_message = "\n\n---\n\n".join(messages)
        
        prompt_template = """
        我将提供一些来自Reddit的LLM（大语言模型）相关帖子内容。请对这些内容进行分析和总结，按以下结构组织：

        ## 大语言模型领域的重要进展
        (总结关于模型发布、性能突破、新技术等重要进展)

        ## 实用技巧与应用
        (总结有关使用技巧、工具应用、优化方法等实用内容)

        ## 其他值得关注的动态
        (总结其他相关趋势、讨论或值得关注的信息)

        要求：
        1. 总结长度必须在300-400字之间，不要过长或过短
        2. 总结应基于我提供的内容，忠实原文，不要添加不存在的事件
        3. 如果内容中有技术术语或专有名词，请保持原样
        4. 使用简洁清晰的中文表述
        5. 确保每个段落都含有核心信息点，对每个帖子内容进行充分提炼
        6. 特别注意分析帖子中包含的图片信息。例如：
           - 如果图片显示数据图表或性能对比，请在摘要中提及这些数据点
           - 如果图片包含代码或架构图，请尝试描述其主要功能或设计
           - 如果图片展示了用户界面，请概述其功能或特点
        7. 在摘要中，明确标注哪些信息来自图片分析（例如："根据图片显示的性能数据..."）

        以下是需要总结的帖子内容：
        
        {message}
        """
        
        return prompt_template.format(message=batch_message)
    
    def _make_api_call_with_retry(self, prompt: str, batch_range: str) -> Optional[str]:
        """
        带重试机制的API调用
        
        Args:
            prompt: 提示词
            batch_range: 当前处理的批次范围，用于日志记录
            
        Returns:
            API响应文本，失败时返回None
        """
        for attempt in range(self.max_retries):
            try:
                # 记录当前尝试次数
                if attempt > 0:
                    logger.info(f"第 {attempt+1}/{self.max_retries} 次尝试调用API，批次 {batch_range}")
                
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
                logger.error(f"API调用出错 (尝试 {attempt+1}/{self.max_retries}): {e}")
                logger.debug(traceback.format_exc())
                
                if attempt < self.max_retries - 1:
                    # 指数退避策略
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    logger.info(f"等待 {wait_time:.2f} 秒后重试...")
                    time.sleep(wait_time)
            
        logger.error(f"达到最大重试次数 {self.max_retries}，无法获取响应")
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
            
            # 检查是否存在图片列
            has_image_column = 'post_images' in df.columns
            if has_image_column:
                logger.info("检测到图片列，将在摘要时包含图片信息")
            else:
                logger.info("未检测到图片列，将只处理文本内容")
            
            # 将DataFrame转换为字典列表，便于处理
            records = df.to_dict('records')
            
            with open(self.output_file, "w", encoding="utf-8") as f:
                # 先写入文件头部信息
                f.write(f"# LLM相关新闻日报摘要 ({self.input_file.stem})\n\n")
                f.write(f"基于 {len(records)} 条当天Reddit帖子生成\n\n")
                
                success_count = 0
                i = 0
                while i < len(records):
                    # 随机生成批处理大小，但确保至少有1个记录
                    batch_size = max(1, random.randint(self.batch_size_min, min(self.batch_size_max, len(records) - i)))
                    batch = records[i:min(i + batch_size, len(records))]
                    
                    # 记录当前批次的范围
                    batch_range = f"Rows {i + 2} to {min(i + batch_size + 1, len(records) + 1)}"
                    logger.info(f"正在处理第 {batch_range} 条记录 (共 {batch_size} 条)...")
                    
                    # 生成提示词
                    prompt = self.generate_prompt(batch)
                    
                    try:
                        # 使用带重试的API调用
                        response_text = self._make_api_call_with_retry(prompt, batch_range)
                        
                        if response_text:
                            # 写入批次信息和响应
                            f.write(f"## 批次 {batch_range} ({batch_size}条帖子):\n\n")
                            f.write(response_text + "\n\n")
                            logger.info(f"✓ 成功生成批次 {batch_range} 的摘要")
                            success_count += 1
                        else:
                            error_msg = f"无法生成摘要 for {batch_range}"
                            f.write(f"### {error_msg}\n\n")
                            logger.error(error_msg)
                    except Exception as e:
                        error_msg = f"摘要生成错误 for {batch_range}: {e}"
                        f.write(f"### {error_msg}\n\n")
                        logger.error(error_msg)
                        logger.debug(traceback.format_exc())
                    
                    # 在批次之间添加一些延迟，避免API速率限制
                    time.sleep(random.uniform(1.0, 3.0))
                    
                    # 移动到下一批
                    i += batch_size
            
                # 写入摘要统计信息
                logger.info(f"摘要生成完成: 成功 {success_count} 批次，共处理 {len(records)} 条记录")
                if success_count > 0:
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
    run()