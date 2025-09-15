1. 标题不一定能提取到同一个块中
2. 作者后面可能跟着1, 2, 3或者*, †等
3. 可能没有Journal, submmited这一行
4. ~~copyright符号识别可能有异常~~
5. 有时候会出现如果两个作者单位完全相同时只在后一个作者下面标注 (这种大概率被识别到同一个块中)
6. 正常的格式下有小概率两个作者的信息被识别到一个块中
7. 可能所有作者都没有邮箱也可能部分作者有邮箱 (如果这种情况和情况6一起出现会比较难处理, 因为无法判断邮箱后面跟着的是下一个作者还是机构, 不过目前还没看到这种情况)
8. 需要判断一些作者不是按照逐行列举的特殊格式, 以及一些前一半按行列举后面直接连起来的的格式

批量处理脚本

```bash
#!/bin/bash

# 定义论文目录
PAPERS_DIR="../jmlr_2024/main_track"

# 定义输出文件
OUTPUT_FILE="combine.txt"

# 清空或创建输出文件
> "$OUTPUT_FILE"

# 遍历目录中的所有 PDF 文件
for pdf in $PAPERS_DIR/*.pdf; do
    if [ -f "$pdf" ]; then
        echo "Processing $pdf..."
        echo -e "\n\n=== Processing $pdf ===\n" >> "$OUTPUT_FILE"
        python proc_jmlr_lite.py --pdf_path "$pdf" >> "$OUTPUT_FILE" 2>/dev/null
        if [ $? -eq 0 ]; then
            echo "Successfully processed $pdf"
        else
            echo "Error processing $pdf"
        fi
    else
        echo "No PDF files found in $PAPERS_DIR"
        exit 1
    fi
done

echo "All PDFs processed. Combined text saved to $OUTPUT_FILE"

```
