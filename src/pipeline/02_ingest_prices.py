# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze: elpriser från landing-volumen (push)
# MAGIC Elpris-API:t är blockerat från Databricks Free Edition. Ett schemalagt GitHub Actions-jobb hämtar priserna
# MAGIC och laddar upp JSON-filer till volumen. `COPY INTO` läser bara in filer som inte redan lästs (idempotent).

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
catalog = dbutils.widgets.get("catalog")
pipeline = f"{catalog}.elvader_pipeline"
landing = f"/Volumes/{catalog}/elvader_pipeline/landing/elpris"

dbutils.fs.mkdirs(landing)

# COMMAND ----------

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {pipeline}.bronze_prices (
  zone STRING, SEK_per_kWh DOUBLE, EUR_per_kWh DOUBLE, EXR DOUBLE,
  time_start STRING, time_end STRING, fetched_at STRING,
  _source_file STRING, _ingested_at TIMESTAMP
)
""")

result = spark.sql(f"""
COPY INTO {pipeline}.bronze_prices
FROM (
  SELECT zone, SEK_per_kWh, EUR_per_kWh, EXR, time_start, time_end, fetched_at,
         _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
  FROM '{landing}'
)
FILEFORMAT = JSON
""")
display(result)
print("Totalt i bronze_prices:", spark.table(f"{pipeline}.bronze_prices").count())
