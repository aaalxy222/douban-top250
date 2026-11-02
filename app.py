"""Web 入口：统计看板、条件筛选分页、按筛选结果导出 CSV。"""
import csv
import io
import os

from flask import Flask, Response, jsonify, render_template, request

import db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "douban.db")

app = Flask(__name__)


def _int_arg(name, default):
    try:
        return int(request.args.get(name, ""))
    except (TypeError, ValueError):
        return default


def _float_arg(name):
    raw = request.args.get(name, "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _filters():
    return {
        "min_rating": _float_arg("min_rating"),
        "keyword": (request.args.get("keyword") or "").strip(),
        "sort": request.args.get("sort", "rank"),
    }


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/movies")
def api_movies():
    conn = db.connect(DB_PATH)
    try:
        result = db.query_movies(
            conn,
            page=_int_arg("page", 1),
            size=_int_arg("size", 20),
            **_filters(),
        )
    finally:
        conn.close()
    return jsonify(result)


@app.get("/api/stats")
def api_stats():
    conn = db.connect(DB_PATH)
    try:
        data = db.stats(conn)
    finally:
        conn.close()
    return jsonify(data)


@app.get("/api/export")
def api_export():
    conn = db.connect(DB_PATH)
    try:
        rows = db.query_all(conn, **_filters())
    finally:
        conn.close()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["排名", "片名", "评分", "评价人数", "年份", "国家", "类型", "短评", "链接"])
    for row in rows:
        writer.writerow([row["rank"], row["title"], row["rating"], row["votes"],
                         row["year"], row["country"], row["genres"], row["quote"], row["url"]])

    # 带 BOM，Excel 直接双击打开不会乱码
    body = "\ufeff" + buf.getvalue()
    return Response(
        body,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=douban_top250.csv"},
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5002, debug=False)
