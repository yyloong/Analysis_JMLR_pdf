from proc_jmlr_lite import parse_jmlr_pdf
from typing import List, Dict, Tuple
from pathlib import Path
from statistics import mean, median
from collections import defaultdict
import os
import csv


def count_review_time(submitted: str, published: str) -> int:
    """计算审稿时间,以月为单位,submitted : year.month , published : year.month"""

    def parse_date(date_str: str) -> Tuple[int, int]:
        parts = date_str.split(".")
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        return year, month

    try:
        submitted_date = parse_date(submitted)
        published_date = parse_date(published)
        delta_months = (published_date[0] - submitted_date[0]) * 12 + (published_date[1] - submitted_date[1])
        return delta_months
    except Exception as e:
        print(f"Error parsing dates: {e}")
        print(f"Submitted: {submitted}, Published: {published}")
        return None


def split_keywords(keywords_str: str) -> List[str]:
    """将关键词字符串拆分为关键词列表"""
    if not keywords_str:
        return []
    if "," in keywords_str:
        keywords = keywords_str.split(",")
    elif ";" in keywords_str:
        keywords = keywords_str.split(";")
    else:
        keywords = [keywords_str]
    return [kw.replace("\n", "").strip().lower() for kw in keywords if kw.strip()]


class Editor:
    def __init__(self, name: str) -> None:
        self.name = name
        self.papers_list_with_year = defaultdict(list)  # year -> List[paper_dict]

    def add_paper(self, year: str, paper_info: Dict[str, str]) -> None:
        """添加一篇论文到该编辑负责的论文列表中"""
        self.papers_list_with_year[year].append(paper_info)

    def total_paper_num(self) -> int:
        """计算该编辑负责的论文总数"""
        return sum(len(papers) for papers in self.papers_list_with_year.values())

    def yearly_paper_num(self) -> Dict[str, int]:
        """计算该编辑负责的论文按年份分类的统计信息"""
        return {year: len(papers) for year, papers in self.papers_list_with_year.items()}

    def keywords_summary_with_year(self) -> Dict[str, Dict[str, int]]:
        """计算该编辑负责的论文关键词出现频次按年份分类的统计信息"""
        keywords_count_per_year = defaultdict(lambda: defaultdict(int))
        for year, papers in self.papers_list_with_year.items():
            for paper in papers:
                keywords_str = paper.get("keywords", "")
                if keywords_str:
                    keywords = split_keywords(keywords_str)
                    for keyword in keywords:
                        if keyword:
                            keywords_count_per_year[year][keyword] += 1
        return {year: dict(counts) for year, counts in keywords_count_per_year.items()}

    def overall_keywords_summary(self) -> Dict[str, int]:
        """计算该编辑负责的论文关键词出现频次的总体统计信息"""
        overall_keywords_count = defaultdict(int)
        for keywords_count in self.keywords_summary_with_year().values():
            for keyword, count in keywords_count.items():
                overall_keywords_count[keyword] += count
        return dict(overall_keywords_count)

    def review_time_summary_with_year(self) -> Tuple[float, float]:
        """计算该编辑负责的论文平均审稿时间和中位数审稿时间,以月为单位"""
        review_times = {}
        for year, papers in self.papers_list_with_year.items():
            times = []
            for paper in papers:
                submitted = paper.get("submitted")
                published = paper.get("published")
                if submitted and published:
                    # 计算审稿时间,以月为单位,submitted : year.month , published : year.month
                    review_time = count_review_time(submitted, published)
                    if review_time is not None:
                        times.append(review_time)

            if times:
                # 计算中位数和平均数
                review_times[year] = {"average": mean(times), "median": median(times), "time_set": times}
        return review_times

    def overall_review_time_summary(self) -> Tuple[float, float]:
        """计算该编辑负责的论文总体平均审稿时间和中位数审稿时间,以月为单位"""
        all_averages_time = []
        all_medians_time = []
        for times in self.review_time_summary_with_year().values():
            all_averages_time.extend(times["time_set"])
            all_medians_time.extend(times["time_set"])
        overall_average = mean(all_averages_time) if all_averages_time else 0
        overall_median = median(all_medians_time) if all_medians_time else 0
        return overall_average, overall_median


class EditorsCollection:
    def __init__(self, papers_list_with_year: Dict[str, List[Dict[str, str]]]) -> None:
        self.get_all_editors(papers_list_with_year)
        # 计算年份范围
        self.years = sorted(papers_list_with_year.keys())

    def get_all_editors(self, papers_list_with_year) -> Dict[str, Editor]:
        """从所有论文中提取编辑列表并创建Editor对象"""
        self.editors_dict = {}
        for year, papers in papers_list_with_year.items():
            for paper in papers:
                editor_name = paper.get("editor", "").strip()
                if editor_name:
                    if editor_name not in self.editors_dict:
                        self.editors_dict[editor_name] = Editor(editor_name)
                    self.editors_dict[editor_name].add_paper(year, paper)
        return self.editors_dict

    def all_editors_review_time_summary(self) -> Dict[str, Tuple[float, float]]:
        """计算所有编辑的总体平均审稿时间和中位数审稿时间,以月为单位"""
        summary = {}
        for editor_name, editor in self.editors_dict.items():
            overall_avg, overall_median = editor.overall_review_time_summary()
            summary[editor_name] = (overall_avg, overall_median)
        return summary

    def editors_to_csv(self, output_file: str) -> None:
        """将所有编辑的统计信息输出到CSV文件中"""
        """按照以下字段输出:
        'editor', 'total_paper_num', 'year1_per_num', 'year2_per_num', ...,
        'yearN_per_num', 'most_keyword','year1_most_keyword', 'year2_most_keyword', ...,
        'yearN_most_keyword',
        'overall_average_review_time(month)', 'overall_median_review_time(month)'
        'all_keywords_num'
        'all_keywords'
        """
        """按照编辑审稿总数量降序排列"""
        """在结尾添加整体平均审稿时间"""
        with open(output_file, mode="w", newline="", encoding="utf-8") as csvfile:
            fieldnames = ["editor", "total_paper_num"]
            for year in self.years:
                fieldnames.append(f"{year}_per_num")
            fieldnames.append("most_keyword")
            for year in self.years:
                fieldnames.append(f"{year}_most_keyword")
            fieldnames.extend(["overall_average_review_time(month)", "overall_median_review_time(month)"])
            fieldnames.append("all_keywords_num")
            fieldnames.append("all_keywords")
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for editor_name, editor in sorted(self.editors_dict.items(), key=lambda x: x[1].total_paper_num(), reverse=True):
                row = {"editor": editor_name, "total_paper_num": editor.total_paper_num()}
                yearly_nums = editor.yearly_paper_num()
                for year in self.years:
                    row[f"{year}_per_num"] = yearly_nums.get(year, 0)

                keywords_summary = editor.keywords_summary_with_year()
                for year in self.years:
                    year_keywords = keywords_summary.get(year, {})
                    if year_keywords:
                        most_keyword = max(year_keywords.items(), key=lambda x: x[1])[0]
                    else:
                        most_keyword = ""
                    row[f"{year}_most_keyword"] = most_keyword
                # 计算整体 most_keyword
                overall_keywords = editor.overall_keywords_summary()
                if overall_keywords:
                    overall_most_keyword = max(overall_keywords.items(), key=lambda x: x[1])[0]
                else:
                    overall_most_keyword = ""
                row["most_keyword"] = overall_most_keyword

                overall_avg, overall_median = editor.overall_review_time_summary()
                row["overall_average_review_time(month)"] = round(overall_avg, 2)
                row["overall_median_review_time(month)"] = round(overall_median, 2)
                all_keywords = sorted(overall_keywords.keys(), key=lambda x: overall_keywords[x], reverse=True)
                row["all_keywords_num"] = len(all_keywords)
                row["all_keywords"] = "; ".join(all_keywords)

                writer.writerow(row)
            # 计算整体平均审稿时间
            overall_summary = self.all_editors_review_time_summary()
            overall_avg_times = [avg for avg, _ in overall_summary.values() if avg is not None]
            overall_avg = mean(overall_avg_times) if overall_avg_times else 0
            writer.writerow(
                {"editor": "Overall Average Review Time", "total_paper_num": round(overall_avg, 2)}
            )
        print(f"Editors statistics written to {output_file}")


class Keyword:
    def __init__(self, name: str) -> None:
        self.name = name
        self.papers_list_with_year = defaultdict(int)  # year -> int
        self.average_review_time_with_year = defaultdict(float)  # year -> float

    def add_paper(self, year: str, review_time: int) -> None:
        """添加一篇论文到该关键词对应的论文计数中"""
        self.papers_list_with_year[year] += 1
        """更新该关键词对应的平均审稿时间"""
        if review_time is None:
            return
        elif review_time < 0:
            return
        if self.average_review_time_with_year.get(year) is not None:
            current_avg = self.average_review_time_with_year[year]
            current_count = self.papers_list_with_year[year] - 1
            new_avg = (current_avg * current_count + review_time) / self.papers_list_with_year[year]
            self.average_review_time_with_year[year] = new_avg
        else:
            self.average_review_time_with_year[year] = review_time

    def overall_paper_num(self) -> int:
        """计算该关键词对应的论文总数"""
        return sum(self.papers_list_with_year.values())

    def overall_average_review_time(self) -> float:
        """计算该关键词对应的总体平均审稿时间"""
        if not self.average_review_time_with_year:
            return 0.0
        return round(mean(self.average_review_time_with_year.values()), 2)


class KeywordsCollection:
    def __init__(self, papers_list_with_year: Dict[str, List[Dict[str, str]]]) -> None:
        self.get_all_keywords(papers_list_with_year)
        # 计算年份范围
        self.years = sorted(papers_list_with_year.keys())

    def get_all_keywords(self, papers_list_with_year) -> Dict[str, Keyword]:
        """从所有论文中提取关键词列表并创建Keyword对象"""
        self.keywords_dict = {}
        for year, papers in papers_list_with_year.items():
            for paper in papers:
                keywords_str = paper.get("keywords", "")
                if keywords_str:
                    keywords = split_keywords(keywords_str)
                    for keyword in keywords:
                        if keyword:
                            if keyword not in self.keywords_dict:
                                self.keywords_dict[keyword] = Keyword(keyword)
                            sumitted = paper.get("submitted")
                            published = paper.get("published")
                            if not sumitted or not published:
                                review_time = None
                            else:
                                review_time = count_review_time(sumitted, published)
                                if review_time < 0:
                                    review_time = None
                            self.keywords_dict[keyword].add_paper(year, review_time)
        return self.keywords_dict

    def keywords_to_csv(self, output_file: str) -> None:
        """将所有关键词的统计信息输出到CSV文件中"""
        """按照以下字段输出:
        'keyword', 'overall_paper_num', 'year1_per_num', 'year2_per_num', ...,
        'yearN_per_num','overall_average_review_time(month)'"""
        with open(output_file, mode="w", newline="", encoding="utf-8") as csvfile:
            fieldnames = ["keyword", "overall_paper_num"]
            for year in self.years:
                fieldnames.append(f"{year}_per_num")
            fieldnames.append("overall_average_review_time(month)")
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for keyword_name, keyword in sorted(
                self.keywords_dict.items(), key=lambda x: x[1].overall_paper_num(), reverse=True
            ):
                row = {"keyword": keyword_name, "overall_paper_num": keyword.overall_paper_num()}
                for year in self.years:
                    row[f"{year}_per_num"] = keyword.papers_list_with_year.get(year, 0)
                row["overall_average_review_time(month)"] = keyword.overall_average_review_time()
                writer.writerow(row)
        print(f"Keywords statistics written to {output_file}")


class Paper:
    def __init__(
        self,
        title: str,
        volume: str,
        year: str,
        n_page: int,
        submitted: str,
        revised: str,
        published: str,
        editor: str,
        keywords: str,
    ) -> None:
        self.title = title
        self.volume = volume
        self.year = year
        self.n_page = n_page
        self.editor = editor
        self.keywords = keywords
        self.submitted = submitted
        self.revised = revised
        self.published = published


class PapersCollection:
    def __init__(self, papers_list_with_year: Dict[str, List[Dict[str, str]]]) -> None:
        self.get_all_papers(papers_list_with_year)
        # 计算年份范围
        self.years = sorted(papers_list_with_year.keys())

    def get_all_papers(self, papers_list_with_year) -> List[Paper]:
        """从所有论文中提取论文列表并创建Paper对象"""
        self.papers_list_with_year = papers_list_with_year
        return papers_list_with_year

    def papers_to_csv(self, output_file: str) -> None:
        """将所有论文的基本信息输出到CSV文件中"""
        """按照以下字段输出:
        'year','title', 'volume', 'n_pages', 'editor', 'keywords', 'submitted', 'revised', 'published'"""
        """按照年份和标题字母顺序排列"""
        with open(output_file, mode="w", newline="", encoding="utf-8") as csvfile:
            fieldnames = [
                "year",
                "title",
                "volume",
                "n_pages",
                "editor",
                "keywords",
                "submitted",
                "revised",
                "published",
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for year in self.years:
                papers = self.papers_list_with_year[year]
                for paper in sorted(papers, key=lambda x: x.get("title", "")):
                    row = {
                        "year": year,
                        "title": paper.get("title", ""),
                        "volume": paper.get("volume", ""),
                        "n_pages": paper.get("n_pages", 0),
                        "editor": paper.get("editor", ""),
                        "keywords": paper.get("keywords", ""),
                        "submitted": paper.get("submitted", ""),
                        "revised": paper.get("revised", ""),
                        "published": paper.get("published", ""),
                    }
                    writer.writerow(row)
        print(f"Papers information written to {output_file}")


if __name__ == "__main__":
    track = "software_track"
    pdf_dirs = [
        Path(f"../JMLR 2024/{track}"),
        Path(f"../JMLR 2023/{track}"),
        Path(f"../JMLR 2022/{track}"),
        Path(f"../JMLR 2021/{track}"),
        Path(f"../JMLR 2020/{track}"),
    ]
    main_track = "main_track"
    pdf_dirs += [
        Path(f"../JMLR 2024/{main_track}"),
        Path(f"../JMLR 2023/{main_track}"),
        Path(f"../JMLR 2022/{main_track}"),
        Path(f"../JMLR 2021/{main_track}"),
        Path(f"../JMLR 2020/{main_track}"),
    ]
    track = 'combination_track'


    # 汇总所有年份的论文数据
    all_papers_list_with_year = {}
    success_count = 0
    fail_count = 0
    for pdf_dir in pdf_dirs:
        year = pdf_dir.parent.name.split()[-1]
        papers_list = []
        for pdf_file in sorted(os.listdir(pdf_dir)):
            if pdf_file.endswith(".pdf"):
                pdf_path = pdf_dir / pdf_file
                try:
                    _, header_info, editor, keywords = parse_jmlr_pdf(pdf_path, verbose=False)
                    paper_info = {
                        "title": pdf_file.replace(".pdf", ""),
                        **header_info,
                        "editor": editor,
                        "keywords": keywords,
                    }
                    papers_list.append(paper_info)
                    success_count += 1
                except Exception as e:
                    print(f"Error processing {pdf_path}: {e}")
                    fail_count += 1
        if year in all_papers_list_with_year:
            all_papers_list_with_year[year].extend(papers_list)
        else:
            all_papers_list_with_year[year] = papers_list
    print(f"Total successfully processed papers: {success_count}")
    print(f"Total failed papers: {fail_count}")

    # 生成编辑统计CSV
    editors_collection = EditorsCollection(all_papers_list_with_year)
    editors_collection.editors_to_csv(f"jmlr_editors_statistics_{track}.csv")

    # 生成关键词统计CSV
    keywords_collection = KeywordsCollection(all_papers_list_with_year)
    keywords_collection.keywords_to_csv(f"jmlr_keywords_statistics_{track}.csv")

    # 生成论文基本信息CSV
    papers_collection = PapersCollection(all_papers_list_with_year)
    papers_collection.papers_to_csv(f"jmlr_papers_information_{track}.csv")
