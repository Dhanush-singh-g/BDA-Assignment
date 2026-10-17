SET hive.execution.engine=mr;
SET hive.exec.mode.local.auto=false;
USE ${hivevar:DATABASE};
SELECT data_type, nutrient_id, unit, COUNT(*) AS records,
       SUM(amount) AS total_amount, AVG(amount) AS mean_amount
FROM ${hivevar:TABLE}
WHERE amount >= 0
GROUP BY data_type, nutrient_id, unit
ORDER BY data_type, nutrient_id, unit;
