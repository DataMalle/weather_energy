# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: affärsklara tabeller för appen (schema `elvader_gold`)

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
catalog = dbutils.widgets.get("catalog")
p = f"{catalog}.elvader_pipeline"
g = f"{catalog}.elvader_gold"

# COMMAND ----------

# Timpriser (medel av kvartspriser) ihop med väder för elområdets referensstad.
spark.sql(f"""
CREATE OR REPLACE TABLE {g}.gold_hourly
COMMENT 'Elpris (SEK/kWh, timmedel), temperatur och vind per elområde och timme'
AS
WITH price_h AS (
  SELECT zone, date_trunc('hour', ts_start) AS hour_utc, AVG(price_sek_kwh) AS price_sek_kwh
  FROM {p}.silver_prices GROUP BY zone, date_trunc('hour', ts_start)
)
SELECT p.zone, w.city, p.hour_utc,
       from_utc_timestamp(p.hour_utc, 'Europe/Stockholm') AS hour_local,
       ROUND(p.price_sek_kwh, 4) AS price_sek_kwh,
       w.temperature_c, w.wind_ms
FROM price_h p
LEFT JOIN {p}.silver_weather w ON w.zone = p.zone AND w.ts_utc = p.hour_utc
""")

spark.sql(f"""
CREATE OR REPLACE TABLE {g}.gold_daily
COMMENT 'Dagssammanfattning per elområde: pris (medel/min/max), temperatur och vind'
AS SELECT zone, city, to_date(hour_local) AS day_local,
          ROUND(AVG(price_sek_kwh), 4) AS avg_price, ROUND(MIN(price_sek_kwh), 4) AS min_price,
          ROUND(MAX(price_sek_kwh), 4) AS max_price,
          ROUND(AVG(temperature_c), 1) AS avg_temp_c, ROUND(AVG(wind_ms), 1) AS avg_wind_ms,
          COUNT(*) AS hours
FROM {g}.gold_hourly GROUP BY zone, city, to_date(hour_local)
""")

spark.sql(f"""
CREATE OR REPLACE TABLE {g}.gold_cheapest_next
COMMENT 'De 24 kommande timmarna per elområde rankade från billigast'
AS SELECT zone, hour_local, price_sek_kwh,
          RANK() OVER (PARTITION BY zone ORDER BY price_sek_kwh) AS price_rank
FROM {g}.gold_hourly
WHERE hour_utc >= date_trunc('hour', current_timestamp())
  AND hour_utc < date_trunc('hour', current_timestamp()) + INTERVAL 24 HOURS
""")

spark.sql(f"""
CREATE OR REPLACE TABLE {g}.gold_correlation
COMMENT 'Korrelation mellan vind/temperatur och elpris per elområde'
AS SELECT zone, ROUND(corr(wind_ms, price_sek_kwh), 3) AS corr_wind_price,
          ROUND(corr(temperature_c, price_sek_kwh), 3) AS corr_temp_price, COUNT(*) AS n_hours
FROM {g}.gold_hourly WHERE wind_ms IS NOT NULL AND temperature_c IS NOT NULL GROUP BY zone
""")

# COMMAND ----------

# Färskhet och körlogg
spark.sql(f"""
CREATE OR REPLACE TABLE {g}.gold_status
COMMENT 'Färskhet per datakälla'
AS
SELECT 'Elpriser (via GitHub Actions)' AS source, MAX(ts_end) AS latest_data_time, MAX(_ingested_at) AS last_ingested_at,
       COUNT(*) AS row_count FROM {p}.silver_prices
UNION ALL
SELECT 'Väder (Open-Meteo)', MAX(ts_utc), MAX(_ingested_at), COUNT(*) FROM {p}.silver_weather
""")

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {g}.pipeline_runs (
  run_ts TIMESTAMP, price_rows BIGINT, weather_rows BIGINT, checks_passed BIGINT, checks_total BIGINT
)""")
spark.sql(f"""
INSERT INTO {g}.pipeline_runs
SELECT current_timestamp(),
       (SELECT COUNT(*) FROM {p}.silver_prices), (SELECT COUNT(*) FROM {p}.silver_weather),
       (SELECT COUNT(*) FROM {g}.quality_results WHERE run_ts = (SELECT MAX(run_ts) FROM {g}.quality_results) AND passed),
       (SELECT COUNT(*) FROM {g}.quality_results WHERE run_ts = (SELECT MAX(run_ts) FROM {g}.quality_results))
""")

for t in ["gold_hourly", "gold_daily", "gold_cheapest_next", "gold_correlation", "gold_status", "pipeline_runs"]:
    print(t, spark.table(f"{g}.{t}").count())
