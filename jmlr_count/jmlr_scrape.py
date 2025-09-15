from __future__ import annotations

from typing import List, Dict

import re
from pathlib import Path

import traceback

import os
import platform
import tempfile

import toml
import requests
from bs4 import BeautifulSoup


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


# --------------------------------------------------------------------------- #
#  1. 下载 / 缓存
# --------------------------------------------------------------------------- #
def download_volume(url: str, *, cache_dir: str | None = None) -> Path:
    """
    下载 JMLR 某卷页面到本地并返回本地路径。

    参数
    ----
    url : str
        形如 https://jmlr.org/papers/v26/ 的地址
    cache_dir : str | None
        如果为 None，则使用系统临时目录；否则缓存到指定目录。
        缓存文件名为 jmlr_v{卷号}.html

    返回
    ----
    Path
        本地 HTML 文件路径
    """
    # 从 URL 提取卷号
    volume_match = re.search(r"v(\d+)/?$", url)
    if not volume_match:
        raise ValueError(f"无法从 URL 提取卷号: {repr(url)}")
    volume = int(volume_match.group(1))

    # 决定缓存路径
    if cache_dir is None:
        tmp_root = Path(tempfile.gettempdir()) / "fml_infra_jmlr_cache"
        tmp_root.mkdir(exist_ok=True)
        local_path = tmp_root / f"jmlr_v{volume}.html"
    else:
        local_path = Path(cache_dir) / f"jmlr_v{volume}.html"
        local_path.parent.mkdir(parents=True, exist_ok=True)

    # 如果缓存已存在且非空，直接复用
    if local_path.exists() and local_path.stat().st_size:
        return local_path

    # 下载
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    local_path.write_text(resp.text, encoding="utf-8")
    return local_path


# --------------------------------------------------------------------------- #
#  2. 解析（含 abs / pdf / bib 链接）
# --------------------------------------------------------------------------- #
def parse_volume_html(html_path: Path, output_dir: Path = Path(".")) -> List[Dict[str, object]]:
    """
    解析本地 HTML，返回论文信息列表。

    返回字段
    --------
    title : str
    authors : list[str]
    volume : int
    issue : int
    page_start : int
    page_end : int
    year : int
    is_mloss : bool
    url_abs : str | None
    url_pdf : str | None
    url_bib : str | None
    """
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "lxml")

    # 卷号
    h1 = soup.find("h1")
    if not h1:
        raise RuntimeError(f"无法定位 <h1> 标签: {repr(html_path)}")
    vol_match = re.search(r"Volume\s+(\d+)", h1.get_text(strip=True), re.I)
    if not vol_match:
        raise RuntimeError(f"无法从 <h1> 提取卷号: {repr(html_path)}")
    volume = int(vol_match.group(1))

    papers: List[Dict[str, object]] = []

    for dl in soup.select("dl"):
        dt = dl.find("dt")
        if not dt:
            raise RuntimeError(f"无法提取 dt: {repr(dl)}")
        title = dt.get_text(strip=True)

        dd = dl.find("dd")
        if not dd:
            raise RuntimeError(f"无法提取 dd: {repr(dl)}")
        author_tag = dd.find("b")
        authors = [a.strip() for a in author_tag.get_text(strip=True).split(",")] if author_tag else []

        meta_text = dd.get_text(separator=" ", strip=True)
        meta_match = re.search(r"\((\d+)\):(\d+)[–−-](\d+),\s*(\d{4})", meta_text)
        if not meta_match:
            raise RuntimeError(f"无法提取 meta (issue/page/year): {repr(dl)}")
        issue = int(meta_match.group(1))
        page_start = int(meta_match.group(2))
        page_end = int(meta_match.group(3))
        year = int(meta_match.group(4))

        is_mloss = "Machine Learning Open Source Software Paper" in meta_text

        # 提取 abs / pdf / bib 链接
        url_abs = url_pdf = url_bib = None
        for a in dd.select("a"):
            href = a.get("href")
            if not href:
                continue
            if href.startswith("/"):
                href = f"https://jmlr.org{href}"
            text = a.get_text(strip=True).lower()
            if text == "abs":
                url_abs = href
            elif text == "pdf":
                url_pdf = href
            elif text == "bib":
                url_bib = href
        if any(map(lambda url: url is None, (url_abs, url_pdf, url_bib))):
            raise RuntimeError(f"无法提取 url (abs/pdf/bib): {repr(dl)}")

        papers.append(
            {
                "title": title,
                "authors": authors,
                "volume": volume,
                "issue": issue,
                "page_start": page_start,
                "page_end": page_end,
                "year": year,
                "is_mloss": is_mloss,
                "url_abs": url_abs,
                "url_pdf": url_pdf,
                "url_bib": url_bib,
            }
        )

    toml_data = {"volume": volume, "papers": papers}
    output_path = Path(output_dir) / f"jmlr_v{volume}.toml"
    with output_path.open("w", encoding="utf-8") as f:
        toml.dump(toml_data, f)
    print(GREEN)
    print(f"已保存TOML文件: {output_path}")
    print(RESET)

    return papers


# --------------------------------------------------------------------------- #
#  3. 命令行示例（可选）
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    urls = [
        "https://jmlr.org/papers/v26/",
        "https://jmlr.org/papers/v25/",
        "https://jmlr.org/papers/v24/",
        "https://jmlr.org/papers/v23/",
        "https://jmlr.org/papers/v22/",
        "https://jmlr.org/papers/v21/",
        "https://jmlr.org/papers/v20/",
    ]

    for url in urls:
        try:
            local_html = download_volume(url, cache_dir="./jmlr_cache")
            data = parse_volume_html(local_html)
            print(f"{repr(url)} 共 {len(data)} 篇论文")
            # for p in data:
            #     print(
            #         (f">>> {p['title']}\n" if not p["is_mloss"] else YELLOW + f">>> [MLOSS] {p['title']}\n")
            #         + f"    作者: {' / '.join(p['authors'])}\n"
            #         + f"    {p['volume']}卷 {p['issue']}期 {p['page_start']}~{p['page_end']}页 {p['year']}年\n"
            #         + RESET
            #     )
        except Exception as e:
            print(RED)
            print(f"处理 {repr(url)} 失败: {repr(e)}")
            traceback.print_exc()
            print(RESET)
