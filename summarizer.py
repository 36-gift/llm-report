import os
import google.generativeai as genai
import pandas as pd
import random

# 配置 Gemini API 密钥
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

# 创建模型
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

model = genai.GenerativeModel(
    model_name="gemini-2.0-flash-exp",
    generation_config=generation_config,
    system_instruction="请用汉语交流，不要用英语",
)

def summarize_and_save_variable_batch(excel_file, output_txt_file, prompt_template):
    """
    读取 Excel 文件，使用 Gemini API 每批处理 5-10 行生成摘要，并将结果保存到 txt 文件。

    参数:
        excel_file (str): 输入的 Excel 文件路径。
        output_txt_file (str): 输出的 txt 文件路径。
        prompt_template (str): 用于生成摘要的 prompt 模板。
    """

    try:
        df = pd.read_excel(excel_file)
    except FileNotFoundError:
        print(f"错误：找不到文件 {excel_file}。")
        return
    except Exception as e:
        print(f"读取文件出错: {e}")
        return

    try:
        with open(output_txt_file, "w", encoding="utf-8") as f:
            i = 0
            while i < len(df):
                batch_size = random.randint(5, 10) # 随机生成5-10之间的batch_size
                batch = df.iloc[i:min(i + batch_size, len(df))]
                messages = []
                for index, row in batch.iterrows():
                    title = row["post_title"]
                    content = row["post_content"]
                    messages.append(f"标题：{title}\n内容：{content}")
                
                batch_message = "\n\n".join(messages)
                prompt = prompt_template.format(message=batch_message)

                chat_session = model.start_chat(history=[])
                try:
                    response = chat_session.send_message(prompt)
                    if response and response.text:
                        f.write(f"摘要 for Rows {i + 2} to {min(i + batch_size + 1, len(df)+1)}:\n") # 加2 是因为行索引从0开始，同时第一行是列名
                        f.write(response.text + "\n\n")
                    else:
                        f.write(f"无法生成摘要 for Rows {i + 2} to {min(i + batch_size + 1, len(df)+1)}\n\n")
                        print(f"无法生成摘要 for Rows {i + 2} to {min(i + batch_size + 1, len(df)+1)}")
                except Exception as e:
                    f.write(f"摘要生成错误 for Rows {i + 2} to {min(i + batch_size + 1, len(df)+1)}: {e}\n\n")
                    print(f"摘要生成错误 for Rows {i + 2} to {min(i + batch_size + 1, len(df)+1)}: {e}")
                i += batch_size

        print(f"成功生成摘要并保存到 {output_txt_file}。")
    except Exception as e:
        print(f"保存文件出错: {e}")

if __name__ == "__main__":
    input_excel_file = "cleaned_reddit_posts.xlsx"  # 替换为你的输入文件路径
    output_txt_file = "summaries.txt"  # 替换为你的输出 txt 文件路径
    
    prompt_template = """
    what you see now is the news in reddit comments, i got some of posts recently;
    please get a summary for these content, you should follow such structure;

    Big things happening with large language models:
    Some practical tips：
    Other things：

    Remember, all your classifications and summaries should be based on the materials I provide you. Please be faithful to the original text and avoid adding non-existent events.
    Word count requirement: 300 words or more
    {message}
    """ # 在这里编写你的 prompt

    summarize_and_save_variable_batch(input_excel_file, output_txt_file, prompt_template)