#!/bin/bash

# 定义输出文件
OUTPUT_FILE="combine.txt"

# 清空或创建输出文件
> "$OUTPUT_FILE"

# 遍历目录中的所有 PDF 文件
for pdf in ../JMLR\ 2024/*.pdf; do
    if [ -f "$pdf" ]; then
        echo "Processing $pdf..."
        echo -e "\n\n=== Processing $pdf ===\n" >> "$OUTPUT_FILE"
        python proc_jmlr.py --pdf_path "$pdf" >> "$OUTPUT_FILE" 2>/dev/null
        if [ $? -eq 0 ]; then
            echo "Successfully processed $pdf"
        else
            echo "Error processing $pdf"
        fi
    else
        echo "No PDF files found in ../JMLR 2024"
        exit 1
    fi
done

echo "All PDFs processed. Combined text saved to $OUTPUT_FILE"