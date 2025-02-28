import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job

glue_table_name = "sample_data_store"
glue_database = "glue_database"
redshift_connection = "redshift_connection"
redshift_db = "redshift_db"
redshift_table = "sales"

args = getResolvedOptions(sys.argv, ["JOB_NAME"])
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

# Read Parquet files from S3 using the Glue Database(Data Catalog)
datasource = glueContext.create_dynamic_frame.from_catalog(
    database=glue_database, table_name=glue_table_name)

# Write to Redshift
glueContext.write_dynamic_frame.from_jdbc_conf(
    frame=datasource,
    catalog_connection=redshift_connection,
    connection_options={
        "dbtable": redshift_table,
        "database": redshift_db
    },
    redshift_tmp_dir="s3://staging-data/temp/")

job.commit()
