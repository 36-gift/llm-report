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
    
    def _analyze_content_quality(self, content: str) -> float:
        """
        使用API分析内容质量并返回分数
        
        Args:
            content: 文本内容
            
        Returns:
            质量分数，0-1之间的浮点数
        """
        try:
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
            
            # 调用API
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json={
                    "model": self.model_name,
                    "messages": [
                        {"role": "system", "content": "你是一个内容质量评估专家，精通AI和机器学习领域。" 
                                                     "你的任务是评估文本内容的质量和相关性。请宽松评分，允许更多样化的内容。"},
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
            
            # 清洗真正空白的内容 (只检查 post_content)
            if 'post_content' in df.columns:
                empty_text_mask = df['post_content'].isna() | (df['post_content'] == '') | (df['post_content'] == '内容未找到')
                
                if empty_text_mask.any():
                    empty_count = empty_text_mask.sum()
                    logger.info(f"发现 {empty_count} 条空白内容（无有效文字），将被移除")
                    df = df[~empty_text_mask]
                    logger.info(f"清洗后保留 {len(df)} 条记录")
            
            # 创建一个新的quality_score列
            df['quality_score'] = 0.0
            
            # 进行内容质量评分
            logger.info("开始对内容进行质量评分...")
            for i, (idx, row) in enumerate(df.iterrows()):
                content = row['post_content']
                
                try:
                    score = self._analyze_content_quality(content)
                    df.at[idx, 'quality_score'] = score
                    logger.info(f"内容 {i+1}/{len(df)} 质量分数: {score:.2f}")
                except Exception as e:
                    logger.error(f"分析内容质量时出错: {str(e)}")
                    # 出错时给予中等分数
                    df.at[idx, 'quality_score'] = 0.5
            
            # 根据质量分数筛选数据
            initial_count = len(df)
            quality_threshold = 0.60
            df = df[df['quality_score'] >= quality_threshold]
            filtered_count = len(df)
            removed_count = initial_count - filtered_count
            logger.info(f"质量评分完成。根据阈值 {quality_threshold} 进行筛选，保留 {filtered_count} 条记录，移除了 {removed_count} 条记录。")

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