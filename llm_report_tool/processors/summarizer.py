"""
文本总结模块，使用Gemini API对清洗后的数据进行摘要生成
"""
import os
import random
import pandas as pd
import time
import traceback
from typing import Optional, Union, List, Dict
from pathlib import Path
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from ..utils.config import config, logger

class TextSummarizer:
    """文本总结类，使用Gemini API生成摘要"""
    
    def __init__(self, 
                 input_file: Optional[Union[str, Path]] = None,
                 output_file: Optional[Union[str, Path]] = None,
                 api_key: Optional[str] = None):
        """
        初始化总结器
        
        Args:
            input_file: 输入文件路径，默认使用配置中的路径
            output_file: 输出文件路径，默认使用配置中的路径
            api_key: Gemini API密钥，默认从配置中获取
        """
        self.input_file = Path(input_file) if input_file else config.cleaned_posts_file
        self.output_file = Path(output_file) if output_file else config.summaries_file
        self.api_key = api_key or config.gemini_api_key
        self.batch_size_min = config.summary_batch_size_min
        self.batch_size_max = config.summary_batch_size_max
        self.max_retries = 3  # 添加重试次数
        
        if not self.api_key:
            raise ValueError("未提供Gemini API密钥，请设置环境变量GEMINI_API_KEY或通过参数提供")
        
        # 初始化Gemini API
        self._setup_gemini()
    
    def _setup_gemini(self) -> None:
        """初始化Gemini API配置"""
        try:
            genai.configure(api_key=self.api_key)
            
            # 生成配置
            self.generation_config = {
                "temperature": 0.7,  # 降低温度使输出更稳定
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 8192,
                "response_mime_type": "text/plain",
            }
            
            # 安全设置 - 降低阈值避免模型过度过滤
            self.safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            }
            
            # 创建模型
            self.model = genai.GenerativeModel(
                model_name="gemini-1.5-pro",  # 改用更稳定的1.5-pro
                generation_config=self.generation_config,
                safety_settings=self.safety_settings,
                system_instruction="你是一位专业的文本摘要工具，擅长总结技术内容。请使用中文回复，提供准确、简洁的摘要。"
            )
            
            logger.info(f"Gemini API 已初始化，使用模型：gemini-1.5-pro")
        except Exception as e:
            logger.error(f"初始化Gemini API时出错: {e}")
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
            
            # 限制每个帖子的长度，避免超过token限制
            max_content_length = 1000
            if len(content) > max_content_length:
                content = content[:max_content_length] + "...(内容已截断)"
                
            messages.append(f"帖子{i+1}:\n标题：{title}\n内容：{content}")
        
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
        1. 总结应基于我提供的内容，忠实原文，不要添加不存在的事件
        2. 总结应有300字以上
        3. 如果内容中有技术术语或专有名词，请保持原样
        4. 使用简洁清晰的中文表述

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
                
                # 创建聊天会话
                chat_session = self.model.start_chat(history=[])
                
                # 发送消息并获取响应
                response = chat_session.send_message(prompt)
                
                if response and response.text:
                    logger.info(f"成功获得API响应，长度：{len(response.text)} 字符")
                    return response.text
                else:
                    logger.warning(f"API返回了空响应，批次 {batch_range}")
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
        读取Excel文件，使用Gemini API批量处理生成摘要，并保存结果
        
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
            
            with open(self.output_file, "w", encoding="utf-8") as f:
                # 先写入文件头部信息
                f.write(f"# LLM相关新闻摘要 ({self.input_file.stem})\n\n")
                f.write(f"基于 {len(records)} 条Reddit帖子生成\n\n")
                
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
                    logger.error("未成功生成任何摘要")
                    return False
            
        except FileNotFoundError:
            logger.error(f"找不到输入文件: {self.input_file}")
            return False
        except Exception as e:
            logger.error(f"摘要生成过程中出错: {e}")
            logger.error(traceback.format_exc())
            return False


def run(input_file: Optional[str] = None, output_file: Optional[str] = None) -> bool:
    """
    运行摘要生成的主函数
    
    Args:
        input_file: 可选的输入文件路径
        output_file: 可选的输出文件路径
        
    Returns:
        是否成功生成摘要
    """
    try:
        summarizer = TextSummarizer(input_file, output_file)
        return summarizer.summarize_posts()
    except ValueError as e:
        logger.error(f"初始化摘要生成器时出错: {e}")
        return False
    except Exception as e:
        logger.error(f"运行摘要生成器时出错: {e}")
        logger.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    run()