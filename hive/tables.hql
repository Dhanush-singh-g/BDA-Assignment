CREATE DATABASE IF NOT EXISTS ${hivevar:DATABASE};
USE ${hivevar:DATABASE};
-- Dedicated external locations; pointing INPUT at Pig output retains raw HDFS input.
CREATE EXTERNAL TABLE nutrients_text (
    fdc_id BIGINT, data_type STRING, food_category_id STRING,
    nutrient_id INT, nutrient_name STRING, unit STRING, amount DOUBLE
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY '\t'
NULL DEFINED AS ''
STORED AS TEXTFILE
LOCATION '${hivevar:INPUT}';

CREATE EXTERNAL TABLE nutrients_rcfile (
    fdc_id BIGINT, data_type STRING, food_category_id STRING,
    nutrient_id INT, nutrient_name STRING, unit STRING, amount DOUBLE
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.columnar.ColumnarSerDe'
WITH SERDEPROPERTIES ('serialization.null.format'='')
STORED AS RCFILE
LOCATION '${hivevar:RC_OUTPUT}';

SET hive.exec.compress.output=true;
SET mapred.output.compression.codec=org.apache.hadoop.io.compress.GzipCodec;
SET mapreduce.output.fileoutputformat.compress.codec=org.apache.hadoop.io.compress.GzipCodec;
INSERT OVERWRITE TABLE nutrients_rcfile SELECT * FROM nutrients_text;
ANALYZE TABLE nutrients_text COMPUTE STATISTICS;
ANALYZE TABLE nutrients_rcfile COMPUTE STATISTICS;
