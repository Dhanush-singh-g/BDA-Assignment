SET hive.execution.engine=mr;
SET hive.exec.mode.local.auto=false;
USE ${hivevar:DATABASE};
-- USDA nutrient 1003 is protein, in grams. Keep unit explicit.
SELECT data_type, nutrient_id, unit, COUNT(*) AS records,
       SUM(amount) AS total_amount, AVG(amount) AS mean_amount
FROM ${hivevar:TABLE}
WHERE nutrient_id = 1003 AND LOWER(unit) = 'g' AND amount >= 0
GROUP BY data_type, nutrient_id, unit
ORDER BY data_type, nutrient_id, unit;
