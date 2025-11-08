# Glue 4.0 / Spark 3.x
import sys
from awsglue.utils import getResolvedOptions
from pyspark.sql import functions as F
from pyspark.sql import Window
from pyspark.sql.types import *

from datetime import datetime

args = getResolvedOptions(
    sys.argv,
    ["JOB_NAME", "silver_path", "gold_path", "catalog_db", "gold_table"]
)

silver_path   = args["silver_path"].rstrip("/")
gold_path     = args["gold_path"].rstrip("/")
catalog_db    = args["catalog_db"]
gold_table    = args["gold_table"]
dt            = datetime.now().strftime("%Y-%m-%d") #args["dt"]  # YYYY-MM-DD

from pyspark.context import SparkContext
from awsglue.context import GlueContext
sc = SparkContext.getOrCreate()
glue = GlueContext(sc)
spark = glue.spark_session

# 1) DB en Glue Catalog
spark.sql(f"CREATE DATABASE IF NOT EXISTS {catalog_db}")

# 2) Leer todos los Parquet Silver del día (todas las entidades)
input_glob = f"{silver_path}/*/{dt}/fact_rates_staging.parquet"
df = spark.read.parquet(input_glob)

# Esperado en Silver:
# date (string/obj), entity__id (long), product__id (long), rate (double),
# ingestion_ts (string/obj), source_file (string)

# 3) Tipos + normalización de nombres
df = (
    df
    .withColumn("date", F.to_date("date"))  # a DATE
    .withColumn("ingestion_ts", F.to_timestamp("ingestion_ts"))
    .withColumnRenamed("entity__id", "entity_id")
    .withColumnRenamed("product__id", "product_id")
    .withColumn("entity_id", F.col("entity_id").cast(IntegerType()))
    .withColumn("product_id", F.col("product_id").cast(IntegerType()))
    .withColumn("rate", F.col("rate").cast(DoubleType()))
    .withColumn("source_file", F.col("source_file").cast(StringType()))
    .withColumn("dt", F.lit(dt))  # partición
)

# 4) Validaciones y rejects
valid = (
    F.col("date").isNotNull() &
    F.col("entity_id").isNotNull() &
    F.col("product_id").isNotNull() &
    F.col("rate").isNotNull() &
    (F.col("rate") > F.lit(0.0)) & (F.col("rate") < F.lit(200.0))
)

df_valid = df.where(valid)
df_rejects = (
    df
    .withColumn(
        "reject_reason",
        F.when(F.col("date").isNull(), "NULL_date")
         .when(F.col("entity_id").isNull(), "NULL_entity_id")
         .when(F.col("product_id").isNull(), "NULL_product_id")
         .when(F.col("rate").isNull(), "NULL_rate")
         .when(~((F.col("rate") > 0.0) & (F.col("rate") < 200.0)), "rate_out_of_range")
         .otherwise("unknown")
    )
    .where(~valid)
)

# 5) Dedup por clave de negocio (date, entity_id, product_id) – conserva el más reciente por ingestion_ts
w = Window.partitionBy("date", "entity_id", "product_id").orderBy(F.col("ingestion_ts").desc_nulls_last())
df_dedup = (
    df_valid
    .withColumn("rn", F.row_number().over(w))
    .where(F.col("rn") == 1)
    .drop("rn")
)

# Hash de negocio (auditoría)
df_dedup = df_dedup.withColumn(
    "business_hash",
    F.sha2(F.concat_ws("||",
                       F.col("date").cast("string"),
                       F.col("entity_id").cast("string"),
                       F.col("product_id").cast("string"),
                       F.coalesce(F.col("rate").cast("string"), F.lit(""))
    ), 256)
)

# 6) Crear tabla Gold si no existe (Parquet particionado por dt)
gold_location = f"{gold_path}/fact_rates"
spark.sql(f"""
CREATE EXTERNAL TABLE IF NOT EXISTS {catalog_db}.{gold_table} (
  `date`          DATE,
  `entity_id`     INT,
  `product_id`    INT,
  `rate`          DOUBLE,
  `ingestion_ts`  TIMESTAMP,
  `source_file`   STRING,
  `business_hash` STRING
)
PARTITIONED BY (`dt` STRING)
STORED AS PARQUET
LOCATION '{gold_location}'
""")

# 7) Escribir Gold (append particionado)
(df_dedup
 .select("date","entity_id","product_id","rate","ingestion_ts","source_file","business_hash","dt")
 .write
 .mode("append")
 .partitionBy("dt")
 .parquet(gold_location)
)

# 8) Registrar particiones en Glue Catalog
spark.sql(f"MSCK REPAIR TABLE {catalog_db}.{gold_table}")