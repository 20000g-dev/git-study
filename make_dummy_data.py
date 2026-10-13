"""가상 버스 노선 / 교통카드 승하차 더미 데이터를 xlsx로 생성한다."""
from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
OUT = Path("data")
OUT.mkdir(exist_ok=True)

# ---------- 1) 버스 노선 데이터 (시트: routes, stops) ----------
route_ids = [f"R{100 + i}" for i in range(1, 6)]
route_types = ["간선", "지선", "광역", "간선", "마을"]
routes = pd.DataFrame({
    "route_id": route_ids,
    "route_name": [f"{100 + i}번" for i in range(1, 6)],
    "route_type": route_types,
    "first_bus": ["05:00", "05:30", "04:30", "05:00", "06:00"],
    "last_bus": ["23:30", "23:00", "22:30", "23:30", "21:00"],
    "interval_min": [8, 12, 15, 10, 20],
})

stop_names = ["시청앞", "중앙시장", "역사공원", "대학로", "병원앞", "도서관", "체육관",
              "버스터미널", "신도시", "강변마을", "산업단지", "공항입구"]
stop_rows = []
for rid in route_ids:
    n = int(rng.integers(8, 12))
    chosen = rng.choice(len(stop_names), size=n, replace=False)
    for seq, idx in enumerate(chosen, start=1):
        stop_rows.append({
            "route_id": rid,
            "stop_seq": seq,
            "stop_id": f"S{idx + 1:03d}",
            "stop_name": stop_names[idx],
            "lat": round(37.50 + rng.uniform(-0.05, 0.05), 6),
            "lon": round(127.00 + rng.uniform(-0.05, 0.05), 6),
        })
stops = pd.DataFrame(stop_rows)

with pd.ExcelWriter(OUT / "bus_routes.xlsx") as w:
    routes.to_excel(w, sheet_name="routes", index=False)
    stops.to_excel(w, sheet_name="stops", index=False)

# ---------- 2) 교통카드 승하차 데이터 (시트: tap_log) ----------
card_ids = [f"C{rng.integers(10**7, 10**8)}" for _ in range(300)]
card_types = {c: rng.choice(["일반", "청소년", "어린이", "경로"], p=[.6, .15, .05, .2]) for c in card_ids}
fare = {"일반": 1500, "청소년": 1000, "어린이": 500, "경로": 0}

HOUR_W = np.array([3, 10, 14, 10, 5, 4, 4, 4, 4, 5, 6, 10, 12, 8, 5, 4, 3, 2, 1], dtype=float)  # 5~23시
rows = []
dates = pd.date_range("2026-10-05", periods=7)
for _ in range(2000):
    rid = rng.choice(route_ids)
    rs = stops[stops.route_id == rid].sort_values("stop_seq")
    i = int(rng.integers(0, len(rs) - 1))
    j = int(rng.integers(i + 1, len(rs)))
    # 출퇴근 시간대에 몰리도록 가중치
    hour = int(rng.choice(range(5, 24), p=HOUR_W / HOUR_W.sum()))
    board = (rng.choice(dates) + pd.Timedelta(hours=hour, minutes=int(rng.integers(0, 60))))
    ride_min = (j - i) * int(rng.integers(2, 5))
    card = rng.choice(card_ids)
    rows.append({
        "tap_id": None,
        "card_id": card,
        "card_type": card_types[card],
        "route_id": rid,
        "board_time": board,
        "board_stop_id": rs.iloc[i].stop_id,
        "alight_time": board + pd.Timedelta(minutes=ride_min),
        "alight_stop_id": rs.iloc[j].stop_id,
        "fare": fare[card_types[card]],
    })
taps = pd.DataFrame(rows).sort_values("board_time").reset_index(drop=True)
taps["tap_id"] = [f"T{n:06d}" for n in range(1, len(taps) + 1)]

with pd.ExcelWriter(OUT / "card_taps.xlsx", datetime_format="YYYY-MM-DD HH:MM:SS") as w:
    taps.to_excel(w, sheet_name="tap_log", index=False)

print("생성 완료:", *(p.as_posix() for p in OUT.glob("*.xlsx")))
