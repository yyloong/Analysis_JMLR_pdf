import os
import json
import pandas as pd
from openai import OpenAI

def get_area(locations):
    results = []
    client = OpenAI(
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    # 使用 system role 设置情景
    messages = [
        {
            "role": "system",
            "content": "你是一个地理信息专家，擅长根据机构名称查询其所在地区（国家或特别行政区）。请根据用户输入的机构名称，返回其所在地区的中文名和英文名，格式为“地区: {地区中文名} {地区英文名}”,严格按照格式输出,并使用ISO 3166-1 Alpha2来表示。例如，输入“Google DeepMind”，返回“地区: 英国 GB”。如果无法确定地区，必须返回“地区: 未知 Unknown”,确保结果的正确性。请仅返回格式化的结果，不要包含其他说明,对于多个机构请只返回第一个机构的地区。",
        }
    ]

    # 示例输入
    
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
        assert result is not None
        print(result)
        results.append(result)
        # 提取并打印token使用情况
        usage = completion.usage
        print(f"Token Usage: Prompt Tokens: {usage.prompt_tokens}, Completion Tokens: {usage.completion_tokens}, Total Tokens: {usage.total_tokens}")
        print('---')
    return results
    

for i in [2020,2021,2022,2023,2024]:
    df = pd.read_csv(f'jmlr_{i}_metadata.csv')
    df1 = pd.read_csv(f'jmlr_{i}_qwen_seperated.csv')
    assert len(df)==len(df1)
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

    results = get_area(locations) 
    df1['area'] = results
    df1.to_csv(f'jmlr_{i}_key_metadata.csv', index=False)