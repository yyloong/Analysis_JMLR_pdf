import traceback

import toml

toml_paths = [
    "jmlr_v26.toml",
    "jmlr_v25.toml",
    "jmlr_v24.toml",
    "jmlr_v23.toml",
    "jmlr_v22.toml",
    "jmlr_v21.toml",
]

total_count = 0
main_count = 0
mloss_count = 0

for toml_path in toml_paths:
    try:
        with open(toml_path, "r", encoding="utf-8") as f:
            data = toml.load(f)
            papers = data.get("papers", [])
            total_count += len(papers)

            for paper in papers:
                if paper.get("is_mloss", False):
                    mloss_count += 1

    except Exception as e:
        print(f"处理 {repr(toml_path)} 失败: {repr(e)}")
        traceback.print_exc()

main_count = total_count - mloss_count

print(f"总论文数: {total_count}")
print(f"Main Track 论文数: {main_count} ({(main_count/total_count)*100:.2f}%)")
print(f"MLOSS 论文数: {mloss_count} ({(mloss_count/total_count)*100:.2f}%)")
