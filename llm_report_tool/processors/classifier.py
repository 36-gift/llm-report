"""
摘要智能分类模块，使用NLP技术对摘要进行分类
"""
import os
import re
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union, Tuple
from pathlib import Path
import requests
import json
import time
import random
import traceback
import argparse
from collections import Counter, defaultdict
from ..utils.config import config, logger

class Classifier: # Renamed from TopicExtractor
    """摘要智能分类类"""
    
    def __init__(self, 
                 input_file: Optional[Union[str, Path]] = None,
                 output_file: Optional[Union[str, Path]] = None,
                 api_key: Optional[str] = None):
        """
        初始化摘要分类器
        
        Args:
            input_file: 摘要输入文件路径，默认使用配置中的路径
            output_file: 分类结果输出文件路径 (JSON)，默认使用配置中自动生成的路径
            api_key: DeepSeek API密钥，默认从配置中获取
        """
        self.input_file = Path(input_file) if input_file else config.summaries_file
        self.output_file = Path(output_file) if output_file else config.data_dir / f"classified_summaries_{config.current_date}.json"
        self.api_key = api_key or config.deepseek_api_key
        self.base_url = "https://api.deepseek.com/v1"
        self.summaries: List[Dict] = []
        self.classified_summaries: List[Dict] = []
        self.category_hotspot_summaries: Dict[str, str] = {}
        self.concept_hotspots: Dict[str, str] = {}
    
    def _load_data(self) -> bool:
        """
        加载摘要数据
        
        Returns:
            是否成功加载数据
        """
        if not self.input_file.exists():
            logger.error(f"摘要文件不存在: {self.input_file}")
            self.summaries = []
            return False
            
        try:
            with open(self.input_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            self.summaries = self._parse_summaries(content)
            logger.info(f"成功解析 {len(self.summaries)} 条摘要")
                
            return True
        except Exception as e:
            logger.error(f"加载摘要数据出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.summaries = []
            return False
    
    def _parse_summaries(self, content: str) -> List[Dict]:
        """
        解析摘要文件内容 (新格式 - 基于标题查找)
        
        Args:
            content: 摘要文件内容
            
        Returns:
            帖子信息字典列表，每个字典包含: index, title, summary, url
        """
        posts = []
        # Regex to find the start of each post section (title line)
        # Captures: 1: Full title line, 2: Index, 3: Title text
        title_pattern = re.compile(r"^(##\s*(\d+)\.\s*(.*?))\s*$(?=\r?\n)", re.MULTILINE)
        # Regex to find the link at the end of a section
        link_pattern = re.compile(r"(?:\r?\n)\s*\[原文链接\]\((.*?)\)\s*$")

        matches = list(title_pattern.finditer(content))
        
        if not matches:
            logger.error("在摘要文件中未找到任何有效的帖子标题 (格式如: ## 1. Title)，无法解析。")
            return []

        successful_parses = 0
        for i, current_match in enumerate(matches):
            try:
                index_str = current_match.group(2)
                title = current_match.group(3).strip()
                index = int(index_str)
                
                # Define the start and end boundaries for the current post's content
                content_start = current_match.end()
                # End is the start of the next title, or end of file if it's the last post
                content_end = matches[i+1].start() if (i + 1) < len(matches) else len(content)
                
                # Extract the block of text for this post
                post_block = content[content_start:content_end].strip()
                
                # Find the link within this block
                link_match = link_pattern.search(post_block)
                
                if link_match:
                    url = link_match.group(1).strip()
                    # Summary is the text before the link match
                    summary_content = post_block[:link_match.start()].strip()
                else:
                    # If no link found (shouldn't happen with current summarizer format), log and skip?
                    logger.warning(f"帖子 {index} ({title[:30]}...) 未找到预期的 [原文链接]，跳过。")
                    continue # Or handle differently if links can be missing

                # Basic check for empty summary
                if not summary_content:
                    logger.warning(f"帖子 {index} ({title[:30]}...) 的摘要内容为空，跳过。")
                    continue
                    
                posts.append({
                    "index": index,
                    "title": title,
                    "summary": summary_content,
                    "url": url
                })
                successful_parses += 1
                
            except ValueError:
                 logger.warning(f"解析帖子标题中的索引 '{index_str}' 时出错，跳过此部分。")
                 continue
            except Exception as e:
                 logger.warning(f"解析摘要部分 {i+1} 时发生意外错误: {e}. 跳过部分: \n{content[current_match.start():content_end][:150]}...")
                 continue
                     
        logger.info(f"通过标题查找成功解析 {successful_parses} / {len(matches)} 条摘要部分")
        
        # Sort by index just in case the regex finds them out of order (unlikely but safe)
        posts.sort(key=lambda x: x['index'])
        
        return posts

    def _classify_summary_with_api(self, title: str, summary: str) -> str:
        """
        使用DeepSeek API对单个摘要进行智能分类

        Args:
            title: 帖子标题
            summary: 帖子摘要内容

        Returns:
            分类名称 (例如 "模型发布", "性能评测" 等)，或 "分类失败"
        """
        logger.debug(f"开始对摘要进行分类: {title[:50]}...")

        if not self.api_key:
            logger.warning("未提供API密钥，无法进行智能分类")
            return "分类失败"

        categories = [
            "模型发布与更新",   # 新模型、版本迭代、权重发布
            "性能评测与比较",   # Benchmarks, MMLU, 性能测试, 模型对比
            "技术讨论与分析",   # 架构探讨, 训练技巧, MoE, 量化, 推理优化
            "应用案例与工具",   # 具体应用, 项目展示, 工具介绍 (如Ollama, LM Studio, UI)
            "资源分享与教程",   # 数据集, Colab Notebook, 指南, 教程
            "社区观点与讨论",   # 寻求建议, 开放式讨论, 市场趋势
            "其他"
        ]

        prompt = f"""
        请根据以下Reddit帖子摘要的内容，将其分类到最合适的类别中。

        帖子标题：{title}
        摘要内容：
        {summary}

        请从以下预定义类别中选择一个最匹配的类别：
        - 模型发布与更新
        - 性能评测与比较
        - 技术讨论与分析
        - 应用案例与工具
        - 资源分享与教程
        - 社区观点与讨论
        - 其他

        请**仅**返回一个类别名称，不要添加任何解释或编号。
        """

        try:
            if not hasattr(self, 'headers'):
                 self.headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                 }
            
            data = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "你是一个精确的内容分类助手。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 30,
                "stream": False
            }

            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=data,
                timeout=30
            )
            response.raise_for_status()
            response_data = response.json()

            if "choices" in response_data and len(response_data["choices"]) > 0:
                category = response_data["choices"][0]["message"]["content"].strip()
                if category in categories:
                    logger.debug(f"分类成功: '{title[:30]}...' -> {category}")
                    return category
                else:
                    logger.warning(f"API返回的分类 '{category}' 不在预定义列表中，标记为'其他'")
                    return "其他"
            else:
                logger.warning(f"API未返回有效分类响应 for '{title[:30]}...'")
                return "分类失败"

        except Exception as e:
            logger.error(f"调用API进行分类时出错 for '{title[:30]}...': {e}")
            return "分类失败"

    def classify_all_summaries(self) -> bool:
        """
        加载摘要，对每个摘要进行分类，并存储结果
        
        Returns:
            是否成功完成分类
        """
        logger.info(f"开始摘要智能分类，输入文件: {self.input_file}")
        
        if not self._load_data():
            logger.error("加载摘要数据失败，无法进行分类")
            return False
            
        if not self.summaries:
             logger.warning("摘要列表为空，无需分类")
             return True

        total_summaries = len(self.summaries)
        classified_count = 0
        failed_count = 0
        self.classified_summaries = []

        for i, post_data in enumerate(self.summaries):
            index = post_data.get("index", i + 1)
            title = post_data.get("title", "")
            summary_content = post_data.get("summary", "")
            url = post_data.get("url", "")
            
            logger.info(f"正在分类第 {index}/{total_summaries} 条摘要: '{title[:40]}...'")
            
            if not summary_content:
                logger.warning(f"摘要 {index} 内容为空，跳过分类")
                category = "内容为空"
                failed_count += 1
            else:
                category = self._classify_summary_with_api(title, summary_content)
                if category != "分类失败":
                    classified_count += 1
                else:
                    failed_count += 1
            
            classified_post = {
                "index": index,
                "title": title,
                "summary": summary_content,
                "url": url,
                "category": category
            }
            self.classified_summaries.append(classified_post)
            
            time.sleep(random.uniform(0.3, 0.8)) 

        logger.info(f"分类完成: 成功 {classified_count}, 失败/跳过 {failed_count}，共 {total_summaries} 条摘要")
        return failed_count == 0

    def _generate_category_summary_with_api(self, category: str, posts: List[Dict]) -> str:
        """
        使用DeepSeek API为特定分类生成热点总结

        Args:
            category: 分类名称
            posts: 属于该分类的帖子列表 (字典包含 title, summary)

        Returns:
            生成的热点总结文本，或 "总结生成失败"
        """
        logger.info(f"开始为分类 '{category}' 生成热点总结...")

        if not self.api_key:
            logger.warning(f"未提供API密钥，无法为分类 '{category}' 生成总结")
            return "总结生成失败 (无API密钥)"
        
        if not posts:
             logger.warning(f"分类 '{category}' 没有帖子，无法生成总结")
             return "总结生成失败 (无内容)"

        # 1. 准备输入内容
        input_content = f"以下是关于 '{category}' 的一些Reddit帖子摘要：\n\n"
        max_combined_length = 3500 # 限制组合长度以防超出token限制
        current_length = len(input_content)
        included_posts_count = 0

        for post in posts:
            post_text = f"标题：{post.get('title', '无标题')}\n摘要：{post.get('summary', '无摘要')}\n---\n"
            if current_length + len(post_text) <= max_combined_length:
                input_content += post_text
                current_length += len(post_text)
                included_posts_count += 1
            else:
                logger.warning(f"内容长度超出限制，为 '{category}' 总结截断了部分帖子")
                input_content += "...(更多帖子内容已省略)..."
                break
        
        if included_posts_count == 0:
             logger.warning(f"分类 '{category}' 的首个帖子已超出长度限制，无法生成总结")
             return "总结生成失败 (内容过长)"

        # 2. 构建 Prompt
        prompt = f"""
        请根据以下提供的关于"{category}"类别的Reddit帖子摘要，生成一个简洁而全面的当日热点总结。

        要求：
        1. 总结必须专注于我提供的这些帖子内容。
        2. 总结应概括这个类别下的主要讨论点、发现或趋势。
        3. 使用流畅的中文书面语表达，避免列表格式，形成连贯的段落。
        4. 总结长度控制在 150-250 字之间。
        5. 不要包含具体的帖子标题或指向单个帖子的链接。
        6. 确保总结内容的准确性，忠实反映原文信息。

        以下是需要总结的帖子内容：
        {input_content}
        """

        # 3. 调用 API (类似分类，简化错误处理，可按需增加重试)
        try:
            if not hasattr(self, 'headers'): # Ensure headers exist
                 self.headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                 }
            
            data = {
                "model": "deepseek-chat", # Or choose another suitable model
                "messages": [
                    {"role": "system", "content": "你是一位善于从多篇相关文章中提炼核心主题和趋势的编辑。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7, # Might need adjustment for summarization
                "max_tokens": 500,  # Allow more tokens for summary generation
                "stream": False
            }

            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=data,
                timeout=90 # Increase timeout for potentially longer generation
            )
            response.raise_for_status()
            response_data = response.json()

            if "choices" in response_data and len(response_data["choices"]) > 0:
                summary_text = response_data["choices"][0]["message"]["content"].strip()
                logger.info(f"✓ 成功为分类 '{category}' 生成热点总结")
                return summary_text
            else:
                logger.warning(f"API未返回有效的总结响应 for category '{category}'")
                return "总结生成失败 (API无有效响应)"

        except requests.exceptions.RequestException as e:
            logger.error(f"调用API为分类 '{category}' 生成总结时网络出错: {e}")
            return f"总结生成失败 (网络错误: {e})"
        except Exception as e:
            logger.error(f"调用API为分类 '{category}' 生成总结时出错: {e}")
            logger.error(traceback.format_exc())
            return f"总结生成失败 (内部错误: {e})"

    def _generate_category_hotspot_summaries(self) -> Dict[str, str]:
        """
        识别热门分类并为其生成总结
        
        Returns:
            一个字典，键是热门分类名称，值是生成的总结
        """
        logger.info("开始生成当日分类热点总结 (基于Top 5分类)...")
        self.category_hotspot_summaries = {}
        if not self.classified_summaries:
            logger.warning("没有分类后的摘要，无法生成分类热点总结")
            return self.category_hotspot_summaries

        category_counts = Counter(post['category'] for post in self.classified_summaries if post['category'] not in ["分类失败", "内容为空"])
        top_categories = [cat for cat, count in category_counts.most_common(5)]
        logger.info(f"识别出的Top 5热点分类: {', '.join(top_categories)}")

        posts_by_category = defaultdict(list)
        for post in self.classified_summaries:
            if post['category'] in top_categories:
                posts_by_category[post['category']].append({
                    'title': post.get('title', ''), 
                    'summary': post.get('summary', '')
                })

        for category in top_categories:
            summary_text = self._generate_category_summary_with_api(category, posts_by_category[category])
            self.category_hotspot_summaries[category] = summary_text
            time.sleep(random.uniform(1.0, 2.0))

        logger.info(f"成功为 {len(self.category_hotspot_summaries)} 个分类生成了热点总结")
        return self.category_hotspot_summaries

    def _extract_top_concepts_with_api(self, all_summaries_text: str, top_n: int = 3) -> List[str]:
        """
        使用DeepSeek API从所有摘要文本中提取Top N核心概念
        Args:
            all_summaries_text: 拼接好的所有摘要内容
            top_n: 需要提取的概念数量
        Returns:
            Top N 概念列表，失败则返回空列表
        """
        logger.info(f"开始提取 Top {top_n} 核心概念...")
        if not self.api_key:
            logger.warning("未提供API密钥，无法提取核心概念")
            return []
        if not all_summaries_text:
             logger.warning("摘要内容为空，无法提取核心概念")
             return []

        # Limit input length for API call
        max_input_length = 8000 # Adjust as needed based on API limits
        if len(all_summaries_text) > max_input_length:
            logger.warning(f"摘要总长度过长 ({len(all_summaries_text)}), 截断至 {max_input_length} 进行概念提取")
            all_summaries_text = all_summaries_text[:max_input_length] + "... (内容已截断)"

        prompt = f"""
        请仔细阅读以下来自多个Reddit LLM相关帖子摘要的集合。
        识别并列出这些摘要中讨论最频繁、最重要的 {top_n} 个核心技术概念、模型名称或主题。
        
        要求：
        1. 专注于技术术语、模型名称、关键特性或反复出现的议题。
        2. **仅**返回一个由逗号分隔的列表，包含不多于 {top_n} 个最重要的概念。
        3. 不要添加任何解释、编号或无关文字。例如：模型A, 技术B, 特性C

        摘要内容集合：
        {all_summaries_text}
        """
        
        try:
            # Reuse headers if they exist
            if not hasattr(self, 'headers'):
                 self.headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}

            data = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "你是一个精确识别文本核心概念的助手。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1, # Low temp for deterministic extraction
                "max_tokens": 100, 
                "stream": False
            }
            response = requests.post(f"{self.base_url}/chat/completions", headers=self.headers, json=data, timeout=60)
            response.raise_for_status()
            response_data = response.json()

            if "choices" in response_data and len(response_data["choices"]) > 0:
                concepts_str = response_data["choices"][0]["message"]["content"].strip()
                # Split by comma and clean up whitespace
                concepts = [c.strip() for c in concepts_str.split(',') if c.strip()]
                if concepts:
                     logger.info(f"成功提取到核心概念: {', '.join(concepts[:top_n])}")
                     return concepts[:top_n] # Return only top_n even if API gives more
                else:
                     logger.warning(f"API返回了空的或无效的概念列表: '{concepts_str}'")
                     return []
            else:
                logger.warning("API未返回有效的概念提取响应")
                return []
        except Exception as e:
            logger.error(f"调用API提取核心概念时出错: {e}")
            logger.error(traceback.format_exc())
            return []

    def _generate_concept_hotspot_summaries(self, top_n: int = 3) -> Dict[str, str]:
        """
        识别热门概念并为其生成总结
        Args:
            top_n: 要总结的热门概念数量
        Returns:
            一个字典，键是热门概念名称，值是生成的总结
        """
        logger.info(f"开始生成当日 Top {top_n} 概念热点总结...")
        self.concept_hotspots = {}
        if not self.classified_summaries:
            logger.warning("没有分类后的摘要，无法生成概念热点总结")
            return self.concept_hotspots

        # 1. Combine all summary texts for concept extraction
        all_summaries_text = "\n\n".join([p.get('summary', '') for p in self.classified_summaries if p.get('summary')])
        if not all_summaries_text:
             logger.warning("所有摘要内容均为空，无法提取概念")
             return self.concept_hotspots
        
        # 2. Extract top concepts using API
        top_concepts = self._extract_top_concepts_with_api(all_summaries_text, top_n)

        if not top_concepts:
             logger.warning("未能提取到核心概念，无法生成概念热点总结")
             return self.concept_hotspots
        
        logger.info(f"识别出的 Top {len(top_concepts)} 核心概念: {', '.join(top_concepts)}")

        # 3. Find relevant posts and generate summary for each concept
        for concept in top_concepts:
            # Find summaries containing the concept (case-insensitive search might be better)
            relevant_posts = [
                {'title': p.get('title', ''), 'summary': p.get('summary', '')} 
                for p in self.classified_summaries 
                if p.get('summary') and concept.lower() in p.get('summary', '').lower()
            ]
            
            if relevant_posts:
                logger.info(f"为概念 '{concept}' 找到 {len(relevant_posts)} 条相关摘要，开始生成总结...")
                # Reuse the category summary generation method for now
                # TODO: Consider creating a dedicated concept summary prompt/method
                summary_text = self._generate_category_summary_with_api(concept, relevant_posts) 
                self.concept_hotspots[concept] = summary_text
                time.sleep(random.uniform(1.0, 2.0))
            else:
                 logger.warning(f"未能为概念 '{concept}' 找到任何相关摘要，跳过总结生成")

        logger.info(f"成功为 {len(self.concept_hotspots)} 个概念生成了热点总结")
        return self.concept_hotspots

    def save_results(self) -> None:
        """
        将分类结果、分类热点和概念热点保存到JSON文件
        """
        if not self.classified_summaries:
            logger.warning("没有分类结果可保存")
            return
            
        output_data = {
            "classification_date": config.current_date,
            "source_summary_file": str(self.input_file),
            "category_hotspot_summaries": self.category_hotspot_summaries,
            "concept_hotspots": self.concept_hotspots,
            "classified_summaries": self.classified_summaries
        }
        
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=4)
            logger.info(f"分类结果和热点总结已保存到: {self.output_file}")
        except Exception as e:
            logger.error(f"保存分类结果时出错: {e}")
            logger.error(traceback.format_exc())

def run(input_file: Optional[str] = None, output_file: Optional[str] = None) -> bool:
    """
    执行摘要智能分类和热点总结的主函数
    
    Args:
        input_file: 可选的输入文件路径
        output_file: 可选的输出文件路径
        
    Returns:
        是否成功完成分类和热点总结
    """
    try:
        classifier = Classifier(input_file, output_file)
        classification_successful = classifier.classify_all_summaries()
        
        if classification_successful or classifier.classified_summaries: # Proceed if we have any summaries
            # Generate Concept Hotspots (New Logic)
            classifier._generate_concept_hotspot_summaries(top_n=3) 
            # Optionally keep or remove category hotspots generation:
            # classifier._generate_category_hotspot_summaries()
        else:
             logger.error("摘要分类完全失败，无法生成任何热点总结。")

        # Save results regardless, including any hotspots generated
        classifier.save_results() 
        
        # Return overall success based on classification 
        return classification_successful or len(classifier.classified_summaries) > 0 

    except Exception as e:
        logger.error(f"运行摘要分类器时出错: {e}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="运行摘要智能分类器")
    parser.add_argument(
        "--input", 
        type=str, 
        help="指定输入的摘要文件路径 (例如：data/summaries_2024-01-01.txt)。如果未指定，则使用 config.summaries_file"
    )
    parser.add_argument(
        "--output", 
        type=str, 
        help="指定输出的分类结果JSON文件路径 (例如：data/my_classified.json)。如果未指定，则使用默认路径"
    )

    args = parser.parse_args()
    run(input_file=args.input, output_file=args.output) 