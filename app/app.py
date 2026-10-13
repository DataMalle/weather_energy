import os
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

from style import GRAY_500, TEAL, hero, inject_style

st.set_page_config(page_title="Elpris & väder - Malvin Portfolio Project", page_icon="⚡", layout="wide")

# Streamlit Community Cloud: lägg secrets i miljön så att Databricks-SDK:t hittar dem.
try:
    for _key, _val in st.secrets.items():
        if isinstance(_val, str):
            os.environ.setdefault(_key, _val)
except Exception:  # inga secrets konfigurerade
    pass

_missing = [k for k in ("DATABRICKS_HOST", "DATABRICKS_WAREHOUSE_ID") if not os.environ.get(k)]
if _missing:
    st.error(f"Appen saknar konfiguration: {', '.join(_missing)}. Lägg till dem under App settings → Secrets.")
    st.stop()

CATALOG = os.environ.get("CATALOG", "workspace")
WAREHOUSE_ID = os.environ["DATABRICKS_WAREHOUSE_ID"]
G = f"{CATALOG}.elvader_gold"
STHLM = ZoneInfo("Europe/Stockholm")
ZONES = {"SE1": "Luleå", "SE2": "Östersund", "SE3": "Stockholm", "SE4": "Malmö"}
REPO_URL = "https://github.com/DataMalle/weather_energy"


@st.cache_resource
def client() -> WorkspaceClient:
    return WorkspaceClient()


_DONE = {StatementState.SUCCEEDED, StatementState.FAILED, StatementState.CANCELED, StatementState.CLOSED}


def _execute(sql: str, max_wait_s: int = 240):
    """Kör SQL och väntar klart, även om warehouse måste startas först (kan ta flera minuter)."""
    api = client().statement_execution
    res = api.execute_statement(statement=sql, warehouse_id=WAREHOUSE_ID, catalog=CATALOG, wait_timeout="30s")
    deadline = time.monotonic() + max_wait_s
    while res.status.state not in _DONE:
        if time.monotonic() > deadline:
            raise TimeoutError("Databricks SQL warehouse startade inte i tid")
        time.sleep(2)
        res = api.get_statement(res.statement_id)
    return res


@st.cache_data(ttl=600, show_spinner=False)
def query(sql: str) -> pd.DataFrame:
    last: Exception | None = None
    for attempt in range(3):  # tåla tillfälliga fel vid kallstart
        try:
            res = _execute(sql)
            if res.status.state == StatementState.SUCCEEDED:
                break
            last = RuntimeError(res.status.error.message if res.status.error else str(res.status.state))
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(3 * (attempt + 1))
    else:
        raise last
    cols = [c.name for c in res.manifest.schema.columns]
    rows = res.result.data_array if res.result and res.result.data_array else []
    df = pd.DataFrame(rows, columns=cols)
    for col in df.columns:
        try:
            df[col] = pd.to_numeric(df[col])
        except (ValueError, TypeError):
            pass
    return df


def to_local_naive(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, utc=True).dt.tz_localize(None)


def minutes_ago(ts) -> str:
    delta = datetime.now(timezone.utc) - pd.to_datetime(ts, utc=True).to_pydatetime()
    mins = int(delta.total_seconds() // 60)
    return f"{mins} min sedan" if mins < 120 else f"{mins // 60} h sedan"


inject_style()
hero(
    "Elpris &amp; väder",
    "Malvin Portfolio Project · Live-pipeline i Databricks med elpriser och väder för Sveriges fyra elområden",
    "Live · uppdateras var tredje timme",
)

try:
    with st.spinner("Hämtar data från Databricks (kan ta upp till någon minut om warehouse sover)..."):
        query("SELECT 1")  # väcker warehouse först, så att övriga frågor går snabbt
        hourly = query(f"SELECT * FROM {G}.gold_hourly ORDER BY zone, hour_utc")
        daily = query(f"SELECT * FROM {G}.gold_daily ORDER BY zone, day_local")
        cheapest = query(f"SELECT * FROM {G}.gold_cheapest_next WHERE price_rank <= 5 ORDER BY zone, price_rank")
        corr = query(f"SELECT * FROM {G}.gold_correlation ORDER BY zone")
        status = query(f"SELECT * FROM {G}.gold_status")
        runs = query(f"SELECT * FROM {G}.pipeline_runs ORDER BY run_ts DESC LIMIT 1")
        quality = query(
            f"SELECT check_name, severity, passed, detail FROM {G}.quality_results "
            f"WHERE run_ts = (SELECT MAX(run_ts) FROM {G}.quality_results) ORDER BY severity, check_name"
        )
except Exception as e:  # noqa: BLE001 - visa fel för besökaren
    st.error(f"Kunde inte hämta data just nu: {e}")
    if st.button("Försök igen"):
        st.cache_data.clear()
        st.rerun()
    st.stop()

if hourly.empty:
    st.warning("Inga data ännu. Pipelinen har inte körts färdigt.")
    st.stop()

hourly["hour_utc"] = pd.to_datetime(hourly["hour_utc"], utc=True)
hourly["hour_local"] = to_local_naive(hourly["hour_local"])
hourly["price_ore"] = hourly["price_sek_kwh"] * 100

tab_overview, tab_pipeline = st.tabs(["📈 Översikt", "🛠️ Pipeline & datakvalitet"])

with tab_overview:
    zone = st.pills("Elområde", list(ZONES), default="SE3", format_func=lambda z: f"{z} {ZONES[z]}", label_visibility="collapsed") or "SE3"
    z = hourly[hourly["zone"] == zone]
    now_utc = pd.Timestamp.now(tz="UTC")
    today_local = datetime.now(STHLM).date()

    past = z[z["hour_utc"] <= now_utc]
    current = past.iloc[-1] if not past.empty else z.iloc[0]
    today_rows = z[z["hour_local"].dt.date == today_local]

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Pris just nu, per kWh", f"{current['price_ore']:.0f} öre")
    if not today_rows.empty:
        cheapest_today = today_rows.loc[today_rows["price_ore"].idxmin()]
        c2.metric("Medel idag, per kWh", f"{today_rows['price_ore'].mean():.0f} öre")
        c3.metric(f"Billigast idag, kl {cheapest_today['hour_local']:%H}:00", f"{cheapest_today['price_ore']:.0f} öre")
    c4.metric(f"Temperatur, {ZONES[zone]}", f"{current['temperature_c']:.1f} °C")
    c5.metric(f"Vind, {ZONES[zone]}", f"{current['wind_ms']:.1f} m/s")

    with st.container(border=True, key="card_price"):
        st.subheader("Elpris, senaste dagarna och imorgon")
        window = z[z["hour_local"] >= pd.Timestamp(today_local) - pd.Timedelta(days=2)]
        st.line_chart(window.set_index("hour_local")["price_ore"], y_label="öre/kWh", x_label="", color=TEAL)

    left, right = st.columns(2)
    with left, st.container(border=True, key="card_cheapest"):
        st.subheader("Billigaste timmarna, kommande dygn")
        ch = cheapest[cheapest["zone"] == zone].copy()
        if ch.empty:
            st.info("Inga framtida priser tillgängliga ännu.")
        else:
            ch["Tid"] = to_local_naive(ch["hour_local"]).dt.strftime("%a %H:00")
            ch["Pris (öre/kWh)"] = (ch["price_sek_kwh"] * 100).round(0).astype(int)
            st.dataframe(ch[["price_rank", "Tid", "Pris (öre/kWh)"]].rename(columns={"price_rank": "#"}), hide_index=True, width="stretch")
    with right, st.container(border=True, key="card_scatter"):
        st.subheader("Blåser det mycket, blir det billigare?")
        st.scatter_chart(z.dropna(subset=["wind_ms"]), x="wind_ms", y="price_ore", x_label="vind (m/s)", y_label="öre/kWh", color=TEAL)

    with st.container(border=True, key="card_corr"):
        st.subheader("Samband mellan väder och pris per elområde")
        st.caption("Korrelation (−1 till 1) över all inladdad historik. Negativt värde betyder lägre pris när det blåser mer/är varmare.")
        cc = corr.set_index("zone")[["corr_wind_price", "corr_temp_price"]].rename(
            columns={"corr_wind_price": "vind och pris", "corr_temp_price": "temperatur och pris"}
        )
        st.bar_chart(cc, color=[TEAL, GRAY_500], stack=False)

with tab_pipeline:
    st.subheader("Datafärskhet")
    if not runs.empty:
        r = runs.iloc[0]
        a, b, c = st.columns(3)
        a.metric("Senaste pipelinekörning", minutes_ago(r["run_ts"]))
        a2 = int(r["checks_passed"]) if pd.notna(r["checks_passed"]) else 0
        b.metric("Kvalitetskontroller godkända", f"{a2} av {int(r['checks_total'])}")
        c.metric("Rader i silver", f"{int(r['price_rows']) + int(r['weather_rows']):,}".replace(",", " "))
    st.dataframe(
        status.assign(
            **{
                "Senaste data till": to_local_naive(status["latest_data_time"]).dt.strftime("%Y-%m-%d %H:%M"),
                "Hämtad": status["last_ingested_at"].map(minutes_ago),
            }
        )[["source", "Senaste data till", "Hämtad", "row_count"]].rename(columns={"source": "Källa", "row_count": "Rader"}),
        hide_index=True,
        width="stretch",
    )

    st.subheader("Datakvalitetskontroller (senaste körning)")
    q = quality.copy()
    q["Status"] = q["passed"].astype(str).str.lower().map({"true": "✅ OK", "false": "⚠️ Avvikelse"})
    st.dataframe(
        q[["Status", "check_name", "severity", "detail"]].rename(columns={"check_name": "Kontroll", "severity": "Allvar", "detail": "Detalj"}),
        hide_index=True,
        width="stretch",
    )
    st.caption("Kritiska kontroller stoppar publiceringen: misslyckas de behåller appen senaste kontrollerade data.")

    st.subheader("Så fungerar pipelinen")
    st.graphviz_chart(
        """
        digraph G {
          rankdir=LR; node [shape=box, style="rounded,filled", fillcolor="#eef2ff", fontname="Helvetica"];
          om [label="Open-Meteo\\n(väder, pull)"]; ep [label="elprisetjustnu.se\\n(elpris)"];
          gh [label="GitHub Actions\\n(push, var 3:e timme)"]; vol [label="Volume: landing"];
          bw [label="bronze_weather"]; bp [label="bronze_prices\\n(COPY INTO)"];
          s [label="silver\\n(MERGE, UTC)"]; q [label="kvalitets-\\nkontroller", fillcolor="#fff7e6"];
          g [label="gold"]; app [label="Streamlit-app", fillcolor="#e6ffed"];
          om -> bw; ep -> gh -> vol -> bp; bw -> s; bp -> s; s -> q -> g -> app;
        }
        """
    )
    st.markdown(f"Källkod, arkitektur och designbeslut: [{REPO_URL}]({REPO_URL})")
