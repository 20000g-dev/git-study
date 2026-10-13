"""정류장 OD(승차->하차) 분석: 매트릭스, TOP10, 정류장별 승하차/순유입, 평균 승차시간/이동 정류장 수."""
from pathlib import Path

import pandas as pd

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 30)

stops = pd.read_excel("data/bus_routes.xlsx", sheet_name="stops")
taps = pd.read_excel(
    "data/card_taps.xlsx", sheet_name="tap_log", parse_dates=["board_time", "alight_time"]
)

# stop_id -> 정류장명 매핑: 같은 stop_id가 여러 노선에 중복되므로 이름이 일관된지 확인 후 중복 제거
assert stops.groupby("stop_id")["stop_name"].nunique().max() == 1, "stop_id별 정류장명 불일치"
stop_map = stops.drop_duplicates("stop_id").set_index("stop_id")["stop_name"]

taps["board_stop"] = taps["board_stop_id"].map(stop_map)
taps["alight_stop"] = taps["alight_stop_id"].map(stop_map)

# 정류장 순번은 (route_id, stop_id) 단위로 매핑해야 함 (stop_id만으로 조인하면 행이 중복됨)
seq = stops.set_index(["route_id", "stop_id"])["stop_seq"]
assert seq.index.is_unique
taps["board_seq"] = pd.MultiIndex.from_frame(taps[["route_id", "board_stop_id"]]).map(seq)
taps["alight_seq"] = pd.MultiIndex.from_frame(taps[["route_id", "alight_stop_id"]]).map(seq)
taps["stops_traveled"] = taps["alight_seq"] - taps["board_seq"]
taps["ride_min"] = (taps["alight_time"] - taps["board_time"]).dt.total_seconds() / 60

# 1) OD 매트릭스
od = taps.pivot_table(
    index="board_stop", columns="alight_stop", values="tap_id",
    aggfunc="count", fill_value=0, margins=True, margins_name="합계",
)
print("=== OD 매트릭스 (행: 승차, 열: 하차) ===")
print(od)

# 2) OD쌍 TOP10
od_pairs = (
    taps.groupby(["board_stop", "alight_stop"]).size().rename("trips")
    .reset_index().sort_values("trips", ascending=False, kind="stable")
)
top10 = od_pairs.head(10).reset_index(drop=True)
print("\n=== 통행량 상위 OD쌍 TOP10 ===")
print(top10)

# 3) 정류장별 승차/하차/순유입
board = taps["board_stop"].value_counts().rename("boardings")
alight = taps["alight_stop"].value_counts().rename("alightings")
flow = pd.concat([board, alight], axis=1).fillna(0).astype(int)
flow["net_inflow"] = flow["alightings"] - flow["boardings"]
flow = flow.sort_values("net_inflow", ascending=False)
print("\n=== 정류장별 승차/하차/순유입 ===")
print(flow)
print("\n순유입 상위 3:\n", flow.head(3))
print("\n순유입 하위 3 (순유출):\n", flow.tail(3).sort_values("net_inflow"))

# 4) 평균 승차 시간 / 평균 이동 정류장 수
print(f"\n평균 승차 시간: {taps['ride_min'].mean():.2f}분")
print(f"평균 이동 정류장 수: {taps['stops_traveled'].mean():.2f}개")

# 저장
Path("results").mkdir(exist_ok=True)
od.to_csv("results/od_matrix.csv", encoding="utf-8-sig")
top10.to_csv("results/od_top10.csv", index=False, encoding="utf-8-sig")
print("\n저장: results/od_matrix.csv, results/od_top10.csv")
