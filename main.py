import subprocess
import os

def run_script(script_path):
    """运行指定的 Python 脚本"""
    try:
        print(f"正在运行 {script_path}...")
        subprocess.run(["python", script_path], check=True)
        print(f"{script_path} 运行完成。\n")
    except subprocess.CalledProcessError as e:
        print(f"运行 {script_path} 时出错: {e}")
        exit(1)  # 遇到错误直接退出

if __name__ == "__main__":
    # 确保脚本文件存在
    reddit_scraper_path = "reddit_scraper.py"
    data_cleaner_path = "data_cleaner.py"
    summarizer_path = "summarizer.py"

    if not all(os.path.exists(path) for path in [reddit_scraper_path, data_cleaner_path, summarizer_path]):
        print("错误：请确保所有脚本文件都存在。")
        exit(1)

    # 运行脚本
    run_script(reddit_scraper_path)
    run_script(data_cleaner_path)
    run_script(summarizer_path)

    print("日报生成完成！")