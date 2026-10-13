"""교통카드 승하차 데이터로 환승(30분 이내, 노선 변경)을 추정한다."""
from pathlib import Path

import pandas as pd

WINDOW = pd.Timedelta(minutes=30)

routes = pd.read_excel("data/bus_routes.xlsx", sheet_name="routes")
stops = pd.read_excel("data/bus_routes.xlsx", sheet_name="stops")
taps = pd.read_excel("data/card_taps.xlsx", sheet_name="tap_log",
                     parse_dates=["board_time", "alight_time"])

rname = routes.set_index("route_id")["route_name"]
sname = stops.drop_duplicates("stop_id").set_index("stop_id")["stop_name"]

# 카드별 승차 시각 순으로 정렬 후 직전 탑승 정보를 붙인다
taps = taps.sort_values(["card_id", "board_time"]).reset_index(drop=True)
g = taps.groupby("card_id")
taps["prev_route"] = g["route_id"].shift()
taps["prev_alight_time"] = g["alight_time"].shift()
taps["prev_alight_stop"] = g["alight_stop_id"].shift()
taps["gap"] = taps["board_time"] - taps["prev_alight_time"]

# 이전 하차 후 0~30분 이내 승차 + 노선 상이 -> 환승 추정
is_tr = (taps["gap"] >= pd.Timedelta(0)) & (taps["gap"] <= WINDOW) & (taps["prev_route"] != taps["route_id"])
tr = taps[is_tr].copy()
tr["wait_min"] = tr["gap"].dt.total_seconds() / 60
tr["pair"] = tr["prev_route"].map(rname) + " -> " + tr["route_id"].map(rname)
tr["stop_name"] = tr["prev_alight_stop"].map(sname)

total = len(taps)
n = len(tr)
ratio = n / total * 100
pair_top = tr["pair"].value_counts().head(5)
stop_top = tr["stop_name"].value_counts().head(5)
bins = [0, 5, 10, 15, 20, 25, 30]
dist = pd.cut(tr["wait_min"], bins=bins, include_lowest=True).value_counts().sort_index()

print(f"전체 탑승 {total}건, 환승 추정 {n}건 ({ratio:.2f}%)")
if n < 20:
    print("※ 더미 데이터 특성상 환승 건수가 매우 적어 통계적 의미는 제한적이다.")
print("\n=== 환승 노선쌍 TOP5 ===");  print(pair_top.to_string() if n else "(없음)")
print("\n=== 환승 정류장 TOP5 (하차 기준) ===");  print(stop_top.to_string() if n else "(없음)")
print("\n=== 환승 대기시간 분포(분) ===");  print(dist.to_string())
if n:
    print(f"\n평균 대기 {tr['wait_min'].mean():.1f}분, 중앙값 {tr['wait_min'].median():.1f}분")

rows = [("summary", "전체 탑승 건수", total), ("summary", "환승 추정 건수", n),
        ("summary", "환승 비율(%)", round(ratio, 2))]
rows += [("route_pair_top5", k, v) for k, v in pair_top.items()]
rows += [("stop_top5", k, v) for k, v in stop_top.items()]
rows += [("wait_dist_min", str(k), v) for k, v in dist.items()]
Path("results").mkdir(exist_ok=True)
pd.DataFrame(rows, columns=["category", "item", "value"]).to_csv(
    "results/transfer_summary.csv", index=False, encoding="utf-8-sig")
