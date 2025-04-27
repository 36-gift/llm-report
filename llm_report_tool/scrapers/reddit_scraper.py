"""
Reddit爬虫模块，负责从Reddit抓取相关帖子信息
"""
import time
import re
import requests
from urllib.parse import urlparse
from typing import List, Dict, Optional
import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
from ..utils.config import config, logger

# 添加重试装饰器
def retry_request(max_retries=3, retry_delay=2):
    """重试请求装饰器，当请求失败时自动重试"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except (requests.RequestException, ConnectionError) as e:
                    retries += 1
                    wait_time = retry_delay * (2 ** (retries - 1))  # 指数退避
                    logger.warning(f"请求失败，正在进行第 {retries} 次重试，等待 {wait_time} 秒...")
                    time.sleep(wait_time)
                    if retries == max_retries:
                        logger.error(f"达到最大重试次数 ({max_retries})，操作失败: {e}")
                        raise
            return None
        return wrapper
    return decorator

class RedditScraper:
    """Reddit爬虫类，用于爬取指定subreddit的帖子"""
    
    def __init__(self, subreddit_url: str = None):
        """
        初始化Reddit爬虫
        
        Args:
            subreddit_url: Reddit版块的URL，如不提供则使用配置中的默认值
        """
        self.subreddit_url = subreddit_url or config.reddit_url
        self.headers = {
            'authority': 'www.reddit.com',
            'method': 'GET',
            'scheme': 'https',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cache-control': 'max-age=0',
            'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        }
        # 添加更多的用户代理，随机选择使用
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0'
        ]
    
    def get_post_urls(self) -> List[str]:
        """
        获取Reddit帖子的URL列表
        
        Returns:
            包含所有爬取帖子URL的列表
        """
        post_urls = []
        logger.info(f"开始爬取 {self.subreddit_url} 的帖子...")
        
        try:
            # 配置 Chrome webdriver
            chrome_options = webdriver.ChromeOptions()
            chrome_options.add_argument("--headless")  # 无头模式
            chrome_options.add_argument(
                f"--user-agent={random.choice(self.user_agents)}"
            )
            # 添加额外选项提高稳定性
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            
            service = ChromeService(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.get(self.subreddit_url)
            
            logger.info("已打开浏览器，开始滚动页面获取帖子...")
            last_height = driver.execute_script("return document.body.scrollHeight")
            while True:
                # 向下滚动页面
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(3)  # 等待页面加载

                # 提取当前页面的帖子链接
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                articles = soup.find_all('article', class_=re.compile(r'w-full m-0'))
                for article in articles:
                    post_link = article.find('a', slot='full-post-link')
                    if post_link:
                        relative_url = post_link.get('href')
                        full_url = f"https://www.reddit.com{relative_url}"
                        if full_url not in post_urls:
                            post_urls.append(full_url)

                # 检查是否滚动到底部
                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    # 没有新的页面内容加载，退出
                    break
                last_height = new_height
                
                # 记录进度
                logger.info(f"已收集 {len(post_urls)} 个帖子URL")
                
                # 可选：如果收集足够多的URL可以提前退出
                if len(post_urls) >= 100:  # 设置一个合理的上限
                    logger.info("已达到预设的帖子数量上限，停止爬取")
                    break
                
        except Exception as e:
            logger.error(f"爬取帖子URL时出错: {e}")
        finally:
            driver.quit()  # 确保关闭浏览器
            
        logger.info(f"共爬取到 {len(post_urls)} 个帖子URL")
        return post_urls
    
    @staticmethod
    def extract_post_info(html_content: str) -> Optional[Dict]:
        """
        从HTML内容中提取Reddit帖子信息
        
        Args:
            html_content: 帖子页面的HTML内容
            
        Returns:
            包含帖子信息的字典，包括发布日期、标题和内容；若提取失败则返回None
        """
        soup = BeautifulSoup(html_content, 'html.parser')

        # 提取发帖日期 - 使用更通用的选择器
        time_ago_tag = soup.find('faceplate-timeago')
        if not time_ago_tag:
            # 尝试其他可能的日期标签
            time_tags = soup.find_all(['time', 'span'], attrs={'datetime': True})
            if time_tags:
                time_ago_tag = time_tags[0]
        
        if time_ago_tag:
            ts = time_ago_tag.get('ts') or time_ago_tag.get('datetime')
            if ts:
                post_date = ts.split('T')[0]  # 获取日期部分
            else:
                post_date = "日期未找到"
        else:
            post_date = "日期未找到"

        # 提取帖子标题 - 使用更多选择器
        title_tag = soup.find('h1', id=lambda id: id and id.startswith('post-title-'))
        if not title_tag:
            # 尝试其他可能的标题选择器
            title_candidates = [
                soup.find('h1', class_=re.compile(r'title|heading', re.I)),
                soup.find('h1'),  # 如果没有特定类，尝试任何h1标签
                soup.find(['h1', 'h2'], attrs={'data-testid': re.compile(r'post.*title', re.I)})
            ]
            for candidate in title_candidates:
                if candidate:
                    title_tag = candidate
                    break
        
        if title_tag:
            post_title = title_tag.text.strip()
        else:
            post_title = "标题未找到"
        
        # 提取帖子内容 - 完全重写，使用多种策略
        post_content = "内容未找到"
        
        # 策略1: 常规内容提取
        text_body_div = soup.find('div', {'slot': 'text-body'})
        if text_body_div:
            content_divs = text_body_div.find_all(['div', 'p'])
            if content_divs:
                post_content = "\n".join([div.text.strip() for div in content_divs if div.text.strip()])
        
        # 策略2: 寻找任何带特定类的内容容器
        if post_content == "内容未找到":
            content_containers = soup.find_all(['div', 'p'], class_=re.compile(r'(text|content|body|post)', re.I))
            if content_containers:
                texts = []
                for container in content_containers:
                    if len(container.text.strip()) > 30:  # 只提取足够长的文本
                        texts.append(container.text.strip())
                if texts:
                    post_content = "\n".join(texts)
        
        # 策略3: 找到帖子区域，然后提取段落
        if post_content == "内容未找到":
            post_area = soup.find('div', id=re.compile(r'post-content|post-body', re.I))
            if not post_area:
                post_area = soup.find('div', attrs={'data-testid': re.compile(r'post', re.I)})
            if post_area:
                paragraphs = post_area.find_all('p')
                if paragraphs:
                    post_content = "\n".join([p.text.strip() for p in paragraphs if p.text.strip()])
        
        # 策略4: 查找任何带有大量文本的段落
        if post_content == "内容未找到":
            paragraphs = soup.find_all('p')
            content_paragraphs = []
            for p in paragraphs:
                text = p.text.strip()
                if len(text) > 100:  # 长文本段落更可能是正文
                    content_paragraphs.append(text)
            if content_paragraphs:
                post_content = "\n".join(content_paragraphs)
        
        # 调试: 保存HTML以供分析
        if config.debug and post_content == "内容未找到":
            try:
                with open(f"{config.data_dir}/failed_extract_debug.html", "w", encoding="utf-8") as f:
                    f.write(html_content)
                logger.debug("已保存失败提取的HTML用于调试")
            except Exception as e:
                logger.debug(f"保存调试HTML失败: {e}")

        # 确保至少有一项非默认值
        if post_date != "日期未找到" or post_title != "标题未找到" or post_content != "内容未找到":
            return {
                "post_date": post_date,
                "post_title": post_title,
                "post_content": post_content,
            }
        else:
            return None
    
    @retry_request(max_retries=3, retry_delay=2)
    def fetch_post(self, url: str) -> Optional[Dict]:
        """
        获取单个帖子内容，带有重试机制
        
        Args:
            url: 帖子的URL
            
        Returns:
            包含帖子信息的字典，若获取失败则返回None
        """
        parsed_url = urlparse(url)
        path = parsed_url.path
        headers = self.headers.copy()
        headers['path'] = path
        # 随机选择一个用户代理
        headers['user-agent'] = random.choice(self.user_agents)
        
        # 增加超时设置和会话复用
        with requests.Session() as session:
            response = session.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                post_data = self.extract_post_info(response.text)
                if post_data:
                    post_data['post_url'] = url  # 添加帖子链接
                    return post_data
            return None
    
    def scrape_posts(self) -> pd.DataFrame:
        """
        爬取帖子内容并保存为DataFrame
        
        Returns:
            包含所有帖子数据的DataFrame
        """
        post_urls = self.get_post_urls()
        all_posts_data = []
        
        logger.info("开始爬取帖子详细内容...")
        for i, url in enumerate(post_urls):
            try:
                # 显示进度
                logger.info(f"正在爬取第 {i+1}/{len(post_urls)} 个帖子: {url}")
                
                # 使用带重试机制的方法获取帖子内容
                post_data = self.fetch_post(url)
                if post_data:
                    all_posts_data.append(post_data)
                else:
                    logger.warning(f"无法提取帖子信息: {url}")
                    
                # 随机延迟，避免请求过于频繁
                delay = random.uniform(1.5, 3.5)
                time.sleep(delay)
                
            except Exception as e:
                logger.error(f"爬取帖子内容时出错: {e}")
                # 出错后增加额外延迟
                time.sleep(5)
        
        # 将数据转换为 DataFrame
        if all_posts_data:
            df = pd.DataFrame(all_posts_data)
            # 保存到Excel
            df.to_excel(config.reddit_posts_file, index=False, engine='openpyxl')
            logger.info(f"所有帖子数据已导出到 {config.reddit_posts_file}")
            return df
        else:
            logger.warning("没有收集到任何帖子数据")
            return pd.DataFrame()


def run():
    """执行Reddit爬虫的主函数"""
    scraper = RedditScraper()
    df = scraper.scrape_posts()
    return len(df) > 0  # 返回是否成功爬取数据
    
    
if __name__ == "__main__":
    run()