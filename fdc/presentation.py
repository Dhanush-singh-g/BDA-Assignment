"""Read-only presentation commands and bounded, provenance-checked file samples."""
import itertools
import json
import re
import shlex
from pathlib import Path


def commands(database, hdfs, hive_database, native=False, pipeline_definitions=None):
    def shell(args):return shlex.join([str(a) for a in args])
    prefix=[] if native else ['docker','compose','-f','infra/compose.yaml','exec','-T','master']
    def hadoop(args):return shell(prefix+args)
    def mongo(js):
        if not database:return None
        return shell(['docker','exec','fdc-mongo-dev','mongosh','--quiet','--eval',
                      'const d=db.getSiblingDB('+json.dumps(database)+'); '+js])
    result={
        'raw':mongo('printjson(d.raw_food.find().sort({_id:1}).limit(3).toArray())'),
        'linked':mongo('printjson(d.foods.find({}, {nutrients:{$slice:5}}).sort({_id:1}).limit(3).toArray())'),
        'observations':mongo('const f=d.raw_food.find().sort({_id:1}).limit(1).toArray()[0]; if(f) printjson(d.raw_food_nutrient.find({fdc_id:f.fdc_id}).limit(5).toArray())'),
        'aggregate':mongo('printjson(d.foods.aggregate([{$match:{data_type:{$ne:""}}},{$group:{_id:"$data_type",foods:{$sum:1}}},{$project:{_id:0,data_type:"$_id",foods:1}},{$sort:{foods:-1,data_type:1}}]).toArray())'),
        'indexes':mongo('printjson(d.raw_food.getIndexes())'),
        'explain':mongo('const f=d.raw_food.findOne(); if(f) printjson(d.runCommand({explain:{find:"raw_food",filter:{fdc_id:f.fdc_id},hint:"idx_fdc_id"},verbosity:"executionStats"}))'),
        'hdfs_list':hadoop(['hdfs','dfs','-ls','-R',hdfs]) if hdfs else None,
        'hdfs_input':hadoop(['hdfs','dfs','-cat',hdfs+'/prepared/food_nutrients.tsv'])+" | sed -n '1,5p'" if hdfs else None,
        'mapreduce':hadoop(['hdfs','dfs','-cat',hdfs+'/mapreduce/part-*'])+" | sed -n '1,10p'" if hdfs else None,
        'workers':hadoop(['yarn','node','-list','-states','RUNNING']),
        'pig':hadoop(['hdfs','dfs','-cat',hdfs+'/pig_clean/part-*'])+" | sed -n '1,5p'" if hdfs else None,
        'hive_text':None,'hive_rcfile':None,'hive_compare':None,'storage':None}
    def writes_data(value):
        if isinstance(value,dict):return any(key in {'$out','$merge'} or writes_data(item) for key,item in value.items())
        if isinstance(value,list):return any(writes_data(item) for item in value)
        return False
    if pipeline_definitions:
        for name in ('foods_by_type','nutrient_summary','overview'):
            if name in pipeline_definitions and not writes_data(pipeline_definitions[name]):
                result[name]=mongo('printjson(d.foods.aggregate('+json.dumps(pipeline_definitions[name])+').toArray().slice(0,5))')
        result['aggregate']=result.get('foods_by_type',result['aggregate'])
    else:
        result.update(nutrient_summary=None,overview=None)
    if hive_database and re.fullmatch(r'fdc_[A-Za-z0-9_]+',hive_database):
        def hive(sql):
            return hadoop(['beeline','-u','jdbc:hive2://localhost:10000/default','-n','hadoop' if native else 'root','-e',sql])
        for key,table in [('hive_text','nutrients_text'),('hive_rcfile','nutrients_rcfile')]:
            result[key]=hive('USE `'+hive_database+'`; SELECT * FROM '+table+' ORDER BY fdc_id, nutrient_id, amount LIMIT 5;')
        result['hive_compare']=hive('USE `'+hive_database+'`; '+ ' '.join('SELECT data_type, nutrient_id, unit, COUNT(*), SUM(amount), AVG(amount) FROM '+table+' WHERE nutrient_id=1003 AND LOWER(unit)=\'g\' AND amount>=0 GROUP BY data_type,nutrient_id,unit ORDER BY data_type,nutrient_id,unit;' for table in ['nutrients_text','nutrients_rcfile']))
    if hdfs:result['storage']=hadoop(['hdfs','dfs','-du','-s',hdfs+'/pig_clean',hdfs+'/hive_rc'])
    return result


def input_sample(folder, root, context, success, source_hash):
    path=folder/'prepared'
    if context.get('prepared_directory'):
        path=Path(context['prepared_directory'])
        if not path.is_absolute():path=folder/path
    path=path.resolve()
    if not path.is_relative_to(Path(root).resolve()):return []
    manifest=path/'manifest.json'
    if not manifest.is_file() or not (path/'food_nutrients.tsv').is_file():return []
    meta=json.loads(manifest.read_text())
    identities={v for v in [source_hash,success.get('subset_sha256')] if v and v!='Unavailable'}
    if meta.get('source_sha256') not in identities:return []
    result=[]
    with (path/'food_nutrients.tsv').open() as stream:
        for line in itertools.islice(stream,5):
            fields=line.rstrip('\n').split('\t')
            if len(fields)!=7:raise ValueError('Invalid prepared sample row')
            result.append(dict(zip(['fdc_id','data_type','category','nutrient_id','nutrient_name','unit','amount'],fields)))
    return result
