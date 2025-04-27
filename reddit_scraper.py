import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup
import re
import requests
import json
import pandas as pd
from urllib.parse import urlparse

def get_post_urls(url):
    """
    使用 Selenium 从 Reddit LocalLLaMA 版块获取帖子网址。

    Args:
        url: Reddit 版块的网址。

    Returns:
        一个包含所有帖子网址的列表。
    """
    post_urls = []

    # 配置 Chrome webdriver
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")  # 无头模式，不显示浏览器界面
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    
    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.get(url)

    try:
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

    finally:
        driver.quit()  # 关闭浏览器

    return post_urls

def extract_reddit_post_info(html_content):
    """
    从HTML内容中提取Reddit帖子信息。

    Args:
      html_content: 包含Reddit帖子HTML的字符串。

    Returns:
      一个字典，包含帖子的发布日期，帖子标题和帖子内容。
      如果无法找到任何信息，则返回None。
    """

    soup = BeautifulSoup(html_content, 'html.parser')

    # 提取发帖日期
    time_ago_tag = soup.find('faceplate-timeago')
    if time_ago_tag:
       ts = time_ago_tag.get('ts')
       if ts:
          post_date = ts.split('T')[0] # 获取日期部分
       else:
          post_date = "日期未找到"
    else:
       post_date = "日期未找到"

    # 提取帖子标题
    title_tag = soup.find('h1', id=lambda id: id and id.startswith('post-title-'))
    if title_tag:
        post_title = title_tag.text.strip()
    else:
        post_title = "标题未找到"
    
    # 提取帖子内容
    text_body_div = soup.find('div', {'slot': 'text-body'})
    if text_body_div:
       post_content_div = text_body_div.find('div', class_='md text-14')
       if post_content_div:
           post_content = ""
           for p_tag in post_content_div.find_all('p'):
             post_content += p_tag.text.strip() + "\n"
           post_content = post_content.strip()
       else:
          post_content = "内容未找到"
    else:
        post_content = "内容未找到"

    if post_date != "日期未找到" or post_title != "标题未找到" or post_content != "内容未找到":
       return {
           "post_date": post_date,
           "post_title": post_title,
           "post_content": post_content,
       }
    else:
        return None


if __name__ == '__main__':
    subreddit_url = "https://www.reddit.com/r/LocalLLaMA/"
    all_post_urls = get_post_urls(subreddit_url)

    print("找到的帖子网址:")
    for url in all_post_urls:
        print(url)
    print(f"\n共找到 {len(all_post_urls)} 个帖子。")

    all_posts_data = []
    headers = {
        'authority': 'www.reddit.com',
        'method': 'GET',
        'scheme': 'https',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-encoding': 'gzip, deflate, br, zstd',
        'accept-language': 'zh-CN,zh;q=0.9',
        'cache-control': 'max-age=0',
        'cookie': 'edgebucket=SzaOnXPmLQvwhuxO1Q; csv=2; g_state={"i_l":0}; reddit_session=eyJhbGciOiJSUzI1NiIsImtpZCI6IlNIQTI1NjpsVFdYNlFVUEloWktaRG1rR0pVd1gvdWNFK01BSjBYRE12RU1kNzVxTXQ4IiwidHlwIjoiSldUIn0.eyJzdWIiOiJ0Ml8xYmN4NGFkeTVuIiwiZXhwIjoxNzUwODI4MjcxLjIxODA4NCwiaWF0IjoxNzM1MTg5ODcxLjIxODA4NCwianRpIjoiN05DRnA1clN2eDBrN1ozaHVjYXhmaEk3aHRqQWh3IiwiY2lkIjoiY29va2llIiwibGNhIjoxNzI5NTc4NzM4MDU2LCJzY3AiOiJlSnlLamdVRUFBRF9fd0VWQUxrIiwidjEiOiIxMzM2MDQ2Mjg3NDgzMzEsMjAyNC0xMi0yNlQwNToxMToxMSxlM2VlN2VjMDQ5NmE2ZmU1OTM2ZmNhNWNhOGUzZTU5OTk4ZThjMzQwIiwiZmxvIjoyfQ.Ke7fNgKK_qdwpJr4VpTrkuGCnXx4D8A_6WNVst7tEYvnQlQm2rE4PSosYSft9gl54ovJDrmv9E8AG7DEFL6ZsFPqK-8mjEZIirtMFv8c_nZO2kr6NQZ5zIng54ukubvh3i5ekO85Itmf8EYlMUy7qkJ-sDKGJo0f-79zLHbAlE_ZIxq33CHTrRoBmzCN0nA7_6ZK0G4aMdrawOD0sOnbFLWHw_6Kob1Pno4an0B0NNIh5GZxdRra7t-NASdXa1kgYvT7Zcml4t3hZ2A9hgxfucz6Q6dYKBI0AfTQDIywWj-jKLAW23eTAjd_H4kK_HmfN1pco5jCq7p1cyvghSlHsQ; loid=000000001bcx4ady5n.2.1729578738056.Z0FBQUFBQm5iT1Z2MWtTYUtzbmpLeExESFRRdWNxUEJqNVJacjdBeHRTM01YcXVGSVpPcmJZendBMXluR1Fnb2RCbVlDQUJtR05iNmFNU2lLUzlOQnhSSlVTYWp6b2pqRVZMbFhqbm1GX2FQWk1Da3JjZjlieUZ1VUFXZi1EWThFdG1JRWV2UmR4OWk; eu_cookie={%22opted%22:true%2C%22nonessential%22:true}; token_v2=eyJhbGciOiJSUzI1NiIsImtpZCI6IlNIQTI1NjpzS3dsMnlsV0VtMjVmcXhwTU40cWY4MXE2OWFFdWFyMnpLMUdhVGxjdWNZIiwidHlwIjoiSldUIn0.eyJzdWIiOiJ1c2VyIiwiZXhwIjoxNzM2MDM4MjUzLjM2MDU3LCJpYXQiOjE3MzU5NTE4NTMuMzYwNTcsImp0aSI6Im0xRHR3MUlzWXVsNVdseFpXelg4YlBPTVN0bkFUZyIsImNpZCI6IjBSLVdBTWh1b28tTXlRIiwibGlkIjoidDJfMWJjeDRhZHk1biIsImFpZCI6InQyXzFiY3g0YWR5NW4iLCJsY2EiOjE3Mjk1Nzg3MzgwNTYsInNjcCI6ImVKeGtrZEdPdERBSWhkLUZhNV9nZjVVX20wMXRjWWFzTFFhb2szbjdEVm9jazcwN2NENHBIUDlES29xRkRDWlhncW5BQkZnVHJUREJSdVQ5bkxtM2cyaU5lOHRZc1puQ0JGbXdGRHJrbUxHc2lRUW1lSklheXhzbW9JTE55Rnl1dEdOTkxUMFFKcWhjTXJlRkhwYzJvYmtiaTU2ZEdGVzVyRHlvc1ZmbDB0akdGTFlueGpjYnF3MnB1QzZuTWtuTFF2a3NYdlRqTjlXMzl2bXpfU2EwSjhPS3F1bUIzaGxKQ0c0c2ZwaW0zZDlUazU2dEN4YTE5M3FRMnVkNjNLNTkxaXcwTzdlZjZfbHJJeG1YWTJoLUp2dDMxeS1oQTQ4OEx6UHFBRWFzNFVjWmRtUWRfbFVIVUxtZ0pHTUo0dE1JNU1ybDIzOEp0bXZUdjhidEV6OThNLUttTl96V0ROUnpDZUxRcF9IMUd3QUFfXzhRMWVUUiIsInJjaWQiOiJhUlBnQVcyU1F4THIwV0UwR2FKSkE4QkpOcEpLLUtpdVZsekd0WjlpRkVVIiwiZmxvIjoyfQ.gKFtRJfgkfVyF9NJyV_KIaBCaNDKLGBR21JI81gR6NZHO0yhyTr5uvjwk0fInO1dP_TKtbzw3V1TZ2OeC8IksevfaAeMaXx9hej1AmS9Iq0g5vbhUjopErJyZI8ZqWbl5sjfvJB4ZXkRcS8clugPQMkKsO8pIEqN4UA1FcwUY87jrK2hyIJO0Fq9FCgS1v5cl9UO5KwL6aoB_I-XW6skpLhMSA0Y-T6Du1e7qIuCneUc1YHbH0yWivdWFTlb6JsGsrdS6G3nb3pNqsAEBpZWMU_erOaCS6b-ZeSBFly3mEgodDiQqO_eibgFC1fWGrHTjQ1M6DQVoWNlWdByh_5y7w',
        'priority': 'u=0, i',
        'referer': 'https://www.google.com/',
        'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    }
    for url in all_post_urls:
        parsed_url = urlparse(url)
        path = parsed_url.path
        headers['path'] = path
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            post_data = extract_reddit_post_info(response.text)
            if post_data:
                post_data['post_url'] = url  # 添加帖子链接到数据中
                all_posts_data.append(post_data)
            else:
                print(f"无法提取帖子信息: {url}")
        else:
            print(f"请求失败，状态码：{response.status_code}，URL: {url}")

    # 将数据转换为 DataFrame
    df = pd.DataFrame(all_posts_data)

    # 导出到 Excel
    excel_file = "reddit_posts.xlsx"
    df.to_excel(excel_file, index=False, engine='openpyxl')
    print(f"所有帖子数据已导出到 {excel_file}")