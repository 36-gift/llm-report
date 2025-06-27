#!/usr/bin/env python
"""
Main entry module for the LLM News Report Tool.
Provides complete workflow control and command line interface.
"""
import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# 确保可以导入项目模块
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from llm_report_tool.processors.classifier import run as run_classifier
from llm_report_tool.processors.data_cleaner import run as run_cleaner
from llm_report_tool.processors.latex_report_generator import run as run_latex_report_generator
from llm_report_tool.processors.summarizer import run as run_summarizer
from llm_report_tool.scrapers.reddit_scraper import run as run_scraper
from llm_report_tool.utils.config import config
from llm_report_tool.utils.logging_config import get_logger, setup_logging


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="LLM News Daily Report Generator - Automatically scrape LLM-related news from Reddit and generate summary reports",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # General options
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging output"
    )
    parser.add_argument(
        "--skip-scrape", action="store_true", help="Skip scraping phase, use existing data"
    )
    parser.add_argument(
        "--skip-clean", action="store_true", help="Skip data quality analysis phase"
    )
    parser.add_argument("--skip-summary", action="store_true", help="Skip summary generation phase")
    parser.add_argument("--skip-topic", action="store_true", help="Skip topic analysis phase")

    # Output format options - PDF only
    parser.add_argument("--no-pdf", action="store_true", help="Do not generate PDF format report")

    # Input/output options
    parser.add_argument(
        "--reddit-url", type=str, help=f"Reddit subreddit URL, default: {config.reddit_url}"
    )
    parser.add_argument(
        "--hours",
        type=int,
        help=f"Filter news from how many hours ago, default: {config.post_cleanup_hours} hours (current day)",
    )
    parser.add_argument("--output-dir", type=str, help="Specify output directory")

    # New argument for classifier input
    parser.add_argument(
        "--classifier-input-file",
        type=str,
        help="Specify input summary file path for the classifier",
    )

    # New argument for report generator input
    parser.add_argument(
        "--report-input-file",
        type=str,
        help="Specify input JSON file path for the PDF report generator",
    )

    # Demo mode for testing
    parser.add_argument("--demo", action="store_true", help="Run in demo mode with test data")

    # Quick mode - skip API-dependent steps when no API key
    parser.add_argument(
        "--quick", action="store_true", help="Quick mode: skip API calls when no valid API key"
    )

    # No-API mode - use rule-based processing only
    parser.add_argument(
        "--no-api",
        action="store_true",
        help="No-API mode: use rule-based processing, skip summaries and classification",
    )

    # Resume options for interrupted workflows
    parser.add_argument(
        "--resume-from-summary",
        action="store_true",
        help="Resume from summary step: skip scraping and cleaning, use existing data files",
    )
    parser.add_argument(
        "--resume-from-report",
        action="store_true",
        help="Resume from report step: skip everything, generate report from existing classified data",
    )
    parser.add_argument(
        "--auto-resume",
        action="store_true",
        help="Automatically detect where to resume based on existing files",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show status of existing files and suggest resume options",
    )

    # Performance options
    parser.add_argument("--python-version", type=str, default="3.10", help="Specify Python version")

    return parser.parse_args()


def setup_logging_config(verbose: bool = False) -> logging.Logger:
    """Configure logging level."""
    log_level = "DEBUG" if verbose else config.log_level

    logger = setup_logging(
        log_level=log_level,
        log_to_file=config.log_to_file,
        log_to_console=config.log_to_console,
        structured_logging=config.structured_logging,
    )

    if verbose:
        logger.debug("已启用详细日志输出")

    return logger


def create_demo_data() -> bool:
    """Create demo data for testing the workflow."""
    logger = get_logger(__name__)

    try:
        # Create demo Reddit posts data
        demo_data = [
            {
                "post_title": "New DeepSeek Model Released - Performance Breakthrough",
                "post_content": "DeepSeek has just released their latest model with impressive performance on reasoning tasks. The model shows significant improvements over previous versions in mathematical reasoning and code generation. Early benchmarks suggest it's competitive with GPT-4 level performance while being more efficient.",
                "post_url": "https://www.reddit.com/r/LocalLLaMA/comments/demo1/",
                "post_date": config.current_date,
                "quality_score": 0.9,
            },
            {
                "post_title": "Open Source LLM Training: Best Practices Guide",
                "post_content": "This comprehensive guide covers the best practices for training large language models from scratch. Topics include data preparation, model architecture choices, training strategies, and evaluation metrics. The author shares lessons learned from training multiple models.",
                "post_url": "https://www.reddit.com/r/LocalLLaMA/comments/demo2/",
                "post_date": config.current_date,
                "quality_score": 0.85,
            },
            {
                "post_title": "LLM Benchmarking: New MMLU-Pro Results",
                "post_content": "Latest MMLU-Pro benchmark results show interesting trends in model performance across different domains. Claude-3.5 and GPT-4o lead in most categories, but some open source models are showing surprising strength in specific areas like mathematics and coding.",
                "post_url": "https://www.reddit.com/r/LocalLLaMA/comments/demo3/",
                "post_date": config.current_date,
                "quality_score": 0.8,
            },
        ]

        # Save to Excel file
        df = pd.DataFrame(demo_data)
        df.to_excel(config.reddit_posts_file, index=False)
        logger.info(f"演示数据已保存到: {config.reddit_posts_file}")

        # Also save as cleaned data
        df.to_excel(config.cleaned_posts_file, index=False)
        logger.info(f"演示数据已保存到: {config.cleaned_posts_file}")

        return True

    except Exception as e:
        logger.error(f"创建演示数据时出错: {e}")
        return False


def check_existing_files() -> dict:
    """Check what workflow files already exist."""
    logger = get_logger(__name__)

    files_status = {
        "scraped_data": config.reddit_posts_file.exists(),
        "cleaned_data": config.cleaned_posts_file.exists(),
        "summaries": config.summaries_file.exists(),
        "classified_data": (
            config.data_dir / f"classified_summaries_{config.current_date}.json"
        ).exists(),
        "pdf_report": (
            config.reports_dir / f"{config.current_date}-{config.report_prefix}.pdf"
        ).exists(),
    }

    logger.info("Existing files status:")
    for file_type, exists in files_status.items():
        status = "✅ EXISTS" if exists else "❌ MISSING"
        logger.info(f"  {file_type}: {status}")

    return files_status


def determine_resume_point(files_status: dict) -> str:
    """Determine the best resume point based on existing files."""
    if files_status["classified_data"]:
        return "report"
    elif files_status["summaries"]:
        return "classification"
    elif files_status["cleaned_data"]:
        return "summary"
    elif files_status["scraped_data"]:
        return "cleaning"
    else:
        return "scraping"


def show_status_and_suggestions() -> None:
    """Show current file status and suggest resume options."""
    logger = get_logger(__name__)

    logger.info("📊 LLM Report Tool - Current Status")
    logger.info("=" * 50)

    files_status = check_existing_files()
    resume_point = determine_resume_point(files_status)

    logger.info("")
    logger.info("💡 Suggestions based on current state:")

    if resume_point == "scraping":
        logger.info("  🟡 No data files found - run full workflow:")
        logger.info("     poetry run python main.py")
    elif resume_point == "cleaning":
        logger.info("  🟡 Scraped data found - resume from cleaning:")
        logger.info("     poetry run python main.py --skip-scrape")
    elif resume_point == "summary":
        logger.info("  🟢 Cleaned data found - resume from summary:")
        logger.info("     poetry run python main.py --resume-from-summary")
    elif resume_point == "classification":
        logger.info("  🟢 Summaries found - resume from classification:")
        logger.info("     poetry run python main.py --skip-scrape --skip-clean --skip-summary")
    elif resume_point == "report":
        logger.info("  🔵 Classified data found - generate report only:")
        logger.info("     poetry run python main.py --resume-from-report")

        if files_status["pdf_report"]:
            logger.info("  ✅ PDF report already exists!")

    logger.info("")
    logger.info("🔄 Auto-resume option:")
    logger.info("     poetry run python main.py --auto-resume")
    logger.info("")


def handle_resume_options(args: argparse.Namespace) -> None:
    """Handle resume options and set appropriate skip flags."""
    logger = get_logger(__name__)

    if args.auto_resume:
        files_status = check_existing_files()
        resume_point = determine_resume_point(files_status)
        logger.info(f"🔄 Auto-resume detected: starting from {resume_point}")

        if resume_point == "report":
            args.resume_from_report = True
        elif resume_point == "classification":
            args.skip_scrape = True
            args.skip_clean = True
            args.skip_summary = True
        elif resume_point == "summary":
            args.resume_from_summary = True
        elif resume_point == "cleaning":
            args.skip_scrape = True

    if args.resume_from_report:
        logger.info("📄 Resume from report: skipping all steps except PDF generation")
        args.skip_scrape = True
        args.skip_clean = True
        args.skip_summary = True
        args.skip_topic = True

        # Check if classified data exists
        classified_file = config.data_dir / f"classified_summaries_{config.current_date}.json"
        if not classified_file.exists():
            logger.error(f"❌ Cannot resume from report: {classified_file} not found")
            logger.error("Please run the full workflow first or use a different resume option")
            exit(1)

    elif args.resume_from_summary:
        logger.info("📝 Resume from summary: skipping scraping and cleaning")
        args.skip_scrape = True
        args.skip_clean = True

        # Check if cleaned data exists
        if not config.cleaned_posts_file.exists():
            logger.error(f"❌ Cannot resume from summary: {config.cleaned_posts_file} not found")
            logger.error("Please run scraping and cleaning first or use --auto-resume")
            exit(1)


def update_config_from_args(args: argparse.Namespace) -> None:
    """Update configuration based on command line arguments."""
    logger = get_logger(__name__)

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


def run_workflow(args: argparse.Namespace) -> bool:
    """Run the complete workflow."""
    logger = get_logger(__name__)
    success = True

    # 1. 爬取阶段
    if not args.skip_scrape:
        logger.info("=== 开始执行Reddit爬虫 ===")
        if args.demo:
            logger.info("演示模式：创建示例数据...")
            success = create_demo_data()
        else:
            success = run_scraper()

        if not success:
            logger.error("爬虫阶段失败")
            return False
    else:
        logger.info("已跳过爬虫阶段")

    # 2. 数据清洗阶段
    if not args.skip_clean:
        logger.info("=== 开始执行数据质量分析 ===")
        if args.demo:
            logger.info("演示模式：跳过API质量分析，使用预设分数")
            success = True  # Skip data cleaning in demo mode
        elif args.no_api:
            # Force rule-based scoring in data cleaner
            logger.info("无API模式：使用基于规则的质量评分")
            from llm_report_tool.processors.data_cleaner import DataCleaner

            cleaner = DataCleaner()
            cleaner.api_available = False  # Force rule-based scoring
            df = cleaner.analyze_data()
            success = not df.empty
        else:
            success = run_cleaner()

        if not success:
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
        report_input_path = args.report_input_file or str(
            config.data_dir / f"classified_summaries_{config.current_date}.json"
        )
        logger.info(f"将使用以下文件生成报告: {report_input_path}")
        if not run_latex_report_generator(classified_summary_file=report_input_path):
            logger.error("PDF报告生成阶段失败")
            success = False
    else:
        logger.info("已跳过PDF报告生成阶段")

    return success


def main() -> int:
    """Main function entry point."""
    # 解析命令行参数
    args = parse_args()

    # 设置日志级别
    logger = setup_logging_config(args.verbose)

    # Handle status command first
    if args.status:
        show_status_and_suggestions()
        return 0

    # 检查Python版本
    logger.info(f"使用Python版本: {args.python_version}")

    # Handle resume options first (this may set skip flags)
    handle_resume_options(args)

    # 更新配置
    update_config_from_args(args)

    # 检查API密钥
    api_key_valid = (
        config.deepseek_api_key and config.deepseek_api_key != "your_deepseek_api_key_here"
    )

    if args.no_api:
        logger.info("无API模式：将使用基于规则的处理，跳过摘要生成和智能分类功能")
        args.skip_summary = True
        args.skip_topic = True
    elif not api_key_valid and not (args.skip_summary and args.skip_topic):
        if args.quick:
            logger.warning("快速模式：未设置有效API密钥，将跳过摘要生成和智能分类功能")
            args.skip_summary = True
            args.skip_topic = True
        else:
            logger.error("错误：未设置DEEPSEEK_API_KEY环境变量，摘要生成和智能分类功能将无法使用。")
            logger.error("请设置环境变量或使用--skip-summary和--skip-topic选项，或添加--quick或--no-api标志跳过相关功能。")
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
