"""解析层测试：不联网，用真实页面结构的 HTML 片段验证字段提取和异常条目跳过。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import crawler


ITEM = """
<li>
  <div class="item">
    <div class="pic">
      <em>{rank}</em>
      <a href="{url}"><img alt="海报"></a>
    </div>
    <div class="info">
      <div class="hd">
        <a href="{url}">
          <span class="title">{title}</span>
          <span class="title">&nbsp;/&nbsp;{title_en}</span>
          <span class="other">&nbsp;/&nbsp;别名一 / 别名二</span>
        </a>
      </div>
      <div class="bd">
        <p>
          导演: 某某&nbsp;&nbsp;&nbsp;主演: 演员甲 / 演员乙 /...<br>
          {meta}
        </p>
        <div>
          <span class="rating5-t"></span>
          <span class="rating_num" property="v:average">{rating}</span>
          <span property="v:best" content="10.0"></span>
          <span>{votes}人评价</span>
        </div>
        <p class="quote"><span>{quote}</span></p>
      </div>
    </div>
  </div>
</li>
"""


def build_item(rank=1, title="肖申克的救赎", title_en="The Shawshank Redemption",
               rating="9.7", votes="3361567",
               meta="1994&nbsp;/&nbsp;美国&nbsp;/&nbsp;犯罪 剧情",
               quote="希望让人自由。", url="https://movie.douban.com/subject/1292052/"):
    return ITEM.format(rank=rank, title=title, title_en=title_en, rating=rating,
                       votes=votes, meta=meta, quote=quote, url=url)


def wrap(*items):
    return '<ol class="grid_view">' + "".join(items) + "</ol>"


def test_parse_single_item_fields():
    movies = crawler.parse_page(wrap(build_item()))
    assert len(movies) == 1
    m = movies[0]
    assert m["rank"] == 1
    assert m["title"] == "肖申克的救赎"
    assert m["rating"] == 9.7
    assert m["votes"] == 3361567
    assert m["year"] == "1994"
    assert m["country"] == "美国"
    assert m["genres"] == "犯罪 剧情"
    assert m["quote"] == "希望让人自由。"
    assert m["url"].startswith("https://movie.douban.com/subject/")


def test_parse_multiple_items_keeps_order():
    html = wrap(build_item(rank=1, title="甲"), build_item(rank=2, title="乙"))
    movies = crawler.parse_page(html)
    assert [m["rank"] for m in movies] == [1, 2]
    assert [m["title"] for m in movies] == ["甲", "乙"]


def test_meta_with_two_release_dates():
    """多一条上映日期时国家/类型不能按固定下标取。"""
    meta = "1961(中国大陆)&nbsp;/&nbsp;1978(中国大陆)&nbsp;/&nbsp;中国大陆&nbsp;/&nbsp;剧情 动画 奇幻 古装"
    m = crawler.parse_page(wrap(build_item(meta=meta)))[0]
    assert m["year"] == "1961"
    assert m["country"] == "中国大陆"
    assert m["genres"] == "剧情 动画 奇幻 古装"


def test_meta_with_single_release_date():
    meta = "1982(中国大陆)&nbsp;/&nbsp;中国大陆&nbsp;/&nbsp;剧情 历史"
    m = crawler.parse_page(wrap(build_item(meta=meta)))[0]
    assert m["year"] == "1982"
    assert m["country"] == "中国大陆"
    assert m["genres"] == "剧情 历史"


def test_cast_line_with_slashes_does_not_break_meta():
    m = crawler.parse_page(wrap(build_item()))[0]
    assert m["year"] == "1994"


def test_votes_with_thousands_separator():
    m = crawler.parse_page(wrap(build_item(votes="1,234,567")))[0]
    assert m["votes"] == 1234567


def test_missing_votes_falls_back_to_zero():
    html = wrap(build_item(votes="")).replace("人评价", "")
    m = crawler.parse_page(html)[0]
    assert m["votes"] == 0


def test_missing_rating_is_skipped():
    broken = build_item().replace('class="rating_num" property="v:average"', 'class="other"')
    movies = crawler.parse_page(wrap(broken, build_item(rank=2)))
    assert len(movies) == 1
    assert movies[0]["rank"] == 2


def test_missing_rank_is_skipped():
    broken = build_item().replace("<em>1</em>", "")
    assert crawler.parse_page(wrap(broken)) == []


def test_missing_quote_falls_back_to_empty():
    html = wrap(build_item(quote="")).replace('<p class="quote"><span></span></p>', "")
    m = crawler.parse_page(html)[0]
    assert m["quote"] == ""


def test_empty_html_returns_empty_list():
    assert crawler.parse_page("<html><body></body></html>") == []


def test_empty_grid_returns_empty_list():
    assert crawler.parse_page('<ol class="grid_view"></ol>') == []
