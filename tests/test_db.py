"""存储层测试：全部跑在内存库上，不碰真实 data/douban.db。"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db


def movie(rank, title="影片", rating=8.0, votes=10000, year="1994",
          country="美国", genres="剧情", quote="短评", url="https://example.com"):
    return {
        "rank": rank, "title": title, "url": url, "rating": rating,
        "votes": votes, "year": year, "country": country,
        "genres": genres, "quote": quote,
    }


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    yield c
    c.close()


@pytest.fixture
def seeded(conn):
    db.upsert_movies(conn, [movie(i, title=f"影片{i}", rating=7.0 + i / 10) for i in range(1, 6)])
    return conn


def test_upsert_twice_keeps_row_count(conn):
    db.upsert_movies(conn, [movie(1), movie(2)])
    db.upsert_movies(conn, [movie(1), movie(2)])
    assert conn.execute("SELECT COUNT(*) FROM movies").fetchone()[0] == 2


def test_upsert_overwrites_changed_fields(conn):
    db.upsert_movies(conn, [movie(1, rating=8.0)])
    db.upsert_movies(conn, [movie(1, rating=9.4, votes=999)])
    row = db.get_movie(conn, 1)
    assert row["rating"] == 9.4
    assert row["votes"] == 999


def test_pagination_splits_pages(seeded):
    first = db.query_movies(seeded, page=1, size=2)
    assert first["total"] == 5
    assert [m["rank"] for m in first["items"]] == [1, 2]

    last = db.query_movies(seeded, page=3, size=2)
    assert [m["rank"] for m in last["items"]] == [5]


def test_page_below_one_is_clamped(seeded):
    result = db.query_movies(seeded, page=0, size=2)
    assert result["page"] == 1
    assert result["items"][0]["rank"] == 1


def test_size_is_clamped(seeded):
    assert db.query_movies(seeded, size=1000)["size"] == 100
    assert db.query_movies(seeded, size=0)["size"] == 1


def test_keyword_matches_title_quote_and_genres(seeded):
    assert db.query_movies(seeded, keyword="影片3")["total"] == 1
    assert db.query_movies(seeded, keyword="不存在的词")["total"] == 0


def test_min_rating_filter(seeded):
    result = db.query_movies(seeded, min_rating=7.45)
    assert result["total"] == 1
    assert result["items"][0]["rank"] == 5


def test_invalid_sort_falls_back_to_rank(seeded):
    result = db.query_movies(seeded, sort="votes; DROP TABLE movies")
    assert [m["rank"] for m in result["items"]] == [1, 2, 3, 4, 5]


def test_sort_by_rating_is_descending(seeded):
    result = db.query_movies(seeded, sort="rating")
    ratings = [m["rating"] for m in result["items"]]
    assert ratings == sorted(ratings, reverse=True)


def test_query_all_returns_every_row(seeded):
    assert len(db.query_all(seeded)) == 5
    assert len(db.query_all(seeded, min_rating=7.45)) == 1


def test_stats_on_empty_db(conn):
    data = db.stats(conn)
    assert data["total"] == 0
    assert data["avg_rating"] == 0
    assert data["max_votes"] is None


def test_stats_aggregates(conn):
    db.upsert_movies(conn, [
        movie(1, rating=9.0, votes=500, year="1994", country="美国"),
        movie(2, rating=8.0, votes=900, year="1997", country="美国"),
        movie(3, rating=8.5, votes=100, year="2001", country="日本"),
    ])
    data = db.stats(conn)
    assert data["total"] == 3
    assert data["avg_rating"] == 8.5
    assert data["by_decade"] == {"1990s": 2, "2000s": 1}
    assert data["by_country"] == {"美国": 2, "日本": 1}
    assert data["max_votes"] == {"title": "影片", "votes": 900}


def test_get_movie_returns_none_when_absent(conn):
    assert db.get_movie(conn, 999) is None
