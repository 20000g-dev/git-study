"""xlsx 더미 데이터를 pandas로 읽어 기본 확인/집계를 해본다."""
import pandas as pd

# sheet_name=None -> 모든 시트를 {시트명: DataFrame} 딕셔너리로 읽는다
bus = pd.read_excel("data/bus_routes.xlsx", sheet_name=None)
routes, stops = bus["routes"], bus["stops"]

taps = pd.read_excel(
    "data/card_taps.xlsx",
    sheet_name="tap_log",
    parse_dates=["board_time", "alight_time"],
)

for name, df in [("routes", routes), ("stops", stops), ("taps", taps)]:
    print(f"\n=== {name} {df.shape} ===")
    print(df.head(3))

# 노선별 승차 건수 / 요금 합계 (노선 정보와 병합)
by_route = (
    taps.merge(routes[["route_id", "route_name", "route_type"]], on="route_id")
    .groupby(["route_id", "route_name", "route_type"])
    .agg(rides=("tap_id", "count"), revenue=("fare", "sum"))
    .reset_index()
)
print("\n=== 노선별 이용 ===")
print(by_route)

# 시간대별 승차 건수
print("\n=== 시간대별 승차 ===")
print(taps.groupby(taps["board_time"].dt.hour).size())

# 승차 정류장 TOP 5 (정류장명 매핑)
stop_map = stops.drop_duplicates("stop_id").set_index("stop_id")["stop_name"]
print("\n=== 승차 정류장 TOP5 ===")
print(taps["board_stop_id"].map(stop_map).value_counts().head(5))
