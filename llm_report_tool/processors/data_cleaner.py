"""
数据清洗模块，负责对爬取的原始数据进行API内容质量分析
"""
import pandas as pd
import re
import requests
import json
from datetime import datetime, timedelta
from typing import Union, Optional, List, Dict
from pathlib import Path
from ..utils.config import config, logger

class DataCleaner:
    """数据清洗类，只进行API内容质量分析，不删除数据"""
    
    def __init__(self, 
                 input_file: Optional[Union[str, Path]] = None,
                 output_file: Optional[Union[str, Path]] = None,
                 api_key: Optional[str] = None):
        """
        初始化数据清洗器
        
        Args:
            input_file: 输入文件路径，默认使用配置文件中的路径
            output_file: 输出文件路径，默认使用配置文件中的路径
            api_key: DeepSeek API密钥，默认从配置中获取
        """
        self.input_file = Path(input_file) if input_file else config.reddit_posts_file
        self.output_file = Path(output_file) if output_file else config.cleaned_posts_file
        self.api_key = api_key or config.deepseek_api_key
        self.base_url = "https://api.deepseek.com/v1"
        
        # 初始化API相关配置
        if self.api_key:
            self._setup_api_config()
    
    def _setup_api_config(self) -> None:
        """初始化DeepSeek API配置"""
        # 设置API头信息
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # 使用deepseek-chat模型
        self.model_name = "deepseek-chat"
    
    def _analyze_content_quality(self, content: str, image_urls: Optional[List[str]] = None) -> float:
        """
        使用API分析内容质量并返回分数
        
        Args:
            content: 文本内容
            image_urls: 图片URL列表，可选
            
        Returns:
            质量分数，0-1之间的浮点数
        """
        try:
            # 构建提示
            image_info = ""
            if image_urls and len(image_urls) > 0:
                image_info = f"\n\n帖子包含 {len(image_urls)} 张图片，图片URL:\n" + "\n".join(image_urls[:3])
                if len(image_urls) > 3:
                    image_info += f"\n...等共 {len(image_urls)} 张图片"
            
            prompt = f"""請分析以下Reddit帖子的質量，考慮以下因素：
            - 內容相關性（與AI、機器學習、深度學習、LLM、語言模型相關）
            - 資訊密度
            - 技術深度
            - 內容有用性
            - 寫作質量
            
            文本：
            {content}
            {image_info}
            
            僅返回0到1之間的質量分數，不需要解釋。分數含義：
            - 0-0.3：低質量或不相關
            - 0.3-0.6：一般質量或部分相關
            - 0.6-1.0：高質量且相關
            """
            
            # 调用API
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json={
                    "model": self.model_name,
                    "messages": [
                        {"role": "system", "content": "你是一個內容質量評估專家，精通AI和機器學習領域。" 
                                                     "你的任務是評估文本內容的質量和相關性。請寬鬆評分，允許更多樣化的內容。"},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": config.temperature_data_cleaner,
                    "max_tokens": 10
                },
                timeout=30
            )
            
            # 检查响应状态
            response.raise_for_status()
            response_data = response.json()
            
            if "choices" in response_data and len(response_data["choices"]) > 0:
                # 解析返回的JSON
                try:
                    raw_score = response_data["choices"][0]["message"]["content"].strip()
                    # 尝试提取数字
                    match = re.search(r'(\d+(\.\d+)?)', raw_score)
                    if match:
                        score = float(match.group(1))
                        # 确保分数在0-1范围内
                        score = max(0.0, min(score, 1.0))
                        return score
                    else:
                        # 默认返回中等分数
                        logger.warning(f"无法从API响应中提取分数: {raw_score}")
                        return 0.5
                except json.JSONDecodeError:
                    logger.warning("API返回的结果不是有效的JSON格式")
                    return 0.5
            
            # 如果API调用失败或解析出错，返回中等分数
            return 0.5
            
        except Exception as e:
            logger.error(f"调用API分析内容质量时出错: {str(e)}")
            # 出错时返回中等分数，避免过滤太多内容
            return 0.5
    
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
            
            # 清洗真正空白的内容（既没有文字也没有图片）
            if 'post_content' in df.columns and 'post_images' in df.columns:
                empty_text_mask = df['post_content'].isna() | (df['post_content'] == '') | (df['post_content'] == '内容未找到')
                no_images_mask = df['post_images'].isna() | (df['post_images'] == '')
                truly_empty_mask = empty_text_mask & no_images_mask
                
                if truly_empty_mask.any():
                    empty_count = truly_empty_mask.sum()
                    logger.info(f"发现 {empty_count} 条真正空白内容（无文字且无图片），将被移除")
                    df = df[~truly_empty_mask]
                    logger.info(f"清洗后保留 {len(df)} 条记录")
            
            # 创建一个新的quality_score列
            df['quality_score'] = 0.0
            
            # 只进行内容质量评分，不过滤数据
            logger.info("开始对内容进行质量评分...")
            for i, (idx, row) in enumerate(df.iterrows()):
                content = row['post_content']
                
                # 获取图片URL列表（如果有）
                image_urls = []
                if 'post_images' in df.columns and pd.notna(row['post_images']) and row['post_images'] != '':
                    image_urls = row['post_images'].split('; ') if isinstance(row['post_images'], str) else []
                
                # 图片帖子直接给予中等以上分数
                if isinstance(content, str) and content.startswith('[图片帖子]'):
                    df.at[idx, 'quality_score'] = 0.65
                    continue
                
                try:
                    # 将图片URL传递给分析函数
                    score = self._analyze_content_quality(content, image_urls)
                    df.at[idx, 'quality_score'] = score
                    logger.info(f"内容 {i+1}/{len(df)} 质量分数: {score:.2f}{' (含图片)' if image_urls else ''}")
                except Exception as e:
                    logger.error(f"分析内容质量时出错: {str(e)}")
                    # 出错时给予中等分数
                    df.at[idx, 'quality_score'] = 0.5
            
            # 保存带质量分数的数据
            df.to_excel(self.output_file, index=False)
            logger.info(f"质量分析完成，保留 {len(df)} 条记录")
            logger.info(f"添加质量分数后的数据已保存到 {self.output_file}")
            
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