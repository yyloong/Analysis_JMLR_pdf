from typing import TypeAlias, Optional, Union, List, Tuple, Dict, Any
from pathlib import Path

import re
import pprint
import unicodedata
import fitz  # PyMuPDF

import os
import platform
import argparse


# 用全局变量记录 ANSI 颜色转义码
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
RESET = "\033[0m"


# Windows 终端开启 ANSI 颜色转义功能
if platform.system() == "Windows":
    os.system("color")


# pieces 中每个元素的结构:
# {
#     "text": str,  # 文本内容
#     "rect": (x0: float, y0: float, x1: float, y1: float)  # 文本区块的矩形位置
# }
PiecesType: TypeAlias = List[Dict[str, Union[str, Tuple[float, float, float, float]]]]


class JMLRPDFExtractionError(Exception):
    """自定义异常类, 用于标识无法从中提取文本区块的 PDF 文件"""

    pass


class JMLRPDFParsingError(Exception):
    """自定义异常类, 用于标识无法从中提取作者信息的文本区块"""

    pass


def normalize_text(text: str) -> str:
    """
    规范化文本内容:
    1. 统一 Unicode 规范形式为 NFKD
    2. 去除首尾空白符
    3. 转义空格和换行符以外的空白符

    Args:
        text (str): 待规范化的文本内容
    Returns:
        str: 规范化后的文本内容
    """

    # 兼容性分解, 彻底分解等价的 Unicode 字符, 如将 "ﬁ" 分解为 "fi"
    text = unicodedata.normalize("NFKD", text)
    # 转义空格和换行符以外的空白符
    text = re.sub(r"\r\n", "\n", text)  # 先处理 Windows 风格换行
    text = re.sub(r"\r", "\n", text)  # 再处理 Mac 风格换行
    text = re.sub(r"\v", "\n", text)  # 垂直制表符视为换行符
    text = re.sub(r"(?u)[^\S \n]+", " ", text)  # 其他空白符视为空格
    # 去除每行首尾空白符
    text = "\n".join([line.strip() for line in text.split("\n")])
    text = text.strip()
    return text


def print_pieces(pieces: PiecesType, pdf_source: str = "") -> None:
    """
    美观打印文本区块内容

    Args:
        pieces (PiecesType): 待打印的文本区块列表
        pdf_source (str): PDF 文件来源, 用于打印调试信息
    """

    if len(pdf_source) > 0:
        print(f"{RED}--- Pieces of {repr(pdf_source)} ---{RESET}\n")
    else:
        print(f"{RED}--- Pieces ---{RESET}\n")
    for piece in pieces:
        text = piece["text"]
        x0, y0, x1, y1 = piece["rect"]
        indented_text = text.replace("\n", "\n" + " " * 16)  # 缩进换行, 保持美观
        print(f"Box rectangle:  {GREEN}({x0:.1f}, {y0:.1f}) -> ({x1:.1f}, {y1:.1f}){RESET}  # (x0, y0) -> (x1, y1)")
        print(f"Text content:   {YELLOW}{indented_text}{RESET}\n")


def coarse_filter_pieces(pieces: PiecesType, pdf_source: str = "") -> PiecesType:
    """
    粗筛文本区块, 过滤摘要和正文

    Args:
        pieces (PiecesType): 待过滤的文本区块列表
        pdf_source (str): PDF 文件来源, 用于打印调试信息
    Returns:
        PiecesType: 过滤后的文本区块列表
    """

    # "Editor" 之后, "Copyright" 之前, 除了keyword之外完全丢弃
    left_index = -1
    right_index = -1
    # 遍历 pieces, 找到 "Editor" / "Abstract" 和 "Copyright" 所在的区块索引
    for i in range(len(pieces)):
        # JMLR 格式的论文中, "Editor" 之后的内容为摘要
        if re.search(r"(?u)Editor", pieces[i]["text"], re.IGNORECASE) and left_index == -1:
            left_index = i
        elif re.search(r"(?u)Abstract", pieces[i]["text"], re.IGNORECASE) and left_index == -1:
            left_index = i - 1

        # JMLR 格式的论文中, Copyright 符号之后的内容为页脚
        if re.search(
            r"(?u)(c\u20dd)|(c\n\u20dd)|(c\u25cb)|(\u00a9)",
            pieces[i]["text"],
            re.IGNORECASE,
        ):  # type: ignore
            right_index = i
    # 如果找到了 "Editor" / "Abstract" 和 Copyright, 则进行过滤
    if left_index != -1 and right_index != -1 and left_index < right_index:
        filtered_pieces = pieces[:left_index] + pieces[right_index:]
        return filtered_pieces 
    # 否则不进行过滤, 直接返回原始 pieces, 并且打印 pieces 信息
    else:
        print(f"{RED}[!] Error: Cannot find 'Editor' / 'Abstract' and Copyright in {repr(pdf_source)}{RESET}")
        print_pieces(pieces=pieces, pdf_source=pdf_source)
        raise JMLRPDFExtractionError(f"Cannot find 'Editor' / 'Abstract' and Copyright in {repr(pdf_source)}")


def fine_filter_pieces(pieces: PiecesType, pdf_source: str = "") -> PiecesType:
    """
    精筛文本区块, 整理语义信息

    Args:
        pieces (PiecesType): 待过滤的文本区块列表
        pdf_source (str): PDF 文件来源, 用于打印调试信息
    Returns:
        PiecesType: 过滤后的文本区块列表
    """

    def parse_header(header: str = "") -> Dict[str, str]:
        """
        解析 JMLR 论文页眉, 提取卷号 (volume), 年份 (year), 页数 (n_pages), 投稿 (Submitted), 修改 (Revised), 发表 (Published) 日期

        Args:
            header (str): JMLR 论文页眉文本内容
        Returns:
            Dict[str, str]: 提取到的元信息字典, 包含 "volume", "year", "n_pages", "submitted", "revised", "published" 六个键, 所有值均为字符串
        """
        # TODO: 提取卷号 (volume), 年份 (year), 页数 (n_pages), 推断投稿 (Submitted), 修改 (Revised), 发表 (Published)日期
        # TODO: 例如 "Journal of Machine Learning Research 21 (2020) 1-37\nSubmitted 9/18; Revised 12/19; Published 9/20,第二个数字代表年份"
        # TODO: 可知  volume=21, year=2020, n_pages=37, submitted=2018.09, revised=2019.12, published=2020.09
        if len(header) == 0:
            return {
                "volume": "",
                "year": "",
                "n_pages": "",
                "submitted": "",
                "revised": "",
                "published": "",
            }
        else:
            # 定义正则表达式模式
            pattern = r"^\s*Journal of Machine Learning Research\s*(?:volume\s*)?(\d+\s*)?\((\d{4})\)\s*(\d+)[-\u2013](\d+)\s*[\r\n]*Submitted\s*(\d{1,2}/\d{1,2})\s*(?:[,;])?\s*(?:Revised\s*:?((?:\d{1,2}/\d{1,2}\s*)?);)?\s*Published\s*(\d{1,2}/\d{1,2}\s*)?$"
            match = re.match(pattern, header, re.IGNORECASE)
            if match:
                # 利用正则表达式获取信息
                volume = match.group(1).strip() if match.group(1) else ""

                year = match.group(2).strip() if match.group(2) else ""

                start_page = match.group(3).strip() if match.group(3) else ""
                end_page = match.group(4).strip() if match.group(4) else ""

                n_pages = str(int(end_page) - int(start_page) + 1) if start_page and end_page else ""

                submitted = match.group(5).strip() if match.group(5) else ""
                revised = match.group(6).strip() if match.group(6) else ""
                published = match.group(7).strip() if match.group(7) else ""

                # 处理日期逻辑
                # 提取出来的年份是两位数, 需要拼接上世纪或本世纪的前两位数字
                # 例如 9/20 -> 2020.09, 12/19 -> 2019.12, 1/5 -> 2005.01
                def year_process(year_str: str) -> str:
                    if year_str:
                        submitted_month, submitted_year = (int(x) for x in year_str.split("/"))
                        # 考虑1999这种特殊情况,先判断年份大小再拼接
                        if int(submitted_year) >= 90:
                            year_str = f"19{submitted_year:02d}.{submitted_month:02d}"
                        else:
                            year_str = f"20{submitted_year:02d}.{submitted_month:02d}"
                    return year_str

                submitted = year_process(submitted)
                revised = year_process(revised)
                published = year_process(published)

                """
                # 打印调试信息
                print(
                    f"{GREEN}[+] Info: Parsed header info from {repr(header)} in {repr(pdf_source)}:{RESET},volume={volume}, year={year}, n_pages={n_pages}, submitted={submitted}, revised={revised}, published={published}"
                )
                """

                return {
                    "volume": volume,
                    "year": year,
                    "n_pages": n_pages,
                    "submitted": submitted,
                    "revised": revised,
                    "published": published,
                }
            else:
                print(f"{YELLOW}[?] Warn: Cannot parse header info from {repr(header)} in {repr(pdf_source)}{RESET}")
                return {
                    "volume": "",
                    "year": "",
                    "n_pages": "",
                    "submitted": "",
                    "revised": "",
                    "published": "",
                }

    # 出栈第一个文本区块作为 header, 即用于标识 JMLR 论文的页眉
    if "Journal of Machine Learning Research" in pieces[0]["text"]:
        header = pieces[0]["text"]
        pieces = pieces[1:]
    # 否则打印警告信息, 并且将 header 置为空字符串
    else:
        header = ""
        print(
            f"{YELLOW}[?] Warn: The first piece does not contain 'Journal of Machine Learning Research' in {repr(pdf_source)}{RESET}"
        )

    # 解析 header 元信息
    header_info = parse_header(header=header)

    filtered_pieces = pieces
    return filtered_pieces , header_info


def parse_jmlr_pdf(pdf_path: Path, verbose: bool = True) -> PiecesType:
    """
    解析 JMLR 论文首页内容

    Args:
        pdf_path (Path): JMLR 论文 PDF 文件路径
        verbose (bool): 是否打印解析过程中的调试信息, 默认为 True
    Returns:
        PiecesType: 解析得到的文本区块列表, 每个区块包含文本内容和矩形位置
    """

    # 打开文档, 准备提取内容
    jmlr = fitz.open(pdf_path)

    # 从页面中提取文本区块的辅助函数
    def get_pieces_from_page(page: fitz.Page) -> PiecesType:
        pieces = []
        blocks = page.get_text("blocks")
        # 遍历首页区块, 请见 https://pymupdf.readthedocs.io/en/latest/textpage.html
        for block in blocks:
            x0, y0, x1, y1, text, block_no, block_type = block
            # 仅需提取文本区块, 文本区块当且仅当 b_type == 0
            if block_type != 0:
                continue
            # 正则化文本内容
            text = normalize_text(text)
            piece = {"text": text, "rect": (x0, y0, x1, y1)}
            pieces.append(piece)
        return pieces
    
    # 在文本区块列表中搜索匹配的文本内容的辅助函数
    def search_info_from_pieces(pieces: PiecesType, pattern: str) -> str:
        """
        在文本区块列表中搜索匹配的文本内容

        Args:
            pieces (PiecesType): 文本区块列表
            pattern (str): 用于搜索的正则表达式模式
        Returns:
            str: 如果找到匹配的文本内容, 则返回该内容; 否则返回 ""
        """
        for piece in pieces:
            match = re.search(pattern, piece["text"], re.IGNORECASE)
            if match:
                return piece["text"][match.start():]
        return ""

    # 先筛选keyword和editor
    first_page = jmlr.load_page(0)
    pieces = get_pieces_from_page(page=first_page)

    editor = search_info_from_pieces(pieces, r"(?u)Editor")
    if editor == "" or len(editor) < 5 or len(editor) > 100:
        print(f"{YELLOW}[?] Warn: Cannot find 'Editor' {repr(editor)} info in {repr(pdf_path)}{RESET}")
    else:
        editor = editor.split(":")[1].strip() if ":" in editor else editor.strip()
    
    keywords = search_info_from_pieces(pieces, r"(?u)Keywords?")

    if keywords == "":
        second_page = jmlr.load_page(1)
        second_pieces = get_pieces_from_page(page=second_page)
        keywords = search_info_from_pieces(second_pieces, r"(?u)Keywords?")

    if keywords == "" or len(keywords) < 8 or len(keywords) > 1000:
        print(f"{YELLOW}[?] Warn: Cannot find 'Keywords' {repr(keywords)} info in {repr(pdf_path)}{RESET}")
    else:
        keywords = keywords.split(":")[1].strip() if ":" in keywords else keywords.strip()


    # 如果没有提取到任何文本区块, 则报错
    if len(pieces) == 0:
        print(f"{RED}[!] Error: No pieces extracted from {repr(pdf_path)}{RESET}")
        raise JMLRPDFExtractionError(f"No pieces extracted from {repr(pdf_path)}")

    # 依据左上角的坐标排序区块, 保持从上到下和从左到右的顺序
    pieces.sort(key=lambda piece: (piece["rect"][1], piece["rect"][0]))

    # 粗筛文本区块, 过滤摘要和正文
    pieces = coarse_filter_pieces(pieces=pieces, pdf_source=pdf_path)

    # 精筛文本区块, 整理语义信息
    pieces , header_info = fine_filter_pieces(pieces=pieces, pdf_source=pdf_path)

    # 如果开启 verbose 模式, 打印文档区块内容
    if verbose:
        print_pieces(pieces=pieces, pdf_source=str(pdf_path))

    # 关闭文档, 返回内容
    jmlr.close()
    return pieces , header_info, editor, keywords


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse JMLR PDF metadata.")
    parser.add_argument("--pdf_path", type=Path, help="Path to the JMLR PDF file.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.pdf_path is None or not args.pdf_path.exists():
        print(f"{RED}[!] Error: Please provide a valid PDF file path using --pdf_path $PDF_PATH{RESET}")
        return

    parse_jmlr_pdf(args.pdf_path, verbose=False)


def test() -> None:
    pdf_dirs = [
        "../JMLR 2020/main_track",
        "../JMLR 2021/main_track",
        "../JMLR 2022/main_track",
        "../JMLR 2023/main_track",
        "../JMLR 2024/main_track",
    ]
    for pdf_dir in pdf_dirs:
        for pdf_name in os.listdir(pdf_dir):
            pdf_path = os.path.join(pdf_dir, pdf_name)
            try:
                parse_jmlr_pdf(pdf_path, verbose=False)
            except JMLRPDFExtractionError:
                pass
            except JMLRPDFParsingError:
                pass


if __name__ == "__main__":
    # main()
    test()
