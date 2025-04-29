"""
话题抽取与分类模块，使用NLP技术从摘要内容中提取和分类主题
"""
import os
import re
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union, Tuple
from pathlib import Path
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation, NMF
import requests
import json
from ..utils.config import config, logger

# 下载所需的nltk资源
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('punkt')
    nltk.download('stopwords')

class TopicExtractor:
    """话题抽取与分类类，使用NLP技术从摘要内容中提取和分类主题"""
    
    def __init__(self, 
                 input_file: Optional[Union[str, Path]] = None,
                 output_file: Optional[Union[str, Path]] = None,
                 api_key: Optional[str] = None):
        """
        初始化话题抽取器
        
        Args:
            input_file: 摘要输入文件路径，默认使用配置中的路径
            output_file: 话题输出文件路径，默认使用配置中自动生成的路径
            api_key: DeepSeek API密钥，默认从配置中获取
        """
        self.input_file = Path(input_file) if input_file else config.summaries_file
        self.output_file = Path(output_file) if output_file else config.data_dir / f"topics_{config.current_date}.json"
        self.api_key = api_key or config.deepseek_api_key
        self.base_url = "https://api.deepseek.com/v1"
        self.num_topics = 5  # 默认主题数量
        self.topic_names = []  # 存储自动命名的主题
        self.topic_keywords = []  # 存储每个主题的关键词
        self.topic_distribution = {}  # 存储摘要在各主题上的分布
        
        # 中英文停用词
        self.stopwords = set(stopwords.words('english'))
        self.cn_stopwords = {'的', '了', '和', '是', '在', '我', '有', '这', '些', '中', '与', '就', '也', '不', '都', '而', '要', '但', '对', '从', '或', '向', '并', '等', '被'}
        self.stopwords.update(self.cn_stopwords)
    
    def preprocess_text(self, text: str) -> str:
        """
        预处理文本，包括标记化、去除停用词等
        
        Args:
            text: 输入文本
            
        Returns:
            处理后的文本字符串
        """
        # 去除特殊字符和数字
        text = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', text)
        text = re.sub(r'\d+', ' ', text)
        
        # 英文转小写并分词
        tokens = word_tokenize(text.lower())
        
        # 去除停用词
        filtered_tokens = [token for token in tokens if token not in self.stopwords and len(token) > 1]
        
        # 返回空格连接的文本
        return ' '.join(filtered_tokens)
    
    def extract_topics_with_lda(self, texts: List[str]) -> Tuple[List[List[str]], List[List[float]]]:
        """
        使用scikit-learn的LDA模型进行主题抽取
        
        Args:
            texts: 文本列表
            
        Returns:
            主题关键词列表和每篇文档的主题分布
        """
        logger.info("使用LDA模型进行主题抽取...")
        
        # 文本预处理
        processed_texts = [self.preprocess_text(text) for text in texts]
        
        # 创建词袋模型 (Count Vectorizer)
        vectorizer = CountVectorizer(max_df=0.9, min_df=2, max_features=1000)
        X = vectorizer.fit_transform(processed_texts)
        
        # 获取特征名称（词汇表）
        feature_names = vectorizer.get_feature_names_out()
        
        # 训练LDA模型
        lda = LatentDirichletAllocation(
            n_components=self.num_topics,
            max_iter=10,
            learning_method='online',
            random_state=42,
            batch_size=128,
            n_jobs=-1
        )
        
        # 应用模型
        lda.fit(X)
        
        # 获取主题词
        topic_keywords = []
        for topic_idx, topic in enumerate(lda.components_):
            # 获取每个主题的前10个词
            top_features_ind = topic.argsort()[:-11:-1]
            top_features = [feature_names[i] for i in top_features_ind]
            topic_keywords.append(top_features)
        
        # 获取文档-主题分布
        doc_topic_dist = lda.transform(X)
        
        return topic_keywords, doc_topic_dist.tolist()
    
    def name_topics_with_api(self, topic_keywords: List[List[str]]) -> List[str]:
        """
        使用DeepSeek API为主题自动命名
        
        Args:
            topic_keywords: 每个主题的关键词列表
            
        Returns:
            主题名称列表
        """
        logger.info("使用DeepSeek API为主题自动命名...")
        
        if not self.api_key:
            logger.warning("未提供API密钥，使用默认主题名称")
            return [f"主题{i+1}" for i in range(len(topic_keywords))]
        
        # 设置API头信息
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # 准备提示词
        prompt_template = """
        作为一名专业的主题命名专家，请为以下关键词组成的主题提供一个简洁、具体的主题名称（不超过5个字）。
        
        关键词列表: {keywords}
        
        如果关键词中包含"图像分析"、"数据图表"、"界面截图"、"系统架构"等与视觉内容相关的词汇，请确保主题名称能反映出图像或可视化的元素。
        
        请直接回答主题名称，不需要任何解释或附加内容。主题名称应当简洁、专业且能准确捕捉关键词的核心概念。
        """
        
        topic_names = []
        
        for keywords in topic_keywords:
            # 检查是否包含图像相关关键词
            has_image_keywords = any(img_term in " ".join(keywords).lower() for img_term in 
                                    ["图像", "图表", "截图", "架构", "数据", "界面", "视觉"])
            
            # 根据是否包含图像相关关键词调整提示词
            if has_image_keywords:
                logger.info(f"检测到图像相关关键词: {keywords}")
                
            prompt = prompt_template.format(keywords=", ".join(keywords))
            
            try:
                # 构建请求数据
                data = {
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": "你是一个专业的主题命名助手，擅长为关键词集合命名简洁的主题。"},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": config.temperature_topic_extractor,  # 使用全局配置的温度参数
                    "max_tokens": 20,
                    "stream": False
                }
                
                # 调用API
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=30
                )
                
                # 检查响应状态
                response.raise_for_status()
                response_data = response.json()
                
                if "choices" in response_data and len(response_data["choices"]) > 0:
                    # 获取主题名称并清理
                    name = response_data["choices"][0]["message"]["content"]
                    name = name.strip().strip('"\'.,;').strip()
                    # 如果名称过长，则截断
                    if len(name) > 10:
                        name = name[:10]
                    topic_names.append(name)
                else:
                    # 使用默认名称
                    topic_names.append(f"主题{len(topic_names)+1}")
                    
            except Exception as e:
                logger.error(f"API调用出错: {e}")
                # 使用默认名称
                topic_names.append(f"主题{len(topic_names)+1}")
                
            # 添加延迟避免API速率限制
            import time
            time.sleep(1)
            
        return topic_names
    
    def analyze_topics(self) -> Dict:
        """
        分析摘要文件并提取主题
        
        Returns:
            包含主题分析结果的字典
        """
        logger.info(f"开始主题分析，从文件 {self.input_file} 读取...")
        
        try:
            # 检查输入文件是否存在
            if not self.input_file.exists():
                logger.error(f"输入文件不存在: {self.input_file}")
                return {}
                
            # 读取摘要文件
            with open(self.input_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 分割摘要部分
            summaries = []
            current_summary = ""
            in_summary = False
            
            # 记录图片信息，与摘要关联
            image_info = {}
            batch_id_current = ""
            has_image_analysis = False
            
            for line in content.split('\n'):
                if line.startswith('## 批次'):
                    if current_summary:
                        summaries.append(current_summary)
                    current_summary = ""
                    in_summary = True
                    
                    # 从批次行提取批次ID，用于关联图片信息
                    batch_id_current = line.split('批次 ')[1].split(' ')[0] if '批次 ' in line else f"batch_{len(summaries)}"
                    image_info[batch_id_current] = {
                        "urls": [],
                        "has_analysis": False
                    }
                    has_image_analysis = False
                    
                elif line.startswith('#') and in_summary:
                    if current_summary:
                        summaries.append(current_summary)
                    current_summary = ""
                    in_summary = False
                elif in_summary and line.strip():
                    # 收集包含图片信息的行
                    if "图片URL" in line or line.startswith("- http"):
                        if line.startswith("- "):
                            image_url = line[2:].split("（")[0].strip()  # 提取URL，移除可能的描述
                            image_info[batch_id_current]["urls"].append(image_url)
                    
                    # 检测是否包含图片分析内容
                    if "图片" in line and ("显示" in line or "表明" in line or "根据图片" in line):
                        image_info[batch_id_current]["has_analysis"] = True
                        has_image_analysis = True
                    
                    current_summary += line + "\n"
                    
            # 添加最后一个摘要
            if current_summary:
                summaries.append(current_summary)
                
            if not summaries:
                logger.warning("未从文件中提取到摘要内容")
                return {}
                
            logger.info(f"共提取出 {len(summaries)} 个摘要段落")
            
            # 增强主题提取提示，包含图片信息
            enhanced_summaries = []
            for i, summary in enumerate(summaries):
                enhanced_summary = summary
                batch_id = f"batch_{i}"
                
                # 检查是否有匹配的批次ID
                matching_batch = None
                for bid in image_info:
                    if bid == batch_id or str(i) in bid:
                        matching_batch = bid
                        break
                
                if matching_batch and image_info[matching_batch]["urls"]:
                    img_count = len(image_info[matching_batch]["urls"])
                    has_analysis = image_info[matching_batch]["has_analysis"]
                    
                    logger.info(f"批次 {matching_batch} 包含 {img_count} 张图片")
                    
                    # 在摘要中添加图片相关信息增强主题分析
                    if has_analysis:
                        # 已包含图片分析
                        enhanced_summary += f"\n[图像分析] [共{img_count}张] "
                        # 添加一些图片URL中可能出现的关键词，帮助主题模型
                        for url in image_info[matching_batch]["urls"][:2]:  # 最多分析2个URL
                            if "chart" in url.lower() or "graph" in url.lower():
                                enhanced_summary += " 数据图表 性能数据 "
                            elif "architecture" in url.lower() or "diagram" in url.lower():
                                enhanced_summary += " 系统架构 模型结构 "
                            elif "screenshot" in url.lower():
                                enhanced_summary += " 界面截图 代码片段 "
                    else:
                        # 未包含图片分析，仅添加图片标记
                        enhanced_summary += f"\n[未分析图像] [共{img_count}张] "
                
                enhanced_summaries.append(enhanced_summary)
            
            # 主题抽取
            self.topic_keywords, doc_topics = self.extract_topics_with_lda(enhanced_summaries)
            
            # 主题命名
            self.topic_names = self.name_topics_with_api(self.topic_keywords)
            
            # 构建主题分布数据
            for i, doc_dist in enumerate(doc_topics):
                # 获取最主要的主题
                main_topic_idx = np.argmax(doc_dist)
                main_topic_prob = doc_dist[main_topic_idx]
                
                # 更新主题分布
                self.topic_distribution[f"摘要{i+1}"] = {
                    "主要主题": self.topic_names[main_topic_idx],
                    "主题概率": main_topic_prob,
                    "完整分布": {self.topic_names[j]: prob for j, prob in enumerate(doc_dist)}
                }
            
            # 保存结果到JSON文件
            result = {
                "主题列表": [{"名称": name, "关键词": keywords} for name, keywords in zip(self.topic_names, self.topic_keywords)],
                "摘要主题分布": self.topic_distribution
            }
            
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
                
            logger.info(f"主题分析完成，结果已保存至 {self.output_file}")
            
            return result
            
        except Exception as e:
            logger.error(f"主题分析出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {}
            
    def get_results(self) -> Dict:
        """
        获取主题分析结果
        
        Returns:
            主题分析结果字典
        """
        if not self.topic_names or not self.topic_distribution:
            return self.analyze_topics()
        else:
            return {
                "主题列表": [{"名称": name, "关键词": keywords} for name, keywords in zip(self.topic_names, self.topic_keywords)],
                "摘要主题分布": self.topic_distribution
            }


def run(input_file: Optional[str] = None, output_file: Optional[str] = None) -> bool:
    """
    执行主题抽取的主函数
    
    Args:
        input_file: 可选的输入文件路径
        output_file: 可选的输出文件路径
        
    Returns:
        是否成功生成主题分析
    """
    try:
        extractor = TopicExtractor(input_file, output_file)
        result = extractor.analyze_topics()
        return bool(result)
    except Exception as e:
        logger.error(f"主题抽取模块出错: {e}")
        return False


if __name__ == "__main__":
    run()