import fitz  # PyMuPDF
import unicodedata
import pandas as pd
import re
import os

def inspect_fonts_pymupdf(pdf_path):
    doc = fitz.open(pdf_path)
    page = doc[0]  # 只提取第一页
    blocks = page.get_text("dict")["blocks"]
    result_blocks = []
    for block in blocks:
        if "lines" in block:
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"]
                    # 检查是否遇到 "Abstract"（不区分大小写）
                    if text.strip().lower() == "abstract":
                        doc.close()
                        return result_blocks  # 遇到 Abstract 后返回已收集的 blocks
                    font = span["font"]  # 字体名称
                    size = span["size"]  # 字体大小
                    flags = span["flags"]  # 字体样式（4=粗体，2=斜体）
                    location = span['bbox']
                    style = []
                    if flags & 4:
                        style.append("Bold")
                    if flags & 2:
                        style.append("Italic")
                    style_str = ", ".join(style) if style else "Regular"
                    result_blocks.append(
                        {
                            "text": text,
                            "font": font,
                            "size": size,
                            "style": style_str,
                            "location": location,
                        }
                    )
    doc.close()
    return result_blocks


def compare_alphanumeric(str1, str2):
    # 先对字符串进行规范化，分解连字（如 ﬁ -> f i）
    normalized_str1 = unicodedata.normalize('NFKD', str1)
    normalized_str2 = unicodedata.normalize('NFKD', str2)
    # 提取字母和数字，忽略其他字符
    alphanumeric1 = ''.join(
        c
        for c in normalized_str1
        if ord('0') <= ord(c) <= ord('9') or ord('a') <= ord(c.lower()) <= ord('z')
    )
    alphanumeric2 = ''.join(
        c
        for c in normalized_str2
        if ord('0') <= ord(c) <= ord('9') or ord('a') <= ord(c.lower()) <= ord('z')
    )  # 不区分大小写比较 print(alphanumeric1.lower())
    print(alphanumeric1.lower())
    print(alphanumeric2.lower())
    return alphanumeric1.lower() == alphanumeric2.lower()


def is_valid_jmlr_format(s):
    pattern = r'^\s*Journal of Machine Learning Research\s*(?:volume\s*)?(\d+\s*)?\(\d{4}\)\s*\d+-\d+\s*Submitted\s*\d{1,2}/\d{2}\s*(?:;)?\s*(?:Revised\s*(?:\d{1,2}/\d{2}\s*(?:&\s*\d{1,2}/\d{2}\s*)*)?;)?\s*Published\s*(?:\d{1,2}/\d{2}\s*)?$'
    return bool(re.match(pattern, s))


def is_valid_id(s):
    pattern = (
        r'^(?:\s*\d+\s*$|\s*(?:\d+|[\*†♢♯♭‡∗])(?:\s*,\s*(?:\d+|[\*†♢♯♭‡∗]))*\s*,?\s*$)'
    )
    return bool(re.match(pattern, s)) and not re.match(r'^\s*[\*†♢♯♭‡∗]\s*$', s)

def check_authors_aline(authors_line_list, result):
    for author_line in authors_line_list:
        if abs(result[author_line]['location'][0] - result[authors_line_list[0]]['location'][0]) > 5:
            print(result[author_line], result[authors_line_list[0]])
            return False
    return True

def check_email_location(authors_line_list, result):
    
    for author_line in authors_line_list:
        now_line = author_line
        find_email = False
        while result[author_line]['location'][3] > result[now_line]['location'][1] and now_line < len(result):
            now_line += 1
            if '@' in result[now_line]['text']:
                find_email = True
        if not find_email:
            return False

    return True

def get_editor_line(result):

    for line in range(len(result)):
        if result[line]['text'] == 'Editor:':
            return line
    return None

def get_authors_line(first_authors_line, editor_line, result):

    authors_line_list = []

    for line in range(first_authors_line , editor_line):
        if result[line]['font'] == result[first_authors_line]['font'] and result[line]['size'] == result[first_authors_line]['size']:
            authors_line_list.append(line)

    return authors_line_list

def analysis_normal_format(line, result, metadata_dict):

    editor_line = get_editor_line(result)
    if editor_line == None:
        return False, metadata_dict['title'] , 'No editor'
    
    authors_line_list = get_authors_line(line, editor_line, result)
    if authors_line_list == []:
        return False, metadata_dict['title'] , 'No authors'
    
    if check_authors_aline(authors_line_list, result) == False:
        return False, metadata_dict['title'] , 'Authors not aline'
    
    if check_email_location(authors_line_list, result) == False:
        return False, metadata_dict['title'] , 'Email location not valid'

    authors = list()

    for i,author_line in enumerate(authors_line_list):
        now_author = result[author_line]['text']
        while now_author[-1] in ['*', '†']:
            now_author = now_author[:-1]
        authors.append({'name': now_author, 'affiliation': []})
        line = author_line + 1
        # next pdf line
        while line < len(result) and result[line]['location'][1] < result[author_line]['location'][3]:
            line += 1

        while (
            line < len(result)
            and result[line]['text'] != 'Editor:'
            and (i==len(authors_line_list)-1 or line != authors_line_list[i + 1])
        ):
            if len(result[line]['text']) == 1:
                if (
                    (
                        ord(result[line]['text']) > ord('9')
                        or ord(result[line]['text']) < ord('0')
                    )
                    and (
                        ord(result[line]['text']) < ord('a')
                        or ord(result[line]['text']) > ord('z')
                    )
                    and (
                        ord(result[line]['text']) < ord('A')
                        or ord(result[line]['text']) > ord('Z')
                    )
                    and result[line]['text'] not in {' ', ',', '.', '-', '&', '(', ')' ,'/'}
                ):
                    print(f"error str : {result[line]['text']}")
                    return False, metadata_dict['title'], 'error str'
            authors[-1]['affiliation'].append(result[line]['text'])
            line += 1

    metadata_dict['authors'] = authors

    metadata_dict['editor'] = (
        result[line + 1]['text'] if line + 1 < len(result) else None
    )

    if len(metadata_dict['authors']) == 0:
        print(f"author: {metadata_dict['authors']}")
        print('authors not found ')
        return False, metadata_dict['title'], 'authors not found'

    if metadata_dict['authors'][-1]['affiliation'] == []:
        print('empty author affiliation')
        return False, metadata_dict['title'] , 'empty author affiliation'

    for author in range(len(metadata_dict['authors']) - 2, -1, -1):
        if metadata_dict['authors'][author]['affiliation'] == []:
            metadata_dict['authors'][author]['affiliation'] = metadata_dict['authors'][
                author + 1
            ]['affiliation']

    return True, metadata_dict,None


def analysis_result(pdf_name, result):
    line = 0
    # pass header
    header = result[line]['text']
    while not is_valid_jmlr_format(header) and line + 1 < len(result):
        line += 1
        header += result[line]['text']
        print(header)

    line += 1

    # 有可能没有header
    if line >= len(result):
        line = 0

    pdf_name = pdf_name[:-4] if pdf_name.endswith('.pdf') else pdf_name
    print(result)
    metadata_dict = dict()
    metadata_dict['title'] = result[line]['text']

    while line + 1 < len(result) and not compare_alphanumeric(
        metadata_dict['title'], pdf_name
    ):
        line += 1
        metadata_dict['title'] += result[line]['text']

    if line >= len(result) - 1:
        print("cannot find title")
        return False, pdf_name, 'cannot find title'

    title_line = line
    line += 1
    while result[line]['location'][1] < result[title_line]['location'][3]:
        line += 1

    metadata_dict['title'] = pdf_name

    def judge_format(line, result):
        now_str = ""
        line += 1
        while not is_valid_id(now_str) and line < len(result):
            now_str += result[line]['text']
            print(now_str)
            line += 1
        if line >= len(result):
            return False
        return True

    if judge_format(line, result):
        print('id format')
        return False, metadata_dict['title'], 'id format'
    else:
        print('normal format')
        return analysis_normal_format(line, result, metadata_dict)


if __name__ == "__main__":
    pdf_path = 'JMLR 2024'
    fail_list = []
    paper_metadata_set = []
    
    for pdf in sorted(os.listdir(pdf_path)):
        if pdf.endswith('.pdf'):
            pdf_full = os.path.join(pdf_path, pdf)
            print(f"Processing {pdf}...")
            result = inspect_fonts_pymupdf(pdf_full)
            success, pdf_metadata, info = analysis_result(pdf, result)
            if not success:
                fail_list.append((pdf_metadata, info))
                continue
            paper_metadata_set.append(pdf_metadata)
            print(pdf_metadata)

    print('success')
    print(paper_metadata_set)
    print('fail\n\n\n\n')
    print(fail_list)
    print(f'success : {len(paper_metadata_set)},fail : {len(fail_list)}')
    pd.DataFrame(paper_metadata_set).to_csv('jmlr_2024_metadata.csv', index=False)
    '''

    print(
        inspect_fonts_pymupdf(
            'JMLR 2024/Accelerated Gradient Tracking over Time-varying Graphs for Decentralized Optimization.pdf'
        )
    )
    print('\n\n\n\n')
    print(
        analysis_result(
            'Accelerated Gradient Tracking over Time-varying Graphs for Decentralized Optimization.pdf',
            inspect_fonts_pymupdf(
                'JMLR 2024/Accelerated Gradient Tracking over Time-varying Graphs for Decentralized Optimization.pdf'
            ),
        )
    )
    '''