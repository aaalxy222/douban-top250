"""命令行入口：抓取 Top250 并写入数据库。"""
import sys

import crawler
import db


def main():
    def progress(page, total_pages, count):
        print(f"  第 {page}/{total_pages} 页，累计 {count} 条", flush=True)

    print("开始抓取豆瓣 Top250 ...")
    movies = crawler.crawl_all(progress=progress)

    if len(movies) < 200:
        print(f"只抓到 {len(movies)} 条，疑似被限流，未写入数据库", file=sys.stderr)
        return 1

    conn = db.connect()
    written = db.upsert_movies(conn, movies)
    print(f"已写入 {written} 条，数据库共 {db.stats(conn)['total']} 条")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
