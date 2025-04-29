"""
测试Reddit爬虫的日期提取功能
"""
import sys
sys.path.append('.')  # 添加当前目录到路径中

from llm_report_tool.scrapers.reddit_scraper import RedditScraper

def test_date_extraction():
    """测试日期提取功能"""
    scraper = RedditScraper()
    # 测试几个流行的LLM相关帖子链接
    test_urls = [
        "https://www.reddit.com/r/LocalLLaMA/comments/1fufyni/latest_llm_rankings_from_chatbot_arena/",
        "https://www.reddit.com/r/artificial/comments/1fsbqik/deepseekai_releases_deepseek_v2/",
        "https://www.reddit.com/r/MachineLearning/comments/1ftbs18/d_midjourney_v6_is_out/"
    ]
    
    results = []
    for url in test_urls:
        print(f"\n测试URL: {url}")
        try:
            post_data = scraper.fetch_post(url)
            if post_data:
                print(f"✓ 成功提取数据:")
                print(f"  - 标题: {post_data.get('post_title')}")
                print(f"  - 日期: {post_data.get('post_date')}")
                print(f"  - 内容长度: {len(post_data.get('post_content', ''))}")
                print(f"  - 图片数量: {len(post_data.get('post_images', []))}")
                results.append(True)
            else:
                print(f"✗ 无法提取帖子数据")
                results.append(False)
        except Exception as e:
            print(f"✗ 错误: {e}")
            results.append(False)
            
    success_rate = sum(results) / len(results) if results else 0
    print(f"\n测试完成: 成功率 {success_rate:.0%} ({sum(results)}/{len(results)})")
    return success_rate == 1.0

if __name__ == "__main__":
    test_date_extraction() 