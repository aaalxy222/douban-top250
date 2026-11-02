const state = { page: 1, size: 20, keyword: "", min_rating: "", sort: "rank" };
let totalPages = 1;

const $ = (id) => document.getElementById(id);
const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ESCAPES[c]);

const fmtVotes = (n) =>
  n >= 10000 ? (n / 10000).toFixed(1) + "万" : String(n ?? 0);

function query() {
  const p = new URLSearchParams({ page: state.page, size: state.size, sort: state.sort });
  if (state.keyword) p.set("keyword", state.keyword);
  if (state.min_rating) p.set("min_rating", state.min_rating);
  return p;
}

function ratingClass(v) {
  if (v >= 9) return "rating top";
  if (v >= 8.5) return "rating high";
  return "rating";
}

function renderBars(el, obj, limit) {
  const entries = Object.entries(obj);
  if (!entries.length) {
    el.innerHTML = '<p class="empty">暂无数据</p>';
    return;
  }
  const max = Math.max(...entries.map(([, v]) => v));
  el.innerHTML = entries.slice(0, limit).map(([k, v]) => `
    <div class="bar-row">
      <span class="bar-label" title="${esc(k)}">${esc(k)}</span>
      <span class="bar-track"><span class="bar-fill" style="width:${(v / max) * 100}%"></span></span>
      <span class="bar-value">${v}</span>
    </div>`).join("");
}

async function loadStats() {
  const data = await (await fetch("/api/stats")).json();
  $("statTotal").textContent = data.total;
  $("statRating").textContent = data.total ? data.avg_rating.toFixed(2) : "--";
  $("statDecade").textContent = Object.keys(data.by_decade).length;
  if (data.max_votes) {
    $("statVotes").textContent = fmtVotes(data.max_votes.votes);
    $("statVotesLabel").textContent = data.max_votes.title;
  }
  renderBars($("decadeBars"), data.by_decade);
  renderBars($("countryBars"), data.by_country, 8);
}

function rowHtml(m) {
  const title = m.url
    ? `<a href="${esc(m.url)}" target="_blank" rel="noopener">${esc(m.title)}</a>`
    : esc(m.title);
  return `
    <tr>
      <td class="num">${m.rank}</td>
      <td class="title">${title}</td>
      <td><span class="${ratingClass(m.rating)}">${(m.rating ?? 0).toFixed(1)}</span></td>
      <td class="votes">${fmtVotes(m.votes)}</td>
      <td class="num">${esc(m.year)}</td>
      <td class="num">${esc(m.country)}</td>
      <td class="genre">${esc(m.genres)}</td>
      <td class="quote">${esc(m.quote) || "—"}</td>
    </tr>`;
}

async function loadList() {
  $("pageInfo").textContent = "加载中…";
  const data = await (await fetch("/api/movies?" + query())).json();
  totalPages = Math.max(1, Math.ceil(data.total / data.size));
  state.page = data.page;

  $("tbody").innerHTML = data.items.length
    ? data.items.map(rowHtml).join("")
    : '<tr><td colspan="8" class="empty">没有匹配的影片</td></tr>';

  $("pageInfo").textContent = `第 ${data.page} / ${totalPages} 页 · 共 ${data.total} 条`;
  $("prevBtn").disabled = data.page <= 1;
  $("nextBtn").disabled = data.page >= totalPages;
}

function resetAndLoad() {
  state.page = 1;
  loadList();
}

let timer = null;
$("keyword").addEventListener("input", (e) => {
  clearTimeout(timer);
  timer = setTimeout(() => {
    state.keyword = e.target.value.trim();
    resetAndLoad();
  }, 300);
});

$("minRating").addEventListener("change", (e) => {
  state.min_rating = e.target.value;
  resetAndLoad();
});

$("sort").addEventListener("change", (e) => {
  state.sort = e.target.value;
  resetAndLoad();
});

$("prevBtn").addEventListener("click", () => {
  if (state.page > 1) {
    state.page -= 1;
    loadList();
  }
});

$("nextBtn").addEventListener("click", () => {
  if (state.page < totalPages) {
    state.page += 1;
    loadList();
  }
});

$("exportBtn").addEventListener("click", () => {
  window.location.href = "/api/export?" + query();
});

loadStats();
loadList();
