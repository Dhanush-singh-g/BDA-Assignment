# USDA FoodData Central — Track B

BCS714D Big Data Analytics · 2026–2027.

We calculate food/nutrient summaries using MongoDB, Hadoop MapReduce, Pig and
Hive, check that the answers agree, compare performance, and display saved
results in a Flask dashboard.

Dataset: [entire October 31, 2024 CSV package](https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_csv_2024-10-31.zip)
· [USDA documentation](https://fdc.nal.usda.gov/download-datasets/).

## Which document should I read?

| Document | When you need it |
| --- | --- |
| [50,000-food laptop run](run%2050%2C000.md) | Commands, explanations and the saved 50,000-food dashboard run. |
| [Laptop demo](docs/LAPTOP-DEMO.md) | Start the dashboard or repeat your small laptop test. |
| [Three-system walkthrough](docs/THREE-SYSTEM-RUN.md) | Set up and run the full dataset on three college computers, step by step. |
| [Architecture explained](docs/ARCHITECTURE.md) | Understand what the program and each tool do. |
| [Presentation Q&A](docs/PRESENTATION-QA.md) | Prepare answers for your presentation/viva. |
| [Report checklist](docs/report-outline.md) | Assemble the Part 1 and Part 2 submission evidence. |
| [Validation record](docs/validation.md) | See what actually passed and what is still pending. |
| [Technical reference](docs/TECHNICAL-REFERENCE.md) | Optional: fresh setup, subset export, troubleshooting and output-file details. |

## Current status

- **Full dataset:** prepared on the user's laptop and all 34 CSVs imported into
  MongoDB. Full-data MongoDB analytics was interrupted, not completed.
- **10,000-food linked subset:** MongoDB profiling and cross-system
  MapReduce/Pig/Hive checks passed on the user's laptop.
- **50,000-food linked subset:** MongoDB analytics and cross-system checks passed
  on the laptop, covering 1,126,928 linked nutrient records.
- **Part 2:** Flask dashboard implemented and opened successfully on the laptop.
- **Still pending:** full-data analytics/benchmarks, three physical college
  systems, final report and presentation evidence.

The dashboard separates **View results** from **Run analysis**. Choose a subset,
a custom size, or the entire dataset using the fixed source database. Optional
controls reuse exports and switch services; progress/errors update automatically. See the
[laptop guide](docs/LAPTOP-DEMO.md).

The production workflow has no sampling limit. Development-subset commands are
explicitly separate and labelled. Three laptop containers do not satisfy the
three-physical-system requirement.

## Get started on your existing laptop

From Ubuntu:

```bash
cd ~/BDA-Assignment
git pull --ff-only origin main
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m fdc.dashboard
```

Open the address Flask prints in your local browser. Saved results are needed;
GitHub does not contain your datasets, database files or benchmark outputs.
