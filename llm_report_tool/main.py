"""
LLM新闻报告工具的主入口模块
提供完整的工作流程控制和命令行接口
"""
import sys
import os
import argparse
from pathlib import Path
from typing import Optional
import logging

# 确保可以导入项目模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from llm_report_tool.scrapers.reddit_scraper import run as run_scraper
from llm_report_tool.processors.data_cleaner import run as run_cleaner
from llm_report_tool.processors.summarizer import run as run_summarizer
from llm_report_tool.processors.classifier import run as run_classifier
from llm_report_tool.processors.latex_report_generator import run as run_latex_report_generator
from llm_report_tool.utils.config import config, logger

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="LLM新闻日报生成工具 - 自动从Reddit爬取当天LLM相关新闻并生成摘要报告",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # 常规选项
    parser.add_argument("-v", "--verbose", action="store_true", help="启用详细日志输出")
    parser.add_argument("--skip-scrape", action="store_true", help="跳过爬取阶段，使用已有数据")
    parser.add_argument("--skip-clean", action="store_true", help="跳过数据质量分析阶段")
    parser.add_argument("--skip-summary", action="store_true", help="跳过摘要生成阶段")
    parser.add_argument("--skip-topic", action="store_true", help="跳过主题分析阶段")
    
    # 输出格式选项 - 仅保留PDF选项
    parser.add_argument("--no-pdf", action="store_true", help="不生成PDF格式报告")
    
    # 输入输出选项
    parser.add_argument("--reddit-url", type=str, help=f"Reddit版块URL，默认: {config.reddit_url}")
    parser.add_argument("--hours", type=int, help=f"过滤多少小时前的新闻，默认: {config.post_cleanup_hours}小时（当天）")
    parser.add_argument("--output-dir", type=str, help="指定输出目录")
    
    # New argument for classifier input
    parser.add_argument("--classifier-input-file", type=str, help="指定摘要分类器使用的输入摘要文件路径")
    
    # New argument for report generator input
    parser.add_argument("--report-input-file", type=str, help="指定PDF报告生成器使用的输入JSON文件路径")
    
    # 性能选项
    parser.add_argument("--python-version", type=str, default="3.10", help="指定Python版本")
    
    return parser.parse_args()

def setup_logging(verbose: bool = False):
    """配置日志级别"""
    if verbose:
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)
        logger.debug("已启用详细日志输出")
    else:
        logger.setLevel(logging.INFO)
        for handler in logger.handlers:
            handler.setLevel(logging.INFO)

def update_config_from_args(args):
    """根据命令行参数更新配置"""
    if args.reddit_url:
        config.reddit_url = args.reddit_url
        logger.debug(f"已设置Reddit URL为: {config.reddit_url}")
    
    if args.hours:
        config.post_cleanup_hours = args.hours
        logger.debug(f"已设置新闻过滤时间为: {config.post_cleanup_hours}小时")
    
    if args.output_dir:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(exist_ok=True, parents=True)
        
        # 更新输出路径
        config.reports_dir = output_dir
        logger.debug(f"已设置输出目录为: {output_dir}")

def run_workflow(args) -> bool:
    """运行完整工作流程"""
    success = True
    
    # 1. 爬取阶段
    if not args.skip_scrape:
        logger.info("=== 开始执行Reddit爬虫 ===")
        if not run_scraper():
            logger.error("爬虫阶段失败")
            return False
    else:
        logger.info("已跳过爬虫阶段")
    
    # 2. 数据清洗阶段
    if not args.skip_clean:
        logger.info("=== 开始执行数据质量分析 ===")
        if not run_cleaner():
            logger.error("数据质量分析阶段失败")
            return False
    else:
        logger.info("已跳过数据质量分析阶段")
    
    # 3. 摘要生成阶段
    if not args.skip_summary:
        logger.info("=== 开始执行摘要生成 ===")
        if not run_summarizer():
            logger.error("摘要生成阶段失败")
            return False
    else:
        logger.info("已跳过摘要生成阶段")
    
    # 4. 智能分类阶段
    if not args.skip_topic:
        logger.info("=== 开始执行摘要智能分类 ===")
        # Pass the specific input file if provided
        if not run_classifier(input_file=args.classifier_input_file):
            logger.warning("摘要智能分类阶段失败或部分失败，但将继续执行报告生成")
    else:
        logger.info("已跳过摘要智能分类阶段")
    
    # 5. 报告生成阶段
    if not args.no_pdf:
        logger.info("=== 开始执行PDF报告生成 ===")
        # Use the specified report input file if provided, otherwise default to today's classified file
        report_input_path = args.report_input_file or str(config.data_dir / f"classified_summaries_{config.current_date}.json")
        logger.info(f"将使用以下文件生成报告: {report_input_path}")
        if not run_latex_report_generator(classified_summary_file=report_input_path):
            logger.error("PDF报告生成阶段失败")
            success = False
    else:
        logger.info("已跳过PDF报告生成阶段")
    
    return success

def main():
    """主函数入口"""
    # 解析命令行参数
    args = parse_args()
    
    # 设置日志级别
    setup_logging(args.verbose)
    
    # 检查Python版本
    logger.info(f"使用Python版本: {args.python_version}")
    
    # 更新配置
    update_config_from_args(args)
    
    # 检查API密钥
    if not config.deepseek_api_key and not (args.skip_summary and args.skip_topic):
        logger.error("错误：未设置DEEPSEEK_API_KEY环境变量，摘要生成和智能分类功能将无法使用。")
        logger.error("请设置环境变量或使用--skip-summary和--skip-topic选项跳过相关功能。")
        return 1
    
    try:
        # 运行工作流
        if run_workflow(args):
            logger.info(f"✅ LLM新闻日报生成完成！")
            if not args.no_pdf:
                pdf_path = config.reports_dir / f"{config.current_date}-{config.report_prefix}.pdf"
                logger.info(f"PDF报告已保存至: {pdf_path}")
            return 0
        else:
            logger.error("❌ LLM新闻日报生成部分失败")
            return 1
    except KeyboardInterrupt:
        logger.info("用户中断操作")
        return 130
    except Exception as e:
        logger.exception(f"执行过程中发生错误: {e}")
        return 1

# Add the execution block here
if __name__ == "__main__":
    sys.exit(main())