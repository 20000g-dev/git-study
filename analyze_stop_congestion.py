"""정류장별 시간대(시) 승차·하차 수 분석 + HTML 히트맵 시각화.

승차는 board_time의 시, 하차는 alight_time의 시 기준으로 집계한다.
기존 analyze_congestion.py(구간 재차 인원)와는 별개의 분석이다.
"""
import json
from pathlib import Path

import pandas as pd

bus = pd.read_excel("data/bus_routes.xlsx", sheet_name=None)
stops = bus["stops"]
taps = pd.read_excel("data/card_taps.xlsx", sheet_name="tap_log",
                     parse_dates=["board_time", "alight_time"])

names = stops.drop_duplicates("stop_id").set_index("stop_id")["stop_name"]
n_days = taps["board_time"].dt.normalize().nunique()
period = (taps["board_time"].min().strftime("%Y-%m-%d"), taps["board_time"].max().strftime("%Y-%m-%d"))

HOURS = range(24)
board = (taps.groupby(["board_stop_id", taps["board_time"].dt.hour]).size()
         .rename("boardings").rename_axis(["stop_id", "hour"]))
alight = (taps.groupby(["alight_stop_id", taps["alight_time"].dt.hour]).size()
          .rename("alightings").rename_axis(["stop_id", "hour"]))

# 정류장 × 시간대 격자 (탑승·하차 모두 0인 칸도 0으로 채운다)
grid = pd.DataFrame(
    [(s, h) for s in names.index for h in HOURS], columns=["stop_id", "hour"]
).set_index(["stop_id", "hour"])
grid = grid.join(board, how="left").join(alight, how="left").fillna(0).astype(int)
grid["total"] = grid["boardings"] + grid["alightings"]
grid = grid.reset_index()
grid.insert(1, "stop_name", grid["stop_id"].map(names))

print(f"분석 기간 {period[0]} ~ {period[1]} ({n_days}일), 탑승 {len(taps)}건")
print("\n=== 정류장별 총 승차·하차 (상위 5) ===")
totals = grid.groupby(["stop_id", "stop_name"])[["boardings", "alightings"]].sum()
totals["total"] = totals.sum(axis=1)
print(totals.sort_values("total", ascending=False).head(5).to_string())

out = Path("results")
out.mkdir(exist_ok=True)
csv_path = out / "stop_hourly_boardings.csv"
grid.sort_values(["stop_id", "hour"]).to_csv(csv_path, index=False, encoding="utf-8-sig")
print("\n저장:", csv_path)

# ---- HTML 시각화 (단일 파일, 외부 의존 없음) ----
order = totals.sort_values("total", ascending=False).index.get_level_values("stop_id")
payload = {
    "period": f"{period[0]} ~ {period[1]} ({n_days}일)",
    "hours": list(HOURS),
    "stops": [{"id": s, "name": names[s]} for s in order],
    "board": [[int(grid.loc[(grid.stop_id == s) & (grid.hour == h), "boardings"].iloc[0])
               for h in HOURS] for s in order],
    "alight": [[int(grid.loc[(grid.stop_id == s) & (grid.hour == h), "alightings"].iloc[0])
                for h in HOURS] for s in order],
}
data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")

HTML = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>정류장별 시간대 승하차 히트맵</title>
<style>
  :root { --bg:#ffffff; --fg:#1f2328; --muted:#656d76; --line:#d0d7de; --accent:#0969da; }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) { --bg:#0d1117; --fg:#e6edf3; --muted:#8b949e; --line:#30363d; --accent:#58a6ff; }
  }
  :root[data-theme="dark"] { --bg:#0d1117; --fg:#e6edf3; --muted:#8b949e; --line:#30363d; --accent:#58a6ff; }
  body { margin:0; background:var(--bg); color:var(--fg); font-family:system-ui,-apple-system,"Malgun Gothic",sans-serif; }
  main { padding:16px; max-width:1100px; margin:0 auto; }
  h1 { font-size:20px; margin:4px 0 6px; }
  .meta { color:var(--muted); font-size:13px; margin-bottom:12px; }
  .tabs { display:flex; gap:8px; margin-bottom:12px; }
  .tabs button { font:inherit; padding:6px 14px; border:1px solid var(--line); border-radius:6px;
                 background:transparent; color:var(--fg); cursor:pointer; }
  .tabs button[aria-pressed="true"] { border-color:var(--accent); color:var(--accent); font-weight:600; }
  .wrap { overflow-x:auto; }
  table { border-collapse:separate; border-spacing:2px; font-size:12px; }
  th { font-weight:500; color:var(--muted); padding:0 4px; white-space:nowrap; }
  th.row { text-align:right; color:var(--fg); }
  td.cell { width:26px; height:26px; min-width:26px; text-align:center; border-radius:3px;
            font-variant-numeric:tabular-nums; }
  .legend { display:flex; align-items:center; gap:8px; margin-top:12px; font-size:12px; color:var(--muted); }
  .legend .bar { width:160px; height:10px; border-radius:3px;
                 background:linear-gradient(to right, var(--lo), var(--hi)); }
</style>
</head>
<body>
<main>
  <h1>정류장별 시간대 승하차 히트맵</h1>
  <div class="meta" id="meta"></div>
  <div class="tabs" role="group" aria-label="지표 선택">
    <button type="button" data-mode="board" aria-pressed="true">승차</button>
    <button type="button" data-mode="alight" aria-pressed="false">하차</button>
  </div>
  <div class="wrap"><table id="grid"></table></div>
  <div class="legend"><span>적음</span><span class="bar"></span><span>많음</span></div>
</main>
<script>
const DATA = __DATA__;
const LO = [255, 247, 236], HI = [180, 35, 24];

function mix(t) {
  const c = LO.map((v, i) => Math.round(v + (HI[i] - v) * t));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

function render(mode) {
  const values = DATA[mode];
  const max = Math.max(1, ...values.flat());
  const table = document.getElementById("grid");
  let html = "<thead><tr><th></th>";
  DATA.hours.forEach(h => html += `<th>${h}</th>`);
  html += "</tr></thead><tbody>";
  DATA.stops.forEach((s, i) => {
    html += `<tr><th class="row" title="${s.id}">${s.name}</th>`;
    values[i].forEach((v, j) => {
      const t = v / max;
      const ink = t > 0.55 ? "#fff" : "var(--fg)";
      html += `<td class="cell" style="background:${mix(t)};color:${ink}"`
            + ` title="${s.name} ${DATA.hours[j]}시: ${v}명">${v || ""}</td>`;
    });
    html += "</tr>";
  });
  table.innerHTML = html + "</tbody>";
  document.querySelectorAll(".tabs button").forEach(b =>
    b.setAttribute("aria-pressed", String(b.dataset.mode === mode)));
  document.getElementById("meta").textContent =
    `분석 기간 ${DATA.period} · ${mode === "board" ? "승차" : "하차"} 수 (칸 = 정류장 × 시간대, 시 단위)`;
}

document.querySelectorAll(".tabs button").forEach(b =>
  b.addEventListener("click", () => render(b.dataset.mode)));
render("board");
</script>
</body>
</html>
"""

html_path = out / "stop_congestion.html"
html_path.write_text(HTML.replace("__DATA__", data_json), encoding="utf-8")
print("저장:", html_path)
