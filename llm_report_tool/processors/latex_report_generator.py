"""
LaTeX PDF报告生成模块，使用pylatex生成PDF格式的报告
"""
import os
import json
from typing import Dict, List, Optional, Union
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import traceback
from pylatex import Document, Section, Subsection, Command, Package, Figure, NoEscape
from pylatex.utils import bold, italic
from ..utils.config import config, logger
import subprocess

class LatexReportGenerator:
    """LaTeX PDF报告生成类，使用pylatex生成PDF格式的报告"""
    
    def __init__(self, 
                 classified_summary_file: Optional[Union[str, Path]] = None,
                 output_file: Optional[Union[str, Path]] = None):
        """
        初始化LaTeX报告生成器
        
        Args:
            classified_summary_file: 分类后的摘要文件路径 (JSON)，默认使用配置中的路径
            output_file: 输出PDF文件路径，默认使用配置中的路径
        """
        self.classified_summary_file = Path(classified_summary_file) if classified_summary_file else config.data_dir / f"classified_summaries_{config.current_date}.json"
        
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
        
        # 修改数据存储
        self.classified_summaries: List[Dict] = []
        self.concept_hotspots: Dict[str, str] = {} # Add storage for concept hotspots
    
    def _load_data(self) -> bool:
        """
        加载分类后的摘要数据
        
        Returns:
            是否成功加载数据
        """
        if not self.classified_summary_file.exists():
            logger.error(f"分类摘要文件不存在: {self.classified_summary_file}")
            return False
            
        try:
            with open(self.classified_summary_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.classified_summaries = data.get("classified_summaries", [])
                self.concept_hotspots = data.get("concept_hotspots", {}) # Load concept hotspots
            
            if not self.classified_summaries:
                 logger.warning("分类摘要文件中没有找到有效的摘要数据")
                 # return False # Allow proceeding even if only hotspots exist?
                 
            # Log loaded counts
            logger.info(f"成功加载 {len(self.classified_summaries)} 条分类后的摘要")
            if self.concept_hotspots:
                 logger.info(f"成功加载 {len(self.concept_hotspots)} 条概念热点总结")
            else:
                 logger.warning("未找到概念热点总结数据")
                 
            return True # Return true if the file was read, even if empty list/dict
        except Exception as e:
            logger.error(f"加载分类摘要数据出错: {e}")
            logger.error(traceback.format_exc())
            return False
    
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
    
    def _add_concept_hotspots_section(self, doc: Document) -> None:
        """
        添加概念热点总结章节
        
        Args:
            doc: PyLaTeX文档对象
        """
        if not self.concept_hotspots:
            logger.info("没有概念热点总结可添加到报告中")
            return

        with doc.create(Section('当日核心概念热点总结')):
            doc.append("本部分总结了当天讨论中最核心的几个概念或主题。\n\n")
            
            for i, (concept, summary) in enumerate(self.concept_hotspots.items()):
                # Add concept as subsection title
                with doc.create(Subsection(f"核心概念: {self._escape_latex(concept)}")):
                    escaped_summary = self._escape_latex(summary)
                    # Replace newlines with LaTeX newlines
                    latex_summary = escaped_summary.replace('\n', NoEscape(' \\\\ '))
                    doc.append(NoEscape(latex_summary))
                    doc.append(NoEscape("\\vspace{1em}")) # Space after each concept summary

    def _add_classified_summaries_section(self, doc: Document) -> None:
        """
        添加按分类组织的摘要内容章节
        
        Args:
            doc: PyLaTeX文档对象
        """
        # 按分类对摘要进行分组
        summaries_by_category: Dict[str, List[Dict]] = {}
        for summary_data in self.classified_summaries:
            category = summary_data.get("category", "其他")
            if category not in summaries_by_category:
                summaries_by_category[category] = []
            summaries_by_category[category].append(summary_data)
            
        # 定义分类顺序 (可以根据需要调整)
        category_order = [
            "模型发布与更新",
            "性能评测与比较",
            "技术讨论与分析",
            "应用案例与工具",
            "资源分享与教程",
            "社区观点与讨论",
            "内容为空", # 将空内容放在后面
            "分类失败", # 将失败的放在后面
            "其他"      # 其他放在最后
        ]

        with doc.create(Section('LLM技术动态分类摘要')):
            doc.append("本部分将当日相关的Reddit帖子摘要按内容主题进行了智能分类。\n\n")
            
            # 按照定义的顺序遍历分类
            for category in category_order:
                if category in summaries_by_category:
                    summaries_in_category = summaries_by_category[category]
                    # 创建分类小节
                    with doc.create(Subsection(self._escape_latex(category))):
                        for i, summary_data in enumerate(summaries_in_category):
                            title = summary_data.get("title", "无标题")
                            summary_content = summary_data.get("summary", "无摘要")
                            url = summary_data.get("url", "")
                            post_index = summary_data.get("index", "?") # 使用原始索引
                            
                            # 添加帖子标题
                            doc.append(bold(f"{i+1}. {self._escape_latex(title)}"))
                            doc.append(NoEscape("\\\\[0.5ex]")) # 标题后稍微隔开
                            
                            # 添加摘要内容
                            escaped_summary = self._escape_latex(summary_content)
                            # 替换换行符为LaTeX换行
                            latex_summary = escaped_summary.replace('\n', NoEscape(' \\\\ '))
                            doc.append(NoEscape(latex_summary))
                            doc.append(NoEscape("\\\\[0.5ex]")) # 摘要后稍微隔开
                            
                            # 添加原文链接
                            if url and url != 'URL_Not_Found':
                                doc.append(italic("原文链接: "))
                                doc.append(Command('href', [url, self._escape_latex(url)]))
                            
                            # 每个帖子后加一点垂直空间
                            doc.append(NoEscape("\\vspace{1em}")) 

            # 处理未在预定义顺序中的其他分类 (如果有)
            for category, summaries_in_category in summaries_by_category.items():
                 if category not in category_order:
                      logger.warning(f"发现未预定义顺序的分类: {category}，将添加到报告末尾")
                      with doc.create(Subsection(self._escape_latex(category))):
                           # ... (此处省略重复的写入逻辑, 与上面类似) ...
                           for i, summary_data in enumerate(summaries_in_category):
                                title = summary_data.get("title", "无标题")
                                summary_content = summary_data.get("summary", "无摘要")
                                url = summary_data.get("url", "")
                                doc.append(bold(f"{i+1}. {self._escape_latex(title)}"))
                                doc.append(NoEscape("\\\\[0.5ex]"))
                                escaped_summary = self._escape_latex(summary_content)
                                latex_summary = escaped_summary.replace('\n', NoEscape(' \\\\ '))
                                doc.append(NoEscape(latex_summary))
                                doc.append(NoEscape("\\\\[0.5ex]"))
                                if url and url != 'URL_Not_Found':
                                     doc.append(italic("原文链接: "))
                                     doc.append(Command('href', [url, self._escape_latex(url)]))
                                doc.append(NoEscape("\\vspace{1em}"))

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
        生成最终的LaTeX PDF报告
        
        Returns:
            是否成功生成报告
        """
        logger.info(f"开始生成LaTeX PDF报告: {self.output_file}")
        
        if not self._load_data():
            logger.error("无法加载报告所需数据")
            return False
        
        # 创建文档结构
        doc = self._create_document()
        self._add_toc(doc)
        
        # Add Concept Hotspots section first
        self._add_concept_hotspots_section(doc)
        
        # Add the detailed classified summaries section
        self._add_classified_summaries_section(doc)
        
        self._add_footer(doc)
        
        # 生成PDF
        try:
            # 使用xelatex以更好支持中文
            logger.info("开始编译LaTeX文件...")
            doc.generate_pdf(self.output_file.with_suffix(''), clean_tex=True, compiler='xelatex')
            logger.info(f"✅ PDF报告已成功生成: {self.output_file}")
            return True
        except subprocess.CalledProcessError as e:
            # 尝试捕获LaTeX编译错误
            log_file = self.output_file.with_suffix('.log')
            if log_file.exists():
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as logf:
                    log_content = logf.read()[-1000:] # 读取最后1000字符
                    logger.error(f"LaTeX编译错误日志 (末尾部分):\n{log_content}")
            logger.error(f"生成PDF报告时出错: {e}")
            logger.error(traceback.format_exc())
            return False


def run(classified_summary_file: Optional[str] = None, output_file: Optional[str] = None) -> bool:
    """
    执行LaTeX报告生成的主函数
    
    Args:
        classified_summary_file: 分类摘要文件路径
        output_file: 可选的输出PDF文件路径
        
    Returns:
        是否成功生成报告
    """
    try:
        generator = LatexReportGenerator(classified_summary_file=classified_summary_file, output_file=output_file)
        return generator.generate_report()
    except Exception as e:
        logger.error(f"报告生成模块出错: {e}")
        logger.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    pass # 暂时不实现独立运行 