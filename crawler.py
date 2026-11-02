"""豆瓣 Top250 采集器：分页抓取、解析、带基础反爬策略。

抓取和解析拆成两个函数，解析可以脱离网络单独测试。
"""
import random
import re
import time

import requests
from bs4 import BeautifulSoup

LIST_URL = "https://movie.douban.com/top250"
PAGE_SIZE = 25
MAX_PAGES = 10

YEAR_RE = re.compile(r"(?:19|20)\d{2}")
VOTES_RE = re.compile(r"(\d[\d,]*)\s*人评价")

USER_AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
)


def fetch_page(start, retries=3, timeout=15):
    """抓取一页 HTML，失败按指数退避重试。"""
    params = {"start": start, "filter": ""}
    last_error = None

    for attempt in range(retries):
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Referer": "https://movie.douban.com/",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        try:
            resp = requests.get(LIST_URL, params=params, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                return resp.text
            last_error = f"HTTP {resp.status_code}"
        except requests.RequestException as exc:
            last_error = str(exc)
        time.sleep(2 ** attempt)

    raise RuntimeError(f"抓取 start={start} 失败：{last_error}")


def _parse_meta(meta_node):
    """元信息行形如「1994 / 美国 / 犯罪 剧情」，也可能多一条上映日期：
    「1961(中国大陆) / 1978(中国大陆) / 中国大陆 / 剧情 动画 奇幻 古装」。
    因此年份取第一段、国家取倒数第二段、类型取最后一段，不能按固定下标取。
    """
    if meta_node is None:
        return "", "", ""

    lines = [ln.strip() for ln in meta_node.get_text("\n", strip=True).split("\n")]
    meta = next((ln for ln in lines if YEAR_RE.match(ln)), lines[-1] if lines else "")
    parts = [p.strip() for p in meta.split("/") if p.strip()]
    if not parts:
        return "", "", ""

    year_match = YEAR_RE.search(parts[0])
    year = year_match.group(0) if year_match else ""
    genres = parts[-1]
    country = parts[-2] if len(parts) >= 3 else ""
    return year, country, genres


def _parse_item(li):
    rank_node = li.select_one("div.pic em")
    rating_node = li.select_one("span.rating_num")
    if rank_node is None or rating_node is None:
        return None

    link = li.select_one("div.hd a")
    title_node = li.select_one("div.hd a span.title")
    quote_node = li.select_one("p.quote")
    meta_node = li.select_one("div.bd p")

    year, country, genres = _parse_meta(meta_node)

    votes_match = VOTES_RE.search(li.get_text(" ", strip=True))
    return {
        "rank": int(rank_node.get_text(strip=True)),
        "title": title_node.get_text(strip=True) if title_node else "",
        "url": link["href"] if link is not None and link.has_attr("href") else "",
        "rating": float(rating_node.get_text(strip=True)),
        "votes": int(votes_match.group(1).replace(",", "")) if votes_match else 0,
        "year": year,
        "country": country,
        "genres": genres,
        "quote": quote_node.get_text(strip=True) if quote_node else "",
    }


def parse_page(html):
    """从列表页 HTML 中提取电影条目。"""
    soup = BeautifulSoup(html, "lxml")
    movies = []
    for li in soup.select("ol.grid_view > li"):
        movie = _parse_item(li)
        if movie:
            movies.append(movie)
    return movies


def crawl_all(delay=(1.0, 2.0), progress=None):
    """抓完 10 页共 250 条，每页之间随机延时，降低被封风险。"""
    movies = []
    for page in range(MAX_PAGES):
        html = fetch_page(page * PAGE_SIZE)
        movies.extend(parse_page(html))
        if progress:
            progress(page + 1, MAX_PAGES, len(movies))
        if page < MAX_PAGES - 1:
            time.sleep(random.uniform(*delay))
    return movies
