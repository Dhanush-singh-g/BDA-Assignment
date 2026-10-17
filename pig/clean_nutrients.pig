-- Run in distributed MapReduce mode; never use -x local for final evidence.
raw = LOAD '$INPUT' USING PigStorage('\t') AS (
    fdc_id:long, data_type:chararray, food_category_id:chararray,
    nutrient_id:int, nutrient_name:chararray, unit:chararray, amount:double
);
clean = FILTER raw BY fdc_id IS NOT NULL AND nutrient_id IS NOT NULL
    AND data_type IS NOT NULL AND amount IS NOT NULL AND amount >= 0.0;
STORE clean INTO '$OUTPUT' USING PigStorage('\t');
