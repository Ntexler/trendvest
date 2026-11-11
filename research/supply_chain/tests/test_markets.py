"""Day-0 alignment across exchanges, and the mechanical role assignment."""
import pandas as pd

from research.supply_chain import graph as G
from research.supply_chain import markets as MK

DAYS = pd.bdate_range("2021-03-01", "2024-04-30")


def day0(ticker, ts):
    return DAYS[MK.day0_position(ticker, DAYS, pd.Timestamp(ts, tz="UTC"))].date().isoformat()


def test_taiwan_quake_morning_hits_same_local_day_everywhere():
    # Hualien earthquake: 2024-04-03 07:58 Taipei = 2024-04-02 23:58 UTC (after the US close)
    ts = "2024-04-02 23:58"
    assert day0("2330.TW", ts) == "2024-04-03"
    assert day0("8035.T", ts) == "2024-04-03"
    assert day0("ASML.AS", ts) == "2024-04-03"
    assert day0("TSM", ts) == "2024-04-03"      # US session of 2 April had already closed


def test_japan_night_fire_reaches_wall_street_a_calendar_day_earlier():
    # Renesas Naka fire: 2021-03-19 02:47 Tokyo = 2021-03-18 17:47 UTC (US market still open)
    ts = "2021-03-18 17:47"
    assert day0("6723.T", ts) == "2021-03-19"
    assert day0("NVDA", ts) == "2021-03-18"


def test_event_after_local_close_moves_to_next_session():
    # 08:00 UTC = 16:00 Taipei, after the 13:30 close
    assert day0("2330.TW", "2024-04-03 08:00") == "2024-04-04"


def test_roles_follow_the_map():
    companies = pd.DataFrame({"segment": ["foundry", "foundry", "fabless", "system", "wafer", "bank"]},
                             index=["TSMC", "UMC", "NVDA", "DELL", "SUMCO", "JPM"])
    edges = pd.DataFrame({"supplier": ["TSMC", "NVDA", "SUMCO"], "customer": ["NVDA", "DELL", "TSMC"]})
    r = G.roles(["TSMC"], edges, companies)
    assert r == {"TSMC": "hit", "UMC": "rival", "NVDA": "down1", "DELL": "down2",
                 "SUMCO": "up1", "JPM": "control"}
