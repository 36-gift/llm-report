"""
数据清洗模块，负责对爬取的原始数据进行清洗和过滤
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import Union, Optional
from pathlib import Path
from ..utils.config import config, logger

class DataCleaner:
    """数据清洗类，用于清洗和过滤Reddit帖子数据"""
    
    def __init__(self, 
                 input_file: Optional[Union[str, Path]] = None,
                 output_file: Optional[Union[str, Path]] = None,
                 hours_threshold: Optional[int] = None):
        """
        初始化数据清洗器
        
        Args:
            input_file: 输入文件路径，默认使用配置文件中的路径
            output_file: 输出文件路径，默认使用配置文件中的路径
            hours_threshold: 过滤多少小时前的帖子，默认使用配置文件中的设置
        """
        self.input_file = Path(input_file) if input_file else config.reddit_posts_file
        self.output_file = Path(output_file) if output_file else config.cleaned_posts_file
        self.hours_threshold = hours_threshold or config.post_cleanup_hours
        
    def clean_data(self) -> pd.DataFrame:
        """
        清洗数据，包括移除"内容未找到"的行以及过时的帖子
        
        Returns:
            清洗后的DataFrame
        """
        logger.info(f"开始清洗数据，从文件 {self.input_file} 读取...")
        
        try:
            df = pd.read_excel(self.input_file)
            original_count = len(df)
            logger.info(f"原始数据包含 {original_count} 条记录")
            
            # 检查数据格式和内容
            logger.info(f"数据列：{', '.join(df.columns)}")
            
            # DEBUG: 输出前几条记录的内容样本
            if config.debug:
                for i, content in enumerate(df['post_content'].head(3)):
                    logger.debug(f"样本内容 {i+1}: {content[:100]}...")
            
            # 使用更健壮的方法删除 "内容未找到" 的行
            # 改为使用字符串包含检查而非严格相等
            if 'post_content' in df.columns:
                # 计算内容为空或者包含"内容未找到"的记录数
                empty_mask = df['post_content'].isna() | (df['post_content'] == '')
                not_found_mask = df['post_content'].str.contains('内容未找到', na=False)
                
                # 输出诊断信息
                empty_count = empty_mask.sum()
                not_found_count = not_found_mask.sum()
                if empty_count > 0:
                    logger.info(f"发现 {empty_count} 条空内容记录")
                if not_found_count > 0:
                    logger.info(f"发现 {not_found_count} 条'内容未找到'记录")
                
                # 获取有效内容的记录
                df = df[~(empty_mask | not_found_mask)]
                no_content_removed_count = original_count - len(df)
                logger.info(f"移除了 {no_content_removed_count} 条无内容的记录")
            else:
                logger.warning("数据中缺少'post_content'列，跳过内容过滤")
            
            # 将 post_date 列转换为 datetime 对象
            if 'post_date' in df.columns:
                df['post_date'] = pd.to_datetime(df['post_date'])
                
                # 获取当前时间
                now = datetime.now()
                
                # 计算截止时间
                cutoff_time = now - timedelta(hours=self.hours_threshold)
                
                # 删除发布时间在阈值之前的帖子
                df_recent = df[df['post_date'] >= cutoff_time]
                old_posts_removed_count = len(df) - len(df_recent)
                logger.info(f"移除了 {old_posts_removed_count} 条超过 {self.hours_threshold} 小时的旧帖子")
                df = df_recent
            else:
                logger.warning("数据中缺少'post_date'列，跳过日期过滤")
            
            # 进行内容去重（可选）
            if len(df) > 0 and 'post_title' in df.columns and 'post_content' in df.columns:
                df_dedup = df.drop_duplicates(subset=['post_title', 'post_content'])
                duplicates_removed_count = len(df) - len(df_dedup)
                if duplicates_removed_count > 0:
                    logger.info(f"移除了 {duplicates_removed_count} 条重复内容")
                df = df_dedup
                
            # 清理长度过短的内容（可选）
            if len(df) > 0 and 'post_content' in df.columns:
                min_content_length = 50  # 最小内容长度
                df_final = df[df['post_content'].str.len() > min_content_length]
                short_content_removed_count = len(df) - len(df_final)
                if short_content_removed_count > 0:
                    logger.info(f"移除了 {short_content_removed_count} 条内容过短的帖子")
                df = df_final
            
            # 如果筛选后没有剩余数据，保留至少10条原始数据（应急措施）
            if len(df) == 0 and original_count > 0:
                logger.warning("筛选后没有数据剩余，保留部分原始数据作为应急措施")
                emergency_count = min(10, original_count)
                df = pd.read_excel(self.input_file).head(emergency_count)
                logger.info(f"应急保留了 {len(df)} 条原始数据")
            
            # 保存清洗后的数据
            df.to_excel(self.output_file, index=False)
            logger.info(f"成功清洗数据，并保存到 {self.output_file}")
            logger.info(f"清洗前: {original_count} 条; 清洗后: {len(df)} 条")
            
            return df
            
        except FileNotFoundError:
            logger.error(f"错误：找不到文件 {self.input_file}")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"清洗数据出错: {e}")
            return pd.DataFrame()


def run(input_file: Optional[str] = None, output_file: Optional[str] = None) -> bool:
    """
    执行数据清洗的主函数
    
    Args:
        input_file: 可选的输入文件路径
        output_file: 可选的输出文件路径
        
    Returns:
        是否成功清洗数据
    """
    cleaner = DataCleaner(input_file, output_file)
    df = cleaner.clean_data()
    return len(df) > 0


if __name__ == "__main__":
    run()