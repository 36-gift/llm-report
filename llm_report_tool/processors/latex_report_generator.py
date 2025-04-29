"""
LaTeX PDF报告生成模块，使用pylatex生成PDF格式的报告
"""
import os
import json
from typing import Dict, List, Optional, Union
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
from pylatex import Document, Section, Subsection, Command, Package, Figure, NoEscape
from pylatex.utils import bold, italic
from ..utils.config import config, logger

class LatexReportGenerator:
    """LaTeX PDF报告生成类，使用pylatex生成PDF格式的报告"""
    
    def __init__(self, 
                 summary_file: Optional[Union[str, Path]] = None,
                 topic_file: Optional[Union[str, Path]] = None,
                 output_file: Optional[Union[str, Path]] = None):
        """
        初始化LaTeX报告生成器
        
        Args:
            summary_file: 摘要文件路径，默认使用配置中的路径
            topic_file: 主题分析文件路径，默认使用根据日期生成的路径
            output_file: 输出PDF文件路径，默认使用配置中的路径
        """
        self.summary_file = Path(summary_file) if summary_file else config.summaries_file
        self.topic_file = Path(topic_file) if topic_file else config.data_dir / f"topics_{config.current_date}.json"
        
        # 设置输出文件
        if output_file:
            self.output_file = Path(output_file)
        else:
            # 使用配置中的报告前缀
            output_name = f"{config.current_date}-{config.report_prefix}.pdf"
            self.output_file = config.reports_dir / output_name
            
        # 确保输出目录存在
        self.output_file.parent.mkdir(exist_ok=True, parents=True)
        
        # 设置LaTeX文档属性
        self.title = config.report_title
        self.author = "自动生成报告系统"
        
        # 设置报告日期范围（当天）
        today = datetime.now().date()
        self.date = f"{today.strftime('%Y年%m月%d日')}"
        
        # 摘要数据
        self.summaries = []
        
        # 主题分析数据
        self.topics = []
        self.topic_distribution = {}
    
    def _load_data(self) -> bool:
        """
        加载摘要和主题分析数据
        
        Returns:
            是否成功加载数据
        """
        # 加载摘要数据
        if not self.summary_file.exists():
            logger.error(f"摘要文件不存在: {self.summary_file}")
            return False
            
        try:
            with open(self.summary_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 解析摘要数据
            self._parse_summaries(content)
            
            # 加载主题分析数据
            if self.topic_file.exists():
                with open(self.topic_file, 'r', encoding='utf-8') as f:
                    topic_data = json.load(f)
                    
                self.topics = topic_data.get("主题列表", [])
                self.topic_distribution = topic_data.get("摘要主题分布", {})
                logger.info(f"成功加载主题分析数据，包含 {len(self.topics)} 个主题")
            else:
                logger.warning(f"主题分析文件不存在: {self.topic_file}，将仅包含摘要内容")
                
            return True
        except Exception as e:
            logger.error(f"加载数据出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def _parse_summaries(self, content: str) -> None:
        """
        解析摘要文件内容
        
        Args:
            content: 摘要文件内容
        """
        # 分割摘要部分
        summaries = []
        current_summary = {"title": "", "content": ""}
        in_summary = False
        
        for line in content.split('\n'):
            if line.startswith('## 批次'):
                if current_summary["content"]:
                    summaries.append(current_summary)
                current_summary = {"title": line.strip('# '), "content": ""}
                in_summary = True
            elif line.startswith('#') and in_summary:
                if current_summary["content"]:
                    summaries.append(current_summary)
                current_summary = {"title": "", "content": ""}
                in_summary = False
            elif in_summary and line.strip():
                # 检查是否是段落标题
                if line.startswith('##'):
                    # 添加为小节标题
                    current_summary["content"] += f"\\subsection*{{{line.strip('# ')}}}\n\n"
                else:
                    current_summary["content"] += line + "\n"
                    
        # 添加最后一个摘要
        if current_summary["content"]:
            summaries.append(current_summary)
            
        self.summaries = summaries
        logger.info(f"成功解析 {len(summaries)} 个摘要段落")
    
    def _escape_latex(self, text: str) -> str:
        """
        转义LaTeX特殊字符
        
        Args:
            text: 输入文本
            
        Returns:
            转义后的文本
        """
        # 替换LaTeX特殊字符
        replacements = {
            '&': '\\&',
            '%': '\\%',
            '$': '\\$',
            '#': '\\#',
            '_': '\\_',
            '{': '\\{',
            '}': '\\}',
            '~': '\\textasciitilde{}',
            '^': '\\textasciicircum{}',
            '\\': '\\textbackslash{}',
        }
        
        for char, replacement in replacements.items():
            text = text.replace(char, replacement)
            
        return text
    
    def _create_document(self) -> Document:
        """
        创建LaTeX文档
        
        Returns:
            PyLaTeX文档对象
        """
        # 创建文档
        doc = Document(page_numbers=True)
        
        # 添加包
        doc.packages.append(Package('ctex'))  # 支持中文
        doc.packages.append(Package('geometry', options=['margin=1in']))
        doc.packages.append(Package('hyperref', options=['colorlinks=true', 'linkcolor=blue']))
        doc.packages.append(Package('graphicx'))
        doc.packages.append(Package('xcolor'))
        doc.packages.append(Package('booktabs'))
        
        # 设置文档信息
        doc.preamble.append(Command('title', self.title))
        doc.preamble.append(Command('author', self.author))
        doc.preamble.append(Command('date', self.date))
        
        # 生成标题页
        doc.append(NoEscape('\\maketitle'))
        
        return doc
    
    def _add_toc(self, doc: Document) -> None:
        """
        添加目录
        
        Args:
            doc: PyLaTeX文档对象
        """
        doc.append(NoEscape('\\tableofcontents'))
        doc.append(NoEscape('\\newpage'))
    
    def _add_topics_section(self, doc: Document) -> None:
        """
        添加主题分析章节
        
        Args:
            doc: PyLaTeX文档对象
        """
        if not self.topics:
            return
            
        with doc.create(Section('主题分析')):
            doc.append("本节展示了对摘要内容进行自动主题分析的结果，反映了今日热点话题。\n\n")
            
            # 添加主题列表
            with doc.create(Subsection('主题列表')):
                for i, topic in enumerate(self.topics):
                    topic_name = topic.get("名称", f"主题{i+1}")
                    keywords = topic.get("关键词", [])
                    
                    doc.append(bold(f"{topic_name}: "))
                    doc.append(f"{', '.join(keywords)}\n\n")
            
            # 添加主题分布
            if self.topic_distribution:
                with doc.create(Subsection('主题分布')):
                    doc.append("各摘要段落的主题分类：\n\n")
                    
                    for summary_id, dist in self.topic_distribution.items():
                        main_topic = dist.get("主要主题", "未知")
                        prob = dist.get("主题概率", 0)
                        
                        doc.append(f"{summary_id}: ")
                        doc.append(bold(f"{main_topic}"))
                        doc.append(f" (概率: {prob:.2f})\n\n")
    
    def _add_summaries_section(self, doc: Document) -> None:
        """
        添加摘要内容章节
        
        Args:
            doc: PyLaTeX文档对象
        """
        with doc.create(Section('LLM技术日报摘要')):
            # 添加日报说明
            doc.append("本日报汇总了当天内与大语言模型相关的重要技术进展、项目动态和社区讨论。\n\n")
            
            for i, summary in enumerate(self.summaries):
                title = summary.get("title", f"摘要 {i+1}")
                content = summary.get("content", "")
                
                # 获取该摘要的主题（如果有）
                topic_info = ""
                summary_key = f"摘要{i+1}"
                if summary_key in self.topic_distribution:
                    topic = self.topic_distribution[summary_key].get("主要主题", "")
                    if topic:
                        topic_info = f" [主题: {topic}]"
                
                with doc.create(Subsection(f"{title}{topic_info}")):
                    doc.append(NoEscape(content))
    
    def _add_footer(self, doc: Document) -> None:
        """
        添加页脚信息
        
        Args:
            doc: PyLaTeX文档对象
        """
        footer_text = f"自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')} | LLM技术日报"
        doc.append(NoEscape(f"\\vspace{{1cm}}\\begin{{center}}\\small{{{footer_text}}}\\end{{center}}"))
    
    def generate_report(self) -> bool:
        """
        生成PDF报告
        
        Returns:
            是否成功生成报告
        """
        try:
            # 加载数据
            if not self._load_data():
                return False
                
            # 创建文档
            doc = self._create_document()
            
            # 添加目录
            self._add_toc(doc)
            
            # 添加主题分析章节
            self._add_topics_section(doc)
            
            # 添加摘要内容章节
            self._add_summaries_section(doc)
            
            # 添加页脚
            self._add_footer(doc)
            
            # 生成PDF
            output_dir = str(self.output_file.parent)
            output_filename = str(Path(output_dir) / self.output_file.stem)
            
            doc.generate_pdf(output_filename, clean_tex=True, compiler='xelatex')
            logger.info(f"PDF報告已生成: {self.output_file}")
            
            return True
        except Exception as e:
            logger.error(f"生成PDF报告出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False


def run(summary_file: Optional[str] = None, topic_file: Optional[str] = None, output_file: Optional[str] = None) -> bool:
    """
    生成PDF报告的主函数
    
    Args:
        summary_file: 可选的摘要文件路径
        topic_file: 可选的主题分析文件路径
        output_file: 可选的输出文件路径
        
    Returns:
        是否成功生成报告
    """
    try:
        generator = LatexReportGenerator(summary_file, topic_file, output_file)
        return generator.generate_report()
    except Exception as e:
        logger.error(f"LaTeX报告生成模块出错: {e}")
        return False


if __name__ == "__main__":
    run() 