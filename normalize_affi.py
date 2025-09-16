import os
from openai import OpenAI
import json
import pandas as pd

def seperate(locations):
    client = OpenAI(
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    results = []
    # 使用 system role 设置情景
    messages = [
        {
            "role": "system",
            "content": "你是一个机构识别家，用户输入一些机构名称,你需要识别出这些机构,每个机构只需要识别出整体名称，不需要具体到部门,比如只需要university而不需要department,为实现批量处理，请严格按照\"机构 :{机构名称}\"的格式输出一行,如有多个机构必须只反回第一个,不要加入其他内容,此外，请小心识别机构的归属关系和并列关系(and,&b表示并列\",\"通常表示归属关系),比如hosipital,school可能属于某个university",
        }
    ]
    for location in locations:
        print(f"Processing: {location}")
        # 在 messages 中添加用户输入
        user_message = {"role": "user", "content": f"输入: {location}"}
        completion = client.chat.completions.create(
            model="qwen-plus",
            messages=messages + [user_message],  # 合并 system 和 user 消息
            extra_body={"enable_thinking": False},
        )
        # 提取返回结果
        result = completion.choices[0].message.content
        print(result)
        results.append(result)
        # 提取并打印token使用情况
        usage = completion.usage
        print(
            f"Token Usage: Prompt Tokens: {usage.prompt_tokens}, Completion Tokens: {usage.completion_tokens}, Total Tokens: {usage.total_tokens}"
        )
        print('---')
    return results


# 输入字符串
for i in [2020,2021,2022,2023,2024]:
    df = pd.read_csv(f'jmlr_{i}_metadata.csv')
    authors = df['authors'].tolist()
    locations = []
    for input_str in authors:
        input_str = input_str.replace("'", '"')  # 替换单引号为双引号，符合JSON格式

        # 解析JSON字符串
        authors = json.loads(input_str)

        # 提取第一个作者的affiliation
        first_author_affiliation = authors[0]['affiliation']

        # 打印结果
        print(first_author_affiliation)
        str_first_affiliation = ','.join(first_author_affiliation)
        print(str_first_affiliation)

        locations.append(str_first_affiliation)

    results = seperate(locations) 
    pd.DataFrame({'location': df['title'].tolist()[:len(results)], 'seperated': results}).to_csv(f'jmlr_{i}_qwen_seperated.csv', index=False)