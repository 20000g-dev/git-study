"""노선별·시간대별 혼잡도(구간 재차 인원) 분석.

재차 인원 = 어떤 정류장 구간(seq k -> k+1)을 통과할 때 승차 후 아직 하차하지 않은 탑승객 수.
구간 통과 시각은 승차~하차 시간을 구간 수로 선형 보간해 추정한다.
"""
from pathlib import Path

import pandas as pd

bus = pd.read_excel("data/bus_routes.xlsx", sheet_name=None)
routes, stops = bus["routes"], bus["stops"]
taps = pd.read_excel("data/card_taps.xlsx", sheet_name="tap_log",
                     parse_dates=["board_time", "alight_time"])
n_days = taps["board_time"].dt.normalize().nunique()

# 승/하차 정류장 -> 노선 내 순번 (같은 정류장이 한 노선에 한 번만 등장)
seq = stops.set_index(["route_id", "stop_id"])["stop_seq"]
taps["b_seq"] = [seq[(r, s)] for r, s in zip(taps.route_id, taps.board_stop_id)]
taps["a_seq"] = [seq[(r, s)] for r, s in zip(taps.route_id, taps.alight_stop_id)]

# 탑승 1건을 통과 구간별 행으로 전개
rows = []
for t in taps.itertuples():
    n = t.a_seq - t.b_seq
    step = (t.alight_time - t.board_time) / n
    for k in range(t.b_seq, t.a_seq):
        rows.append((t.route_id, k, t.board_time + step * (k - t.b_seq)))
seg = pd.DataFrame(rows, columns=["route_id", "seg_seq", "pass_time"])
seg["hour"] = seg["pass_time"].dt.hour

# 구간 정보: 구간 k = stop_seq k -> k+1
nm = stops.set_index(["route_id", "stop_seq"])["stop_name"]
segs = seg.groupby(["route_id", "seg_seq", "hour"]).size().rename("total_pass").reset_index()
segs["avg_daily_load"] = segs["total_pass"] / n_days  # 일평균 해당 시간대 구간 통과 승객
segs["segment"] = [f"{nm[(r, k)]}→{nm[(r, k + 1)]}" for r, k in zip(segs.route_id, segs.seg_seq)]
segs = segs.merge(routes[["route_id", "route_name", "route_type", "interval_min"]], on="route_id")
segs["buses_per_hour"] = 60 / segs["interval_min"]
segs["load_per_bus"] = segs["avg_daily_load"] / segs["buses_per_hour"]  # 버스 1대당 추정 재차 인원

# 노선·시간대 피크 (구간 최대 재차)
rh = segs.loc[segs.groupby(["route_id", "hour"])["load_per_bus"].idxmax()]
peak = rh.loc[rh.groupby("route_id")["load_per_bus"].idxmax()].sort_values("load_per_bus", ascending=False)

print(f"분석 기간 {n_days}일, 탑승 {len(taps)}건, 구간통과 {len(seg)}건")
print("\n=== 노선별 피크 시간대 (구간 최대 버스당 재차 인원) ===")
print(peak[["route_name", "route_type", "interval_min", "hour", "segment",
            "avg_daily_load", "load_per_bus"]].round(2).to_string(index=False))

print("\n=== 노선×시간대 최대 구간 버스당 재차 (상위 시간대) ===")
pivot = rh.pivot(index="route_name", columns="hour", values="load_per_bus").round(1)
print(pivot.fillna(0).to_string())

top5 = segs.sort_values("load_per_bus", ascending=False).head(5)
print("\n=== 가장 혼잡한 구간 TOP5 (노선·시간대·구간 단위) ===")
print(top5[["route_name", "hour", "segment", "avg_daily_load", "interval_min", "load_per_bus"]]
      .round(2).to_string(index=False))

# 배차간격 시사점: 피크 시 버스당 재차 대비 필요 배차
print("\n=== 배차간격 대비 시사점 ===")
peak = peak.copy()
TARGET = peak["load_per_bus"].median()
for r in peak.itertuples():
    need = r.avg_daily_load / TARGET  # 중앙값 수준 혼잡으로 맞추려면 필요한 시간당 대수
    new_int = 60 / need if need > 0 else r.interval_min
    msg = "배차 단축 검토" if r.load_per_bus > TARGET else "현행 유지/감회 여지"
    print(f"{r.route_name}: 피크 {r.hour}시 {r.segment}, 현재 {r.interval_min}분 간격 "
          f"버스당 {r.load_per_bus:.2f}명 -> {msg}"
          + (f" (중앙값 {TARGET:.2f}명 수준이면 약 {new_int:.0f}분)" if r.load_per_bus > TARGET else ""))
print("※ 더미 데이터는 승객 표본(2,000건)이라 절대 인원은 작음. 노선 간 상대 비교 용도.")

out = Path("results"); out.mkdir(exist_ok=True)
segs[["route_id", "route_name", "route_type", "interval_min", "hour", "seg_seq", "segment",
      "total_pass", "avg_daily_load", "buses_per_hour", "load_per_bus"]] \
    .sort_values(["route_id", "hour", "seg_seq"]).round(3) \
    .to_csv(out / "congestion_summary.csv", index=False, encoding="utf-8-sig")
print("\n저장:", out / "congestion_summary.csv")
