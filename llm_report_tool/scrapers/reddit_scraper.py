"""
Reddit爬虫模块，负责从Reddit抓取相关帖子信息
"""
import time
import re
import requests
from urllib.parse import urlparse
from typing import List, Dict, Optional, Any, Union, Callable
from bs4.element import Tag
import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import platform
import traceback
from ..utils.config import config, logger
import html
import json
from pathlib import Path
import hashlib
import functools # 新增导入 functools

# 添加重试装饰器
def retry_request(max_retries=3, retry_delay=2, allowed_exceptions=(requests.RequestException, ConnectionError)):
    """重试请求装饰器，当请求失败时自动重试"""
    def decorator(func):
        # 使用 functools.wraps 保留原函数的元数据
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            last_exception = None
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except allowed_exceptions as e:
                    retries += 1
                    last_exception = e
                    # 使用指数退避增加等待时间
                    wait_time = retry_delay * (2 ** (retries - 1))
                    # 获取当前日志记录器的名称
                    logger_instance = getattr(args[0], 'logger', logger) if args else logger
                    logger_instance.warning(f"请求函数 {func.__name__} 失败 (第 {retries}/{max_retries} 次尝试): {e}. 等待 {wait_time:.1f} 秒后重试...")
                    time.sleep(wait_time)
            # 如果所有重试都失败，记录错误并重新抛出最后一个异常
            logger_instance.error(f"函数 {func.__name__} 在 {max_retries} 次重试后彻底失败.")
            if last_exception:
                raise last_exception
            # 如果没有捕获到异常但循环结束了（理论上不太可能），返回 None 或抛出通用错误
            return None # 或者 raise RuntimeError(f"{func.__name__} failed after {max_retries} retries without specific exception.")
        return wrapper
    return decorator

class RedditScraper:
    """Reddit爬虫类，用于爬取指定subreddit的帖子"""
    
    def __init__(self, subreddit_url: Optional[str] = None):
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
        # 设置当天日期，用于筛选帖子
        self.today = datetime.now().date()
        # 设置爬取开始时间范围（前24小时）
        self.day_ago = self.today - timedelta(days=1)
        # 添加日志记录当前时间范围
        logger.info(f"设置爬取时间范围: {self.day_ago} 至 {self.today}")
    
    def get_post_urls(self) -> List[str]:
        """
        获取Reddit帖子的URL列表，筛选当天发布的所有帖子
        
        Returns:
            包含当天发布的所有帖子URL的列表
        """
        # 首先尝试使用API直接获取帖子，这种方式更可靠
        logger.info(f"尝试使用API直接获取{self.subreddit_url}的帖子...")
        posts_data = self._get_posts_by_requests()
        if posts_data:
            recent_urls = [post['url'] for post in posts_data if 'url' in post]
            logger.info(f"通过API获取了 {len(recent_urls)} 个当天帖子")
            if recent_urls:  # 只要有获取到帖子就返回，不设置最低数量限制
                return recent_urls
            else:
                logger.warning(f"通过API未获取到当天帖子，将尝试使用浏览器爬取")
        else:
            logger.warning("API请求未返回有效数据，将尝试使用浏览器爬取")
            
        # 如果API获取失败或获取的帖子不足，则使用Selenium
        post_urls = []
        post_dates = {}  # 存储帖子URL及其对应的日期
        recent_urls = []  # 存储当天的帖子URL
        driver = None
        
        logger.info(f"开始爬取 {self.subreddit_url} 的帖子，筛选日期范围: {self.day_ago} 至 {self.today}...")
        
        try:
            # 配置 Chrome webdriver
            from selenium import webdriver
            chrome_options = webdriver.ChromeOptions()
            chrome_options.add_argument("--headless")  # 无头模式
            chrome_options.add_argument(
                f"--user-agent={random.choice(self.user_agents)}"
            )
            # 添加额外选项提高稳定性
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            
            # 检测系统平台并相应调整WebDriver设置
            system_platform = platform.system()
            if system_platform == "Windows":
                try:
                    # 对于Windows，尝试使用更兼容的方法
                    # 使Chrome自动匹配合适的驱动
                    chrome_options.add_argument("--remote-allow-origins=*")
                    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
                    chrome_options.add_experimental_option("detach", True)
                    
                    # 尝试使用undetected_chromedriver替代方法
                    try:
                        from selenium import webdriver
                        driver = webdriver.Chrome(options=chrome_options)
                    except Exception as e:
                        logger.warning(f"Chrome浏览器驱动程序不可用: {e}")
                        # 使用requests替代获取数据而不是Selenium
                        logger.info("将改用requests直接请求数据而非使用浏览器")
                        # 模拟直接通过API获取帖子数据
                        posts_data = self._get_posts_by_requests()
                        if posts_data:
                            logger.info(f"通过API获取了 {len(posts_data)} 个帖子")
                            # 将帖子URL添加到recent_urls
                            for post in posts_data:
                                if 'url' in post and post['url'] not in recent_urls:
                                    recent_urls.append(post['url'])
                            return recent_urls
                        else:
                            logger.warning("API请求未返回有效数据")
                            # 因为没有获取到数据，所以返回空列表
                            return []
                except Exception as e:
                    logger.error(f"ChromeDriver加载失败: {e}")
                    # 使用requests替代获取数据而不是Selenium
                    logger.info("将改用requests直接请求数据而非使用浏览器")
                    return []
            else:
                # 对于其他系统使用标准设置
                try:
                    service = ChromeService(ChromeDriverManager().install())
                    driver = webdriver.Chrome(service=service, options=chrome_options)
                except Exception as e:
                    logger.error(f"ChromeDriver加载失败: {e}")
                    return []
            
            driver.get(self.subreddit_url)
            
            logger.info("已打开浏览器，开始滚动页面获取帖子...")
            
            # 设置最大滚动次数，防止无限滚动
            max_scrolls = 100
            scrolls = 0
            no_new_posts_count = 0
            last_posts_count = 0
            
            while scrolls < max_scrolls:
                # 向下滚动页面
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(3)  # 等待页面加载

                # 提取当前页面的帖子链接和时间
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                articles = soup.find_all('article', class_=re.compile(r'w-full m-0'))
                
                for article in articles:
                    post_link = article.find('a', attrs={'slot': 'full-post-link'})
                    if post_link and isinstance(post_link, Tag) and post_link.has_attr('href'):
                        relative_url = post_link['href']
                        full_url = f"https://www.reddit.com{relative_url}"
                        
                        if full_url not in post_urls:
                            post_urls.append(full_url)
                            
                            # 提取帖子日期信息
                            time_tag = article.find('faceplate-timeago')
                            if isinstance(time_tag, Tag) and time_tag.has_attr('ts'):
                                try:
                                    ts = time_tag['ts']
                                    if isinstance(ts, list):
                                        ts = ts[0] if ts else ""
                                    if ts and isinstance(ts, str) and ts.isdigit():
                                        post_date = datetime.fromtimestamp(int(ts)).date()
                                        post_dates[full_url] = post_date
                                        
                                        # 检查是否为当天发布的帖子
                                        if self.day_ago <= post_date <= self.today:
                                            if full_url not in recent_urls:
                                                recent_urls.append(full_url)
                                except (ValueError, TypeError) as e:
                                    logger.warning(f"解析时间戳出错: {e}")
                
                # 检查是否有新帖子被添加
                if len(post_urls) == last_posts_count:
                    no_new_posts_count += 1
                else:
                    no_new_posts_count = 0
                    last_posts_count = len(post_urls)
                
                # 如果连续5次滚动没有新帖子，认为已经到达底部
                if no_new_posts_count >= 5:
                    logger.info("连续多次滚动未发现新帖子，认为已达到底部")
                    break
                
                scrolls += 1
                logger.info(f"已爬取 {len(post_urls)} 个帖子URL，其中当天发布的有 {len(recent_urls)} 个")
                
            logger.info(f"爬取完成，共获取 {len(post_urls)} 个帖子URL")
            logger.info(f"当天发布的帖子数量: {len(recent_urls)}")
            
            # 如果当天没有获取到任何帖子，则填充近期帖子
            if not recent_urls:
                logger.warning(f"未获取到当天发布的帖子，将添加近期发布的帖子")
                
                # 按日期排序所有帖子
                sorted_posts = sorted(
                    [(url, date) for url, date in post_dates.items()],
                    key=lambda x: x[1],
                    reverse=True
                )
                
                # 添加近期发布的帖子，确保至少有内容可分析
                for url, date in sorted_posts[:10]:  # 最多添加10个近期帖子
                    recent_urls.append(url)
                    logger.info(f"添加了日期为 {date} 的近期帖子")
            
            return recent_urls
                
        except Exception as e:
            logger.error(f"爬取帖子URL时出错: {e}")
            logger.error(traceback.format_exc())
            return []
        finally:
            if driver:
                try:
                    driver.quit()  # 确保关闭浏览器
                except Exception as e:
                    logger.error(f"关闭浏览器时出错: {e}")
            
        logger.info(f"共爬取到 {len(recent_urls)} 个当天发布的帖子URL")
        return recent_urls
    
    @staticmethod
    def extract_post_info(html_content: str) -> Optional[Dict]:
        """
        从HTML内容中提取Reddit帖子信息 (仅标题、内容)
        
        Args:
            html_content: 帖子页面的HTML内容
            
        Returns:
            包含帖子信息的字典 (标题、内容)，若提取失败则返回None
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        post_title = "标题未找到"
        post_content = "内容未找到"

        # 安全地提取标签的文本内容
        def safe_get_text(element) -> str:
            if element and isinstance(element, Tag) and hasattr(element, 'text'):
                return element.text.strip()
            return ""

        # 安全地获取属性值
        def safe_get_attr(element, attr: str) -> Optional[str]:
            if element and isinstance(element, Tag) and element.has_attr(attr):
                value = element[attr]
                if isinstance(value, list):
                    return value[0] if value else None
                return value
            return None
        
        # --- 提取帖子标题 --- (保留)
        def title_id_filter(id_val: Any) -> bool:
            return id_val and isinstance(id_val, str) and id_val.startswith('post-title-')
            
        title_tag = soup.find('h1', id=title_id_filter)        
        title_text = safe_get_text(title_tag)
        if title_text:
            post_title = title_text
        else:
            # 尝试其他可能的标题选择器
            title_candidates = [
                soup.find('h1', class_=re.compile(r'title|heading', re.I)),
                soup.find('h1'),  # 如果没有特定类，尝试任何h1标签
                soup.find(['h1', 'h2'], attrs={'data-testid': re.compile(r'post.*title', re.I)}),
                soup.find('title')  # 如果其他都失败，使用页面标题
            ]
            for candidate in title_candidates:
                candidate_text = safe_get_text(candidate)
                if candidate_text:
                    # 如果使用页面标题，尝试清理掉网站名称部分
                    if candidate and hasattr(candidate, 'name') and candidate.name == 'title':
                        candidate_text = candidate_text.replace(' - Reddit', '').strip()
                    post_title = candidate_text
                    break
        
        # --- 提取帖子内容 --- (保留)
        text_body_div = soup.find('div', attrs={'slot': 'text-body'})
        if isinstance(text_body_div, Tag):
            content_divs = text_body_div.find_all(['div', 'p'])
            if content_divs:
                post_content = "\n".join([safe_get_text(div) for div in content_divs if safe_get_text(div)])
        
        # --- 调试: 保存HTML以供分析 --- (修改调试条件，不再检查 post_images)
        if config.debug and post_content == "内容未找到": 
            try:
                # 确保 data_dir 存在
                Path(config.data_dir).mkdir(parents=True, exist_ok=True)
                # 使用更独特的文件名，例如基于时间戳或 URL hash
                url_hash = hashlib.md5(html_content[:1000].encode()).hexdigest()[:8]
                debug_filename = Path(config.data_dir) / f"failed_extract_{url_hash}_{datetime.now().strftime('%Y%m%d%H%M%S')}.html"
                with open(debug_filename, "w", encoding="utf-8") as f:
                    f.write(html_content)
                logger.debug(f"已保存失败提取的HTML用于调试: {debug_filename}")
            except Exception as e:
                logger.debug(f"保存调试HTML失败: {e}")

        if not post_content:
            post_content = "内容未找到"

        # 确保至少有一项非默认值
        if post_title != "标题未找到" or post_content != "内容未找到":
            return {
                "post_title": post_title,
                "post_content": post_content,
            }
        else:
            # 如果所有字段都是默认值，则认为提取失败
            logger.warning("提取帖子信息失败：标题和内容均未找到有效值。")
            return None
    
    @retry_request(max_retries=3, retry_delay=3, allowed_exceptions=(requests.RequestException, ConnectionError, requests.exceptions.SSLError))
    def _extract_post_info_via_json(self, url: str) -> Optional[Dict]:
        """
        使用 Reddit JSON API 后备提取帖子信息 (仅标题、内容)。
        增加了重试逻辑以处理包括SSLError在内的临时网络问题。
        """
            # 构造 JSON API 地址
            api_url = url.rstrip('/') + '.json'
            headers = {'User-Agent': random.choice(self.user_agents), 'Accept': 'application/json'}
        response = requests.get(api_url, headers=headers, timeout=20)
        response.raise_for_status() # 如果状态码不是 2xx，则抛出异常
            data = response.json()

        try:
            # Reddit JSON 返回列表，首项包含帖子详情
            post_info = data[0]['data']['children'][0]['data']
            title = post_info.get('title', '') or ''
            content = post_info.get('selftext', '') or ''
            logger.debug(f"成功通过 JSON API 解析帖子信息: {api_url}")
            return {
                'post_title': title,
                'post_content': content,
            }
        except (IndexError, KeyError, TypeError) as e:
            logger.error(f"解析 JSON API 返回数据失败 ({api_url}): {e}", exc_info=True)
            return None

    @retry_request(max_retries=3, retry_delay=2)
    def fetch_post(self, url: str) -> Optional[Dict]:
        """
        获取单个帖子内容 (仅标题、内容)，带有重试机制。
        尝试 JSON API 和 HTML 两种方式获取内容并合并。
        """
        parsed_url = urlparse(url)
        path = parsed_url.path
        headers = self.headers.copy()
        headers['path'] = path
        headers['user-agent'] = random.choice(self.user_agents)

        json_info = None
        html_info = None
        final_post_data = {}

        # 尝试通过 JSON API 获取信息
        try:
        json_info = self._extract_post_info_via_json(url)
        except Exception as e:
            logger.warning(f"调用 _extract_post_info_via_json 失败 ({url}): {e}", exc_info=True)

        # 尝试通过 HTML 获取信息
        try:
        with requests.Session() as session:
                response = session.get(url, headers=headers, timeout=20) # 增加 HTML 请求超时
                response.raise_for_status() # 检查 HTML 请求是否成功
                html_info = self.extract_post_info(response.text)
        except requests.RequestException as e:
            logger.warning(f"HTML 请求失败 ({url}): {e}")
        except Exception as e:
            logger.warning(f"调用 extract_post_info 失败 ({url}): {e}", exc_info=True)

        # 合并信息：优先 JSON，HTML 补充
                if json_info:
            final_post_data.update(json_info)
        
        if html_info:
            if not json_info or html_info.get('post_title') != "标题未找到":
                final_post_data['post_title'] = html_info.get('post_title', final_post_data.get('post_title'))
            if not json_info or html_info.get('post_content') != "内容未找到":
                final_post_data['post_content'] = html_info.get('post_content', final_post_data.get('post_content'))

        # 检查是否至少提取到了一些信息 (标题或内容)
        if not final_post_data.get('post_title', "标题未找到") != "标题未找到" and \
           not final_post_data.get('post_content', "内容未找到") != "内容未找到":
            logger.warning(f"未能为 {url} 提取到任何有效内容（标题、正文）")
            return None
            
        final_post_data['post_url'] = url
        return final_post_data
    
    def scrape_posts(self) -> pd.DataFrame:
        """
        爬取帖子内容并保存为DataFrame
        
        Returns:
            包含所有帖子数据的DataFrame
        """
        post_urls = self.get_post_urls()
        all_posts_data = []
        
        # 如果没有获取到任何URL，使用直接API请求作为备用方案
        if not post_urls:
            logger.warning("没有获取到任何帖子URL，尝试直接通过API获取帖子内容")
            try:
                # 使用多个LLM相关的subreddit
                reddit_urls = [
                    "https://www.reddit.com/r/LocalLLaMA.json",
                    "https://www.reddit.com/r/MachineLearning.json",
                    "https://www.reddit.com/r/ChatGPT.json",
                    "https://www.reddit.com/r/artificial.json",
                    "https://www.reddit.com/r/OpenAI.json",
                    "https://www.reddit.com/r/GenerativeAI.json"
                ]
                
                for url in reddit_urls:
                    try:
                        logger.info(f"尝试从 {url} 获取帖子...")
                        headers = {
                            'User-Agent': random.choice(self.user_agents),
                            'Accept': 'application/json'
                        }
                        
                        # 获取多页数据
                        after_token = None
                        max_pages = 15  # 每个subreddit最多获取15页，确保收集足够的帖子
                        
                        for page in range(max_pages):
                            page_url = url if after_token is None else f"{url}?after={after_token}"
                            logger.info(f"获取 {url} 第 {page+1} 页数据")
                            
                            response = requests.get(page_url, headers=headers, timeout=15)
                            if response.status_code != 200:
                                logger.warning(f"API请求失败，状态码: {response.status_code}")
                                break
                                
                            data = response.json()
                            found_new_posts = False
                            
                            if 'data' in data and 'children' in data['data']:
                                for post_data in data['data']['children']:
                                    if 'data' in post_data:
                                        post_info = post_data['data']
                                        # 提取需要的字段
                                        created_utc = post_info.get('created_utc')
                                        if created_utc:
                                            post_date = datetime.fromtimestamp(created_utc).date()
                                            # 只收集一天内的帖子
                                            if self.day_ago <= post_date <= self.today:
                                                found_new_posts = True
                                                # 直接处理帖子内容
                                                all_posts_data.append({
                                                    'post_date': post_date.isoformat(),
                                                    'post_title': post_info.get('title', ''),
                                                    'post_content': post_info.get('selftext', ''),
                                                    'post_url': f"https://www.reddit.com{post_info.get('permalink', '')}",
                                                })
                            
                            # 获取下一页Token
                            after_token = data.get('data', {}).get('after')
                            logger.info(f"已从 {url} 收集 {len(all_posts_data)} 条帖子")
                            
                            # 如果没有下一页或没有找到新帖子，则跳出循环
                            if after_token is None or not found_new_posts:
                                break
                                
                            # 随机延迟，避免请求过于频繁
                            time.sleep(random.uniform(1, 3))
                        
                    except Exception as e:
                        logger.error(f"从 {url} 获取帖子出错: {e}")
                
                # 如果收集到了帖子，直接跳到保存阶段
                if all_posts_data:
                    logger.info(f"通过API直接获取了 {len(all_posts_data)} 条帖子内容")
                    df = pd.DataFrame(all_posts_data)
                    df.to_excel(config.reddit_posts_file, index=False, engine='openpyxl')
                    logger.info(f"所有帖子数据已导出到 {config.reddit_posts_file}")
                    return df
            except Exception as e:
                logger.error(f"备用方案获取帖子时出错: {e}")
        
        logger.info("开始爬取帖子详细内容...")
        for i, url in enumerate(post_urls):
            try:
                # 显示进度
                logger.info(f"正在爬取第 {i+1}/{len(post_urls)} 个帖子: {url}")
                
                # 使用带重试机制的方法获取帖子内容
                post_data = self.fetch_post(url)
                if post_data:
                    # 直接为帖子数据添加运行日期
                    post_data['post_date'] = self.today.isoformat()
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
        
        # 将所有帖子数据导出到Excel
        df = pd.DataFrame(all_posts_data)
        
        # 添加一列用于标记数据来源
        df['source'] = 'reddit'
        df['scrape_date'] = datetime.now().date().isoformat()
        
        df.to_excel(config.reddit_posts_file, index=False, engine='openpyxl')
        logger.info(f"成功爬取 {len(df)} 条帖子数据 (仅标题和内容)，已导出到 {config.reddit_posts_file}")
        return df

    def _get_posts_by_requests(self) -> List[Dict]:
        """
        使用requests直接获取Reddit帖子数据，作为Selenium的备选方案
        
        Returns:
            包含帖子数据的列表
        """
        try:
            # 模拟请求Reddit的JSON API
            headers = {
                'User-Agent': random.choice(self.user_agents),
                'Accept': 'application/json'
            }
            
            # 将subreddit URL转为JSON API URL，增加请求数量
            api_url = f"{self.subreddit_url}.json?limit=100"
            logger.info(f"请求API: {api_url}")
            
            posts = []
            next_token = None
            max_pages = 30  # 最多获取30页数据，确保能收集到足够的帖子
            total_retrieved = 0
            current_date_posts = 0
            
            for page in range(max_pages):
                # 添加分页参数
                page_url = api_url if next_token is None else f"{api_url}&after={next_token}"
                logger.info(f"获取第 {page+1} 页数据: {page_url}")
                
                response = requests.get(page_url, headers=headers, timeout=15)
                if response.status_code != 200:
                    logger.warning(f"API请求失败，状态码: {response.status_code}")
                    break
                    
                data = response.json()
                posts_added = 0
                total_in_page = 0
                
                # 处理返回的数据
                if 'data' in data and 'children' in data['data']:
                    total_in_page = len(data['data']['children'])
                    for post_data in data['data']['children']:
                        if 'data' in post_data:
                            post_info = post_data['data']
                            # 提取需要的字段
                            created_utc = post_info.get('created_utc')
                            if created_utc:
                                post_date = datetime.fromtimestamp(created_utc).date()
                                # 检查日期是否在当天
                                if self.day_ago <= post_date <= self.today:
                                    posts.append({
                                        'url': f"https://www.reddit.com{post_info.get('permalink', '')}",
                                        'title': post_info.get('title', ''),
                                        'created_utc': created_utc,
                                        'post_date': post_date.isoformat()  # 添加日期字符串以便日志记录
                                    })
                                    posts_added += 1
                                    current_date_posts += 1
                
                # 获取下一页的token
                next_token = data.get('data', {}).get('after')
                total_retrieved += total_in_page
                logger.info(f"第 {page+1} 页找到 {posts_added} 个当天发布的帖子，页面总数: {total_in_page}，当天累计: {current_date_posts}，总处理: {total_retrieved}")
                
                # 如果没有下一页或者整页都没有找到符合条件的帖子，结束循环
                if next_token is None or (total_in_page > 0 and posts_added == 0):
                    logger.info(f"没有更多帖子或本页未找到符合日期范围的帖子，停止获取")
                    break
                    
                # 随机延迟，避免请求过于频繁
                time.sleep(random.uniform(1, 3))
            
            logger.info(f"API请求完成，共获取 {len(posts)} 个从 {self.day_ago} 至 {self.today} 发布的帖子")
            return posts
        except Exception as e:
            logger.error(f"通过API获取帖子时出错: {e}")
            return []

def run():
    """执行Reddit爬虫的主函数"""
    scraper = RedditScraper()
    df = scraper.scrape_posts()
    return len(df) > 0  # 返回是否成功爬取数据


def test_date_extraction():
    """测试日期提取功能"""
    from pprint import pprint
    
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
    # 如果指定测试参数，则运行测试函数
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_date_extraction()
    else:
        run()