# Presentation questions and answers

Use these as speaking notes, not a script to memorize. Our development subset
passed; do not claim the full-data college run is finished until it actually is.

## 1. What is your project about?

We analyze USDA food/nutrient data using MongoDB, Hadoop MapReduce, Pig and Hive.
We check that their answers agree, measure query/storage performance, and show
saved results in a Flask dashboard.

## 2. Which dataset did you use?

USDA FoodData Central's October 31, 2024 CSV package. Full preparation found
2,063,876 foods and 26,848,323 nutrient observations.

## 3. Have you processed the whole dataset?

We prepared the full ZIP and imported all 34 CSV tables into MongoDB. Analytics
across all themes passed on the linked 10,000-food development subset. Full-data
analytics on three college machines is still pending. Update this answer with
actual run evidence after that succeeds.

## 4. Does 10,000 mean 10,000 total rows?

No: 10,000 foods plus their associated nutrient observations. One food can have
many nutrient records. The selection is for development, not representative
sampling; most selected foods are branded foods.

## 5. How do you connect the CSV tables?

Food IDs link nutrient measurements to food records. Nutrient IDs link those
measurements to nutrient names and units.

## 6. What is nutrient ID 1003?

Protein. We obtain that meaning from USDA's nutrient definitions, not from the
number itself. For example, 1004 is total fat and 1008 is energy.

## 7. What are mean and total amount?

For a food-type/nutrient group, total is the sum of recorded amounts; mean is
total divided by observations. Example: 2, 4 and 9 g give total 15 g and mean 5 g.
These are grouped observations, not the nutrition of a particular product or
someone's food intake. Do not mix different nutrient IDs or units.

## 8. Does the dashboard show the protein in chicken?

Not in the current grouped view. It summarizes food types and nutrients. Food
names exist in storage, but individual-food search/details are not implemented.

## 9. Why MongoDB?

It stores imported records as documents and supports aggregation pipelines. We
also build food documents containing linked nutrient observations.

## 10. Which aggregation operators did you use?

`$match` filters, `$unwind` expands nutrient arrays, `$group` calculates summaries,
`$project` selects/calculates fields, and `$facet` produces several summaries.
`$lookup` connects foods with their nutrient records.

## 11. How did you test indexes?

We ran the same food-ID query as a forced collection scan and an index scan with
`executionStats`. On the 10,000-food subset, the scan examined 10,000 documents;
the indexed query examined one document and one key. Both returned the same row.

## 12. Why can a query show 0 ms?

The timer reports whole milliseconds. Zero means below that resolution, not no
work. We also save repeated measurements and documents/keys examined.

## 13. Where does MongoDB run? Did you use Atlas?

It runs locally in the `fdc-mongo-dev` Docker container, using MongoDB 7.0.16.
The default address is `mongodb://127.0.0.1:27017`. We have not used Atlas or set
up sharding. Persistent files are in `data/mongo/`.

## 14. Why SQLite too?

It is a local preparation helper: `join.sqlite` holds lookup tables on disk so
Python need not load all data into RAM. It is a file, with no separate database
server or login. It does not replace MongoDB/Hive.

## 15. What do HDFS and YARN do?

HDFS stores files on workers and keeps replicas. YARN allocates processing
resources and schedules jobs. Our HDFS configuration uses replication two.

## 16. What does MapReduce calculate?

The mapper emits nutrient amounts keyed by food type/nutrient ID. Reducers
combine each group into observation counts, totals and means.

## 17. What does Pig do?

It loads the prepared data and filters unusable analytical records, including
negative nutrient amounts. It executes through MapReduce, not local mode.

## 18. Why compare Hive Text and RCFile?

They hold the same cleaned records in different layouts. We check identical
query answers, then compare elapsed times and storage. RCFile is a legacy
column-oriented format used because this assignment requires it. It is not
guaranteed to be faster or smaller for every workload.

## 19. How do you know the answers are right?

We independently calculate expected summaries from prepared records, then compare
counts, sums and means with MongoDB, MapReduce and Hive. Counts match exactly;
floating-point comparisons use a small tolerance. Rejected/filtered rows are
accounted for rather than silently disappearing.

## 20. Why warmups and repeated runs?

Startup and caching affect timings. We exclude Hive warmups and summarize measured
repetitions. The development cluster test uses one measured run per query/table
pair; the final workflow uses five. Timings include client/job startup, so we do
not claim pure engine time or cold-cache measurements.

## 21. Are three containers three physical systems?

No. They are separate software environments sharing one laptop's resources. They
are for development; final assignment evidence requires three college machines.

## 22. What do master and workers do?

Master runs NameNode (file metadata), ResourceManager (job resources), JobHistory
and analytics services. Workers run DataNodes (file blocks) and NodeManagers
(task execution). The master does not manually assign different scripts to friends;
YARN schedules tasks within the connected cluster.

## 23. What does Flask do?

It displays recorded nutrient summaries, MongoDB index comparisons, Hive timings,
storage and source fingerprints. It does not launch jobs or query MongoDB live.
The database and cluster can be stopped while showing the dashboard.

## 24. What is SHA-256 used for?

It is a fingerprint of the exact ZIP we processed. It helps check copied data and
connect results to an input file. Our local fingerprint is not a publisher's
digital signature or independent proof that the file came from USDA.

## 25. What are the limitations?

The subset is not representative; full-data analytics/physical-cluster evidence
remain pending. Dashboard results are grouped observations, not food-specific
advice. Performance depends on hardware, cache, job startup and cluster settings.

## 26. Is Hadoop necessary for a ZIP this size?

Not necessarily. We use it to meet the assignment and demonstrate distributed
storage, execution and benchmarking. We do not claim it is automatically faster;
startup overhead can dominate small workloads.

## 27. Why did you stop the full laptop analytics run?

The laptop had limited WSL memory and the large linked-document aggregation took
a long time. We preserved the full import, tested correctness using a smaller
linked subset, and reserved final full-data execution for the college cluster.

## 28. What did you learn?

How to connect related data, execute analyses using different systems, check
matching answers, measure performance carefully, and distinguish development
success from final full-scale verification.

## Quick opening for the presentation

“Our project uses USDA food data to demonstrate the three required big-data
themes. We calculate nutrient summaries, check agreement across MongoDB,
MapReduce and Hive, compare indexing and storage performance, and display saved
results in a Flask dashboard. We clearly label development and full-data runs.”

## What should we have ready to show?

The selected run ID and source hash, worker/task evidence, MongoDB plans,
MapReduce/Pig results, Hive Text/RCFile comparisons, dashboard and report. Answer
using the selected run's actual numbers; do not invent speedups or completion.
