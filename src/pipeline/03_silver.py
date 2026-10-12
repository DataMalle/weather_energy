# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: typning, dedupe och MERGE (upsert)
# MAGIC Senast hämtade värdet per nyckel vinner. Tider lagras i UTC.

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
catalog = dbutils.widgets.get("catalog")
p = f"{catalog}.elvader_pipeline"

# COMMAND ----------

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {p}.silver_prices (
  zone STRING, ts_start TIMESTAMP, ts_end TIMESTAMP,
  price_sek_kwh DOUBLE, price_eur_kwh DOUBLE, _ingested_at TIMESTAMP
)""")

spark.sql(f"""
MERGE INTO {p}.silver_prices t
USING (
  SELECT zone, ts_start, ts_end, price_sek_kwh, price_eur_kwh, _ingested_at FROM (
    SELECT zone,
           to_timestamp(time_start) AS ts_start,
           to_timestamp(time_end) AS ts_end,
           SEK_per_kWh AS price_sek_kwh,
           EUR_per_kWh AS price_eur_kwh,
           _ingested_at,
           ROW_NUMBER() OVER (PARTITION BY zone, to_timestamp(time_start) ORDER BY _ingested_at DESC) AS rn
    FROM {p}.bronze_prices
    WHERE zone IS NOT NULL AND time_start IS NOT NULL
  ) WHERE rn = 1
) s
ON t.zone = s.zone AND t.ts_start = s.ts_start
WHEN MATCHED AND s._ingested_at > t._ingested_at THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
""")

# COMMAND ----------

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {p}.silver_weather (
  zone STRING, city STRING, ts_utc TIMESTAMP,
  temperature_c DOUBLE, wind_ms DOUBLE, _ingested_at TIMESTAMP
)""")

# Open-Meteo levererar lokal tid (Europe/Stockholm) utan offset -> konvertera till UTC.
spark.sql(f"""
MERGE INTO {p}.silver_weather t
USING (
  SELECT zone, city, ts_utc, temperature_c, wind_ms, _ingested_at FROM (
    SELECT zone, city,
           to_utc_timestamp(to_timestamp(ts_local), 'Europe/Stockholm') AS ts_utc,
           temperature_c, wind_ms, _ingested_at,
           ROW_NUMBER() OVER (PARTITION BY zone, ts_local ORDER BY _ingested_at DESC) AS rn
    FROM {p}.bronze_weather
    WHERE zone IS NOT NULL AND ts_local IS NOT NULL
  ) WHERE rn = 1
) s
ON t.zone = s.zone AND t.ts_utc = s.ts_utc
WHEN MATCHED AND s._ingested_at > t._ingested_at THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
""")

for t in ["silver_prices", "silver_weather"]:
    print(t, spark.table(f"{p}.{t}").count())
