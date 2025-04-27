import pandas as pd
from datetime import datetime, timedelta

def clean_reddit_posts(excel_file, output_file):
    """
    清洗 Reddit 帖子数据，移除“内容未找到”的行以及过时的帖子。

    参数:
        excel_file (str): 输入 Excel 文件的路径。
        output_file (str): 输出 Excel 文件的路径。
    """

    try:
      df = pd.read_excel(excel_file)
    except FileNotFoundError:
        print(f"错误：找不到文件 {excel_file}。")
        return
    except Exception as e:
         print(f"读取文件出错: {e}")
         return

    # 获取当前时间
    now = datetime.now()

    # 删除 "内容未找到" 的行
    df = df[df['post_content'] != '内容未找到']

    # 将 post_date 列转换为 datetime 对象
    df['post_date'] = pd.to_datetime(df['post_date'])

    # 计算 24 小时之前的时间
    cutoff_time = now - timedelta(hours=48)

    # 删除发布时间在 24 小时之前的帖子
    df = df[df['post_date'] >= cutoff_time]

    # 保存清洗后的数据到新的 Excel 文件
    try:
      df.to_excel(output_file, index=False)
      print(f"成功清洗数据，并保存到 {output_file}。")
    except Exception as e:
      print(f"保存文件出错: {e}")

if __name__ == "__main__":
    input_excel_file = "reddit_posts.xlsx"  # 替换为你的输入文件路径
    output_excel_file = "cleaned_reddit_posts.xlsx"  # 替换为你希望的输出文件路径
    clean_reddit_posts(input_excel_file, output_excel_file)