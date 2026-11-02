# 豆瓣 Top250 数据采集与看板

一个从采集到展示跑通全链路的项目：抓取豆瓣电影 Top250 → 解析结构化字段 → SQLite 按排名增量入库 → Web 看板做检索、筛选、统计与导出。

## 功能

- **采集**：10 页共 250 条，UA 轮换、Referer 伪装、指数退避重试、页间随机延时
- **解析**：抓取与解析拆成独立函数，解析可脱离网络单测
- **存储**：以排名为主键做 upsert，重复抓取不产生重复行，可当作定时增量更新
- **查询**：关键词（片名 / 短评 / 类型）、最低评分、四种排序、分页
- **看板**：总量、平均分、年代分布、国家分布、评价人数之最
- **导出**：按当前筛选结果导出 CSV，带 BOM，Excel 双击不乱码

## 目录

```
douban-top250/
├── crawler.py          # 抓取 + 解析（fetch_page / parse_page / crawl_all）
├── db.py               # SQLite 存取层（upsert / 分页查询 / 统计）
├── crawl.py            # 命令行抓取入口
├── app.py              # Flask Web 入口
├── templates/index.html
├── static/style.css
├── static/app.js
├── data/
│   ├── douban_top250.csv   # 250 条数据快照，可直接看结果
│   └── douban.db           # 运行 crawl.py 后生成，不入库
└── tests/
    ├── test_parser.py  # 解析层，用真实页面结构的 HTML 片段
    └── test_db.py      # 存储层，跑在内存库上
```

## 运行

```bash
pip install requests beautifulsoup4 lxml flask pytest

python crawl.py     # 抓取并入库（约 20 秒）
python app.py       # 打开 http://127.0.0.1:5002
python -m pytest tests -q
```

`data/douban_top250.csv` 是一次完整抓取的数据快照，可以直接打开看结果。数据库文件是二进制，没有提交进仓库，启动看板前先跑一次 `crawl.py` 生成（约 20 秒，需要联网）。

## 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/` | 看板页面 |
| GET | `/api/movies` | `page` `size` `keyword` `min_rating` `sort` |
| GET | `/api/stats` | 汇总统计 |
| GET | `/api/export` | 按同样筛选条件导出 CSV |

`sort` 只接受 `rank` `rating` `votes` `year`，非法值回退到 `rank`。

## 几个值得讲的技术点

**1. 元信息行的两种格式。** 豆瓣的年份/国家/类型挤在同一行，格式有两种：

```
1994 / 美国 / 犯罪 剧情
1961(中国大陆) / 1978(中国大陆) / 中国大陆 / 剧情 动画 奇幻 古装
```

按固定下标取 `parts[1]`、`parts[2]`，第二种格式会把国家读成上映日期。所以改成**年份取第一段、国家取倒数第二段、类型取最后一段**，并对第一段做四位年份的正匹配。这个坑是先跑出脏数据、查库定位到具体条目、再回去看原始 HTML 才发现的。

**2. 评价人数和短评的选择器。** 页面上评价人数是无属性的 `<span>3361567人评价</span>`，短评在 `p.quote > span` 里，都不是想当然的 `span[property='v:votes']` / `span.inq`。现在用正则 `(\d[\d,]*)\s*人评价` 抓人数，兼容千分位。

**3. 增量更新而非全量覆盖。** `INSERT ... ON CONFLICT(rank) DO UPDATE`，配合 `updated_at` 字段，重复跑不会产生脏数据，也方便以后接定时任务。

**4. 排序字段走白名单。** `sort` 直接拼进 SQL 会注入，用集合校验后回退到默认值，测试里专门用 `sort="votes; DROP TABLE movies"` 验证过。

**5. 解析和网络解耦。** `parse_page(html)` 只吃字符串，测试不需要 mock 网络，25 个用例 0.3 秒跑完。

## 已知限制

- 只抓 Top250 榜单本身，不做电影详情页和评论抓取
- 豆瓣无短评的影片有 115 条，导出时该列为空，不是漏抓
- 国家字段存在「英国 美国」这类多地区写法，统计时按首个地区归类
- 未做代理池与验证码处理，高频抓取仍可能被限流；本项目只抓 10 页，页间随机延时 1-2 秒
- 开发服务器为 Flask 内置，仅本地演示用
