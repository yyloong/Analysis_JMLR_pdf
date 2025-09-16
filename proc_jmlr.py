import fitz  # PyMuPDF
import unicodedata
import pandas as pd
import re
import os


def str_font_style_flags(flags):
    """
    将字体样式标志位转换为可读的字符串描述。

    Args:
        flags (int): 字体样式的位标志

    Returns:
        str: 字体样式的字符串描述, 多个样式用逗号分隔
    """
    styles = []
    # 遍历每个样式位, 检查对应的标志是否设置
    for bit_shift, style_name in enumerate(["Superscripted", "Italic", "Serifed", "Monospaced", "Bold"]):
        if (flags >> bit_shift) & 1:
            styles.append(style_name)
    if len(styles) == 0:
        styles.append("Regular")
    return ", ".join(styles)


def inspect_fonts_pymupdf(pdf_path):
    """
    检查PDF文件的第一页内容, 提取文本块的字体信息直到遇到"Abstract"。

    Args:
        pdf_path (str): PDF文件路径

    Returns:
        list: 包含文本块信息的字典列表, 每个字典包含text、location、size、style和font信息
    """

    # NOTE: https://pymupdf.readthedocs.io/en/latest/textpage.html#structure-of-dictionary-outputs

    # 打开 pdf 文件, 只提取第一页
    doc = fitz.open(pdf_path)
    page = doc[0]

    raw_blocks = page.get_text("dict")["blocks"]
    filtered_blocks = []

    for block in raw_blocks:

        if not "lines" in block:
            continue

        for line in block["lines"]:
            for span in line["spans"]:
                text = span["text"]

                # 检查是否遇到 "Abstract"（不区分大小写）
                # 遇到 "Abstract" 后立即关闭文档, 返回结果
                if text.strip().lower() == "abstract":
                    doc.close()
                    return filtered_blocks

                size = span["size"]  # 字体大小
                location = span["bbox"]  # 矩形框位置大小 (x0, y0, x1, y1)
                flags = span["flags"]  # 字体样式
                style = str_font_style_flags(flags)  # 字体样式描述
                font = span["font"]  # 字体名称

                filtered_block = {
                    "text": text,
                    "location": location,
                    "size": size,
                    "style": style,
                    "font": font,
                }

                filtered_blocks.append(filtered_block)

    # 遍历文档内容结束, 关闭文档, 返回结果
    doc.close()
    return filtered_blocks


def compare_alphanumeric(str1, str2):
    """
    比较两个字符串的字母数字部分是否相等。

    Args:
        str1 (str): 第一个字符串
        str2 (str): 第二个字符串

    Returns:
        bool: 如果两个字符串的字母数字部分相等则返回True
    """
    # 先对字符串进行规范化, 分解连字（如 ﬁ -> fi）
    normalized_str1 = unicodedata.normalize("NFKD", str1).lower()
    normalized_str2 = unicodedata.normalize("NFKD", str2).lower()
    # 提取字母和数字, 忽略其他字符
    alphanumeric1 = "".join(
        c for c in normalized_str1 if ord("0") <= ord(c) and ord(c) <= ord("9") or ord("a") <= ord(c) and ord(c) <= ord("z")
    )
    alphanumeric2 = "".join(
        c for c in normalized_str2 if ord("0") <= ord(c) and ord(c) <= ord("9") or ord("a") <= ord(c) and ord(c) <= ord("z")
    )
    return alphanumeric1 == alphanumeric2


def is_valid_jmlr_format(s):
    """
    检查字符串是否符合JMLR期刊格式要求。

    Args:
        s (str): 待检查的字符串

    Returns:
        bool: 如果符合JMLR格式则返回True
    """
    pattern = r"^\s*Journal of Machine Learning Research\s*(?:volume\s*)?(\d+\s*)?\(\d{4}\)\s*\d+-\d+\s*Submitted\s*\d{1,2}/\d{2}\s*(?:;)?\s*(?:Revised\s*(?:\d{1,2}/\d{2}\s*(?:&\s*\d{1,2}/\d{2}\s*)*)?;)?\s*Published\s*(?:\d{1,2}/\d{2}\s*)?$"
    return bool(re.match(pattern, s))


def is_valid_id(s):
    """
    检查字符串是否为有效的ID格式。

    Args:
        s (str): 待检查的字符串

    Returns:
        bool: 如果是有效的ID格式则返回True
    """
    pattern = r"^(?:\s*\d+\s*$|\s*(?:\d+|[\*†♢♯♭‡∗])(?:\s*,\s*(?:\d+|[\*†♢♯♭‡∗]))*\s*,?\s*$)"
    return bool(re.match(pattern, s)) and not re.match(r"^\s*[\*†♢♯♭‡∗]\s*$", s)


def check_authors_aline(authors_line_list, result):
    """
    检查作者行是否对齐。

    Args:
        authors_line_list (list): 作者行索引列表
        result (list): 解析结果列表

    Returns:
        bool: 如果作者行对齐则返回True
    """
    for author_line in authors_line_list:
        if abs(result[author_line]["location"][0] - result[authors_line_list[0]]["location"][0]) > 5:
            print(result[author_line], result[authors_line_list[0]])
            return False
    return True


def check_email_location(authors_line_list, result):
    """
    检查每个作者是否都有对应的email。

    Args:
        authors_line_list (list): 作者行索引列表
        result (list): 解析结果列表

    Returns:
        bool: 如果每个作者都有对应email则返回True
    """
    for author_line in authors_line_list:
        now_line = author_line
        find_email = False
        while result[author_line]["location"][3] > result[now_line]["location"][1] and now_line < len(result):
            now_line += 1
            if "@" in result[now_line]["text"]:
                find_email = True
        if not find_email:
            return False
    return True


def get_editor_line(result):
    """
    获取编辑行的索引。

    Args:
        result (list): 解析结果列表

    Returns:
        int: 编辑行的索引, 如果未找到则返回None
    """
    for line in range(len(result)):
        if result[line]["text"] == "Editor:":
            return line
    return None


def get_authors_line(first_authors_line, editor_line, result):
    """
    获取所有作者行的索引列表。

    Args:
        first_authors_line (int): 第一个作者行的索引
        editor_line (int): 编辑行的索引
        result (list): 解析结果列表

    Returns:
        list: 作者行索引列表
    """
    authors_line_list = []
    for line in range(first_authors_line, editor_line):
        if (
            result[line]["font"] == result[first_authors_line]["font"]
            and result[line]["size"] == result[first_authors_line]["size"]
        ):
            authors_line_list.append(line)
    return authors_line_list


def analysis_normal_format(line, result, metadata_dict):
    """
    分析常规格式的论文内容, 提取作者、机构和编辑信息。

    处理流程:
    1. 查找编辑行位置
    2. 获取所有作者行
    3. 检查作者行对齐和邮箱位置
    4. 处理每位作者的信息:
       - 清理作者名中的特殊字符
       - 提取机构信息
       - 处理作者机构的继承关系
    5. 保存编辑信息
    6. 进行各种有效性验证

    Args:
        line (int): 从title后的起始行号
        result (list): PDF解析出的文本块列表
        metadata_dict (dict): 存储元数据的字典
    """

    # 获取编辑行位置
    editor_line = get_editor_line(result)
    if editor_line == None:
        return False, metadata_dict["title"], "No editor"

    # 获取所有作者行,并进行格式检查
    authors_line_list = get_authors_line(line, editor_line, result)
    if authors_line_list == []:
        return False, metadata_dict["title"], "No authors"

    # 检查作者行是否左对齐
    if check_authors_aline(authors_line_list, result) == False:
        return False, metadata_dict["title"], "Authors not aline"

    # 检查每个作者是否都有对应的email
    if check_email_location(authors_line_list, result) == False:
        return False, metadata_dict["title"], "Email location not valid"

    authors = list()

    # 处理每个作者的信息
    for i, author_line in enumerate(authors_line_list):
        # 清理作者名中的特殊字符(* †)
        now_author = result[author_line]["text"]
        while now_author[-1] in ["*", "†"]:
            now_author = now_author[:-1]
        authors.append({"name": now_author, "affiliation": []})

        # 定位到作者名下方的机构信息起始位置
        line = author_line + 1
        while line < len(result) and result[line]["location"][1] < result[author_line]["location"][3]:
            line += 1

        # 收集该作者的所有机构信息,直到遇到下一个作者或Editor
        while (
            line < len(result)
            and result[line]["text"] != "Editor:"
            and (i == len(authors_line_list) - 1 or line != authors_line_list[i + 1])
        ):
            # 检查单字符是否合法
            if len(result[line]["text"]) == 1:
                if (
                    (ord(result[line]["text"]) > ord("9") or ord(result[line]["text"]) < ord("0"))
                    and (ord(result[line]["text"]) < ord("a") or ord(result[line]["text"]) > ord("z"))
                    and (ord(result[line]["text"]) < ord("A") or ord(result[line]["text"]) > ord("Z"))
                    and result[line]["text"] not in {" ", ",", ".", "-", "&", "(", ")", "/"}
                ):
                    print(f"error str : {result[line]['text']}")
                    return False, metadata_dict["title"], "error str"
            authors[-1]["affiliation"].append(result[line]["text"])
            line += 1

    metadata_dict["authors"] = authors

    # 保存编辑信息
    metadata_dict["editor"] = result[line + 1]["text"] if line + 1 < len(result) else None

    # 验证作者信息的完整性
    if len(metadata_dict["authors"]) == 0:
        print(f"author: {metadata_dict['authors']}")
        print("authors not found ")
        return False, metadata_dict["title"], "authors not found"

    if metadata_dict["authors"][-1]["affiliation"] == []:
        print("empty author affiliation")
        return False, metadata_dict["title"], "empty author affiliation"

    # 对于没有单独列出机构的作者,继承上一个作者的机构信息
    for author in range(len(metadata_dict["authors"]) - 2, -1, -1):
        if metadata_dict["authors"][author]["affiliation"] == []:
            metadata_dict["authors"][author]["affiliation"] = metadata_dict["authors"][author + 1]["affiliation"]

    return True, metadata_dict, None


def analysis_result(pdf_name, result):
    """
    分析PDF文件内容, 提取论文的元数据信息。

    处理流程:
    1. 查找并验证JMLR期刊头部信息
    2. 提取论文标题:
       - 将PDF文件名作为标题
       - 查找文本中对应的标题行
    3. 确定文档格式:
       - 通过judge_format函数判断是否为id格式
       - id格式: 作者标记为数字编号
       - normal格式: 常规的作者-机构对应格式
    4. 根据不同格式调用对应的处理函数

    Args:
        pdf_name (str): PDF文件名
        result (list): PDF解析出的文本块列表

    Returns:
        tuple: (是否解析成功, 元数据字典或标题, 错误信息)
    """

    # 从第一行开始查找JMLR期刊头部信息
    line = 0
    header = result[line]["text"]
    while not is_valid_jmlr_format(header) and line + 1 < len(result):
        line += 1
        header += result[line]["text"]
        print(header)

    line += 1

    # 若未找到header,从文件开始处理
    if line >= len(result):
        line = 0

    # 去掉pdf文件的扩展名
    pdf_name = pdf_name[:-4] if pdf_name.endswith(".pdf") else pdf_name
    print(result)
    metadata_dict = dict()

    # 提取标题文本,直到与pdf文件名匹配
    metadata_dict["title"] = result[line]["text"]
    while line + 1 < len(result) and not compare_alphanumeric(metadata_dict["title"], pdf_name):
        line += 1
        metadata_dict["title"] += result[line]["text"]

    if line >= len(result) - 1:
        print("cannot find title")
        return False, pdf_name, "cannot find title"

    # 跳过标题所占的多行
    title_line = line
    line += 1
    while result[line]["location"][1] < result[title_line]["location"][3]:
        line += 1

    metadata_dict["title"] = pdf_name

    def judge_format(line, result):
        """
        判断文档是否为id格式
        通过检查作者后是否紧跟数字id来判断

        Args:
            line (int): 当前处理行号
            result (list): PDF解析结果

        Returns:
            bool: True表示id格式, False表示常规格式
        """
        now_str = ""
        line += 1
        while not is_valid_id(now_str) and line < len(result):
            now_str += result[line]["text"]
            print(now_str)
            line += 1
        if line >= len(result):
            return False
        return True

    if judge_format(line, result):
        print("id format")
        return False, metadata_dict["title"], "id format"
    else:
        print("normal format")
        return analysis_normal_format(line, result, metadata_dict)


if __name__ == "__main__":

    pdf_path = "../JMLR 2024"

    fail_list = []
    paper_metadata_set = []

    for pdf in sorted(os.listdir(pdf_path)):
        if pdf.endswith(".pdf"):
            pdf_full = os.path.join(pdf_path, pdf)
            print(f"Processing {pdf}...")
            result = inspect_fonts_pymupdf(pdf_full)
            success, pdf_metadata, info = analysis_result(pdf, result)
            if not success:
                fail_list.append((pdf_metadata, info))
                continue
            paper_metadata_set.append(pdf_metadata)
            print(pdf_metadata)

    print("success")
    print(paper_metadata_set)
    print("fail")
    print(fail_list)
    print(f"success : {len(paper_metadata_set)},fail : {len(fail_list)}")
    pd.DataFrame(paper_metadata_set).to_csv("jmlr_2024_metadata.csv", index=False)

    # print(
    #     inspect_fonts_pymupdf(
    #         'JMLR 2024/Accelerated Gradient Tracking over Time-varying Graphs for Decentralized Optimization.pdf'
    #     )
    # )
    # print(
    #     analysis_result(
    #         'Accelerated Gradient Tracking over Time-varying Graphs for Decentralized Optimization.pdf',
    #         inspect_fonts_pymupdf(
    #             'JMLR 2024/Accelerated Gradient Tracking over Time-varying Graphs for Decentralized Optimization.pdf'
    #         ),
    #     )
    # )
