"""요금·카드유형 수익 분석. 결과는 콘솔 + results/fare_summary.csv."""
from pathlib import Path

import pandas as pd

GENERAL_FARE = 1500  # 일반요금 기준 (무임 손실 추정용)

routes = pd.read_excel("data/bus_routes.xlsx", sheet_name="routes")
taps = pd.read_excel("data/card_taps.xlsx", sheet_name="tap_log",
                     parse_dates=["board_time", "alight_time"])
df = taps.merge(routes[["route_id", "route_name", "route_type"]], on="route_id")
total_rev, total_n = df["fare"].sum(), len(df)
rows = []  # (분석구분, 항목, 이용건수, 요금합계, 비중(%), 건당평균)


def add(section, g):
    for k, r in g.iterrows():
        rows.append((section, str(k), int(r.rides), int(r.revenue),
                     round(r.revenue / total_rev * 100, 1) if total_rev else 0,
                     round(r.revenue / r.rides, 1)))


def agg(by):
    return df.groupby(by).agg(rides=("tap_id", "count"), revenue=("fare", "sum"))


# 1) 카드유형별
ct = agg("card_type")
ct["ride_share"] = (ct.rides / total_n * 100).round(1)
ct["rev_share"] = (ct.revenue / total_rev * 100).round(1)
print("=== 카드유형별 ===\n", ct.sort_values("revenue", ascending=False))
add("카드유형", ct.sort_values("revenue", ascending=False))

# 2) 노선유형별
rt = agg("route_type").sort_values("revenue", ascending=False)
print("\n=== 노선유형별 수익 ===\n", rt)
add("노선유형", rt)

# 3) 요일/일자별
df["date"] = df["board_time"].dt.strftime("%Y-%m-%d") + \
    "(" + df["board_time"].dt.dayofweek.map(dict(enumerate("월화수목금토일"))) + ")"
dd = agg("date")
print("\n=== 일자별 수익 ===\n", dd)
add("일자", dd)

# 4) 무임(0원) 비중 및 손실
free = df[df["fare"] == 0]
loss = len(free) * GENERAL_FARE
print(f"\n=== 무임 ===\n0원 승객 {len(free)}건 / {total_n}건 ({len(free)/total_n*100:.1f}%), "
      f"일반요금 {GENERAL_FARE}원 기준 손실 추정 {loss:,}원 (실수익 {total_rev:,}원, "
      f"무임 반영 시 잠재수익 {total_rev+loss:,}원 대비 {loss/(total_rev+loss)*100:.1f}%)")
rows.append(("무임", "0원 승객", len(free), loss, round(len(free)/total_n*100, 1), 0.0))

# 5) 노선별 건당 평균 수익
br = df.groupby(["route_id", "route_name"]).agg(
    rides=("tap_id", "count"), revenue=("fare", "sum"))
br["avg"] = (br.revenue / br.rides).round(1)
br = br.sort_values("avg", ascending=False)
print("\n=== 노선별 건당 평균 수익 (높은 순) ===\n", br)
for (rid, name), r in br.iterrows():
    rows.append(("노선별건당평균", f"{rid} {name}", int(r.rides), int(r.revenue),
                 round(r.revenue / total_rev * 100, 1), r.avg))
print(f"\n최고: {br.index[0][1]} ({br.avg.iloc[0]}원), 최저: {br.index[-1][1]} ({br.avg.iloc[-1]}원)")

Path("results").mkdir(exist_ok=True)
pd.DataFrame(rows, columns=["분석구분", "항목", "이용건수", "요금합계", "비중(%)", "건당평균"]) \
    .to_csv("results/fare_summary.csv", index=False, encoding="utf-8-sig")
print("\n저장: results/fare_summary.csv")
