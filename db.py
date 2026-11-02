"""SQLite 存取层：按排名做增量更新，提供筛选、排序、统计查询。"""
import sqlite3
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS movies (
    rank INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT,
    rating REAL,
    votes INTEGER,
    year TEXT,
    country TEXT,
    genres TEXT,
    quote TEXT,
    updated_at TEXT
);
"""

SORT_FIELDS = {"rank", "rating", "votes", "year"}


def connect(path="data/douban.db"):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
    return conn


def upsert_movies(conn, movies):
    """以排名为主键写入，重复抓取不会产生重复行。"""
    now = datetime.now().isoformat(timespec="seconds")
    rows = [
        (m["rank"], m["title"], m["url"], m["rating"], m["votes"],
         m["year"], m["country"], m["genres"], m["quote"], now)
        for m in movies
    ]
    conn.executemany(
        """
        INSERT INTO movies
            (rank, title, url, rating, votes, year, country, genres, quote, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(rank) DO UPDATE SET
            title = excluded.title,
            url = excluded.url,
            rating = excluded.rating,
            votes = excluded.votes,
            year = excluded.year,
            country = excluded.country,
            genres = excluded.genres,
            quote = excluded.quote,
            updated_at = excluded.updated_at
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def _order_of(sort):
    if sort not in SORT_FIELDS:
        sort = "rank"
    return sort, ("DESC" if sort in ("rating", "votes", "year") else "ASC")


def _where(min_rating=None, keyword=None):
    """把筛选条件拼成 WHERE 子句，值一律走占位符参数。"""
    conds = []
    params = []
    if min_rating is not None:
        conds.append("rating >= ?")
        params.append(min_rating)
    if keyword:
        conds.append("(title LIKE ? OR quote LIKE ? OR genres LIKE ?)")
        like = f"%{keyword}%"
        params.extend([like, like, like])
    return (" WHERE " + " AND ".join(conds)) if conds else "", params


def query_movies(conn, page=1, size=20, min_rating=None, keyword=None, sort="rank"):
    """分页查询。排序字段走白名单，避免拼接任意 SQL。"""
    sort, order = _order_of(sort)
    clause, params = _where(min_rating, keyword)

    total = conn.execute(f"SELECT COUNT(*) FROM movies{clause}", params).fetchone()[0]

    size = max(1, min(size, 100))
    page = max(1, page)
    offset = (page - 1) * size
    rows = conn.execute(
        f"SELECT * FROM movies{clause} ORDER BY {sort} {order} LIMIT ? OFFSET ?",
        params + [size, offset],
    ).fetchall()

    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [dict(row) for row in rows],
    }


def query_all(conn, min_rating=None, keyword=None, sort="rank"):
    """不分页，按当前筛选条件取全量，供导出使用。"""
    sort, order = _order_of(sort)
    clause, params = _where(min_rating, keyword)
    rows = conn.execute(
        f"SELECT * FROM movies{clause} ORDER BY {sort} {order}", params
    ).fetchall()
    return [dict(row) for row in rows]


def stats(conn):
    total = conn.execute("SELECT COUNT(*) FROM movies").fetchone()[0]
    if total == 0:
        return {"total": 0, "avg_rating": 0, "by_decade": {}, "by_country": {}, "max_votes": None}

    avg_rating = conn.execute("SELECT AVG(rating) FROM movies").fetchone()[0]

    by_decade = {}
    for row in conn.execute("SELECT year, COUNT(*) AS n FROM movies GROUP BY year"):
        year = (row["year"] or "")[:4]
        if not year.isdigit():
            continue
        decade = f"{year[:3]}0s"
        by_decade[decade] = by_decade.get(decade, 0) + row["n"]

    by_country = {}
    for row in conn.execute("SELECT country, COUNT(*) AS n FROM movies GROUP BY country"):
        key = (row["country"] or "未知").split()[0] if row["country"] else "未知"
        by_country[key] = by_country.get(key, 0) + row["n"]

    top = conn.execute(
        "SELECT title, votes FROM movies ORDER BY votes DESC LIMIT 1"
    ).fetchone()

    return {
        "total": total,
        "avg_rating": round(avg_rating, 2),
        "by_decade": dict(sorted(by_decade.items())),
        "by_country": dict(sorted(by_country.items(), key=lambda kv: -kv[1])),
        "max_votes": {"title": top["title"], "votes": top["votes"]},
    }


def get_movie(conn, rank):
    row = conn.execute("SELECT * FROM movies WHERE rank = ?", (rank,)).fetchone()
    return dict(row) if row else None
