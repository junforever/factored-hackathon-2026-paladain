import os
from pathlib import Path

from dotenv import load_dotenv

import duckdb

load_dotenv()

file_path = Path("data/complaints/year=2025/month=12/day=02/complaints_20251202.csv")

print("Existe archivo:", file_path.exists())

if not file_path.exists():
    raise FileNotFoundError(f"No existe el archivo: {file_path}")

Path("duckdb").mkdir(exist_ok=True)

con = duckdb.connect(f"duckdb/{os.getenv('DUCKDB_NAME')}")

query = f"""
SELECT
    COUNT(*) AS row_count,
    COUNT(DISTINCT complaint_id) AS distinct_complaint_ids,
    MIN(creation_date) AS min_creation_date,
    MAX(creation_date) AS max_creation_date
FROM read_csv_auto('{file_path.as_posix()}')
"""

print(con.sql(query))

con.close()
