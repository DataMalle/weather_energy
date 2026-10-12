# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze: väder från Open-Meteo (pull)
# MAGIC Hämtar timvärden (temperatur, vind) för en referensstad per elområde, igår till imorgon.
# MAGIC Varje körning läggs till (append) med `_ingested_at`; dubbletter löses i silver.

# COMMAND ----------

from pyspark.sql import functions as F

from elvader_lib import ZONES, fetch_json, parse_weather, weather_url

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("weather_past_days", "2")  # sätt till t.ex. 16 för att backfilla (Open-Meteo stödjer max 92)
catalog = dbutils.widgets.get("catalog")
past_days = min(int(dbutils.widgets.get("weather_past_days")), 92)
pipeline = f"{catalog}.elvader_pipeline"

# COMMAND ----------

rows = []
for zone, (city, lat, lon) in ZONES.items():
    payload = fetch_json(weather_url(lat, lon, past_days=past_days))
    rows += parse_weather(payload, zone, city)
    print(f"{zone} {city}: {len(payload['hourly']['time'])} timmar")

df = spark.createDataFrame(
    rows, "zone string, city string, ts_local string, temperature_c double, wind_ms double"
).withColumn("_ingested_at", F.current_timestamp())

df.write.mode("append").saveAsTable(f"{pipeline}.bronze_weather")
print(f"Skrev {df.count()} rader till bronze_weather")
