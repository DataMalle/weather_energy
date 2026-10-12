# Databricks notebook source
# MAGIC %md
# MAGIC # Datakvalitet: circuit breaker före gold
# MAGIC Resultaten sparas i `quality_results` (visas i appen). Kritiska fel stoppar jobbet, så att gold-tabellerna
# MAGIC och därmed appen behåller senaste *kontrollerade* data.

# COMMAND ----------

from datetime import timezone

from pyspark.sql import functions as F

from elvader_lib import run_quality_checks

dbutils.widgets.text("catalog", "workspace")
catalog = dbutils.widgets.get("catalog")
p = f"{catalog}.elvader_pipeline"
g = f"{catalog}.elvader_gold"


def aware(ts):
    return ts.replace(tzinfo=timezone.utc) if ts is not None else None


price = spark.sql(f"""
SELECT COUNT(*) AS rows, COUNT(DISTINCT zone) AS zones,
       SUM(CASE WHEN price_sek_kwh IS NULL THEN 1 ELSE 0 END) AS nulls,
       MIN(price_sek_kwh) AS pmin, MAX(price_sek_kwh) AS pmax
FROM {p}.silver_prices""").first()
dupes = spark.sql(f"""
SELECT COUNT(*) AS c FROM (SELECT zone, ts_start FROM {p}.silver_prices GROUP BY zone, ts_start HAVING COUNT(*) > 1)
""").first()["c"]
min_end = spark.sql(f"SELECT MIN(e) AS e FROM (SELECT MAX(ts_end) AS e FROM {p}.silver_prices GROUP BY zone)").first()["e"]
weather = spark.sql(f"""
SELECT COUNT(*) AS rows, MAX(_ingested_at) AS last_ingest,
       MIN(temperature_c) AS tmin, MAX(temperature_c) AS tmax, MIN(wind_ms) AS wmin, MAX(wind_ms) AS wmax
FROM {p}.silver_weather""").first()

metrics = {
    "price_rows": price["rows"], "price_zones": price["zones"], "price_nulls": price["nulls"] or 0,
    "price_dupes": dupes, "price_min": price["pmin"], "price_max": price["pmax"],
    "price_min_zone_latest_end": aware(min_end),
    "weather_rows": weather["rows"], "weather_latest_ingest": aware(weather["last_ingest"]),
    "temp_min": weather["tmin"], "temp_max": weather["tmax"], "wind_min": weather["wmin"], "wind_max": weather["wmax"],
}
results = run_quality_checks(metrics)

# COMMAND ----------

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {g}.quality_results (
  run_ts TIMESTAMP, check_name STRING, severity STRING, passed BOOLEAN, detail STRING
)""")
df = spark.createDataFrame(results, "check_name string, severity string, passed boolean, detail string").withColumn(
    "run_ts", F.current_timestamp()
).select("run_ts", "check_name", "severity", "passed", "detail")
df.write.mode("append").saveAsTable(f"{g}.quality_results")
display(df)

critical_failed = [r for r in results if r["severity"] == "critical" and not r["passed"]]
if critical_failed:
    raise Exception("Kritiska kvalitetskontroller misslyckades: " + ", ".join(r["check_name"] for r in critical_failed))
print(f"OK: {sum(r['passed'] for r in results)}/{len(results)} kontroller godkända")
