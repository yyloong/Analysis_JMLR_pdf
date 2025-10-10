from typing import TypeAlias, Optional, Union, List, Tuple, Dict, Any
from pathlib import Path

import re
import pprint
import unicodedata
import fitz  # PyMuPDF

import os
import platform
import argparse


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
    # 去除首尾空白符
    text = text.strip()
    # 转义空格和换行符以外的空白符
    text = re.sub(r"\r\n", "\n", text)  # 先处理 Windows 风格换行
    text = re.sub(r"\r", "\n", text)  # 再处理 Mac 风格换行
    text = re.sub(r"\v", "\n", text)  # 垂直制表符视为换行符
    text = re.sub(r"(?u)[^\S \n]+", " ", text)  # 其他空白符视为空格
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

    # "Editor" 之后, "Copyright" 之前, 完全丢弃
    left_index = -1
    right_index = -1
    # 遍历 pieces, 找到 "Editor" / "Abstract" 和 "Copyright" 所在的区块索引
    for i in range(len(pieces)):
        # JMLR 格式的论文中, "Editor" 之后的内容为摘要
        if re.search(r"(?u)Editor", pieces[i]["text"], re.IGNORECASE):
            left_index = i
        elif re.search(r"(?u)Abstract", pieces[i]["text"], re.IGNORECASE):
            left_index = i - 1
        # JMLR 格式的论文中, Copyright 符号之后的内容为页脚
        if re.search(r"(?u)(c\u20dd)|(c\n\u20dd)|(c\u25cb)|(\u00a9)", pieces[i]["text"], re.IGNORECASE):
            right_index = i
    # 如果找到了 "Editor" / "Abstract" 和 "Copyright", 则进行过滤
    if left_index != -1 and right_index != -1 and left_index < right_index:
        filtered_pieces = pieces[:left_index] + pieces[right_index:]
        return filtered_pieces
    # 否则不进行过滤, 直接返回原始 pieces, 并且打印 pieces 信息
    else:
        print_pieces(pieces=pieces, pdf_source=pdf_source)
        return pieces


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
    pieces = []

    # 仅需提取首页内容
    first_page = jmlr.load_page(0)
    blocks = first_page.get_text("blocks")
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

    # 如果没有提取到任何文本区块, 则报错
    if len(pieces) == 0:
        print(f"{RED}[!] Error: No pieces extracted from {repr(pdf_path)}{RESET}")
        raise JMLRPDFExtractionError(f"No pieces extracted from {repr(pdf_path)}")

    # 依据左上角的坐标排序区块, 保持从上到下和从左到右的顺序
    pieces.sort(key=lambda piece: (piece["rect"][1], piece["rect"][0]))

    # 粗筛文本区块, 过滤摘要和正文
    pieces = coarse_filter_pieces(pieces=pieces, pdf_source=repr(pdf_path))

    # 如果开启 verbose 模式, 打印文档区块内容
    if verbose:
        print_pieces(pieces=pieces, pdf_source=str(pdf_path))

    # 关闭文档, 返回内容
    jmlr.close()
    return pieces


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse JMLR PDF metadata.")
    parser.add_argument("--pdf_path", type=Path, help="Path to the JMLR PDF file.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    parse_jmlr_pdf(args.pdf_path, verbose=True)


def test() -> None:
    pdf_dirs = [
        "../jmlr_2020/main_track",
        "../jmlr_2021/main_track",
        "../jmlr_2022/main_track",
        "../jmlr_2023/main_track",
        "../jmlr_2024/main_track",
    ]
    for pdf_dir in pdf_dirs:
        for pdf_name in os.listdir(pdf_dir):
            pdf_path = os.path.join(pdf_dir, pdf_name)
            try:
                parse_jmlr_pdf(pdf_path, verbose=False)
            except JMLRPDFExtractionError:
                pass


if __name__ == "__main__":
    main()
    # test()
