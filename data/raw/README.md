# Data: Raw

This directory stores the raw procurement data used by the application.

## What belongs here

- `full.csv` — OCP Data Registry Publication 64 (Nigeria BPP) procurement data
- `full.csv.tar.gz` — Compressed original archive
- `full/` — Extracted OCDS-format CSV files

## How to obtain the data

Download from the OCP Data Registry:

```
https://data.open-contracting.org/en/publication/64/download?name=full.csv.tar.gz
```

Extract the archive into this directory.

## Can the application start without this data?

Yes. The application will start with an empty database. You can then import data
through the web interface (Import Dataset page) or via the management command:

```
python manage.py import_data data/raw/full.csv
```

## Notes

- The dataset contains 17,417 raw procurement records from Nigerian public institutions.
- After preprocessing, 16,637 valid contracts are retained.
- These files are not version-controlled due to size (~200 MB uncompressed).
