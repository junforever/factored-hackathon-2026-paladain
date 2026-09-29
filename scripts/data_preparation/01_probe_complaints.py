from pathlib import Path

import duckdb
from ai_banking_customer_service.config import settings

file_path = Path("data/complaints/year=2025/month=12/day=02/complaints_20251202.csv")

print("Existe archivo:", file_path.exists())

if not file_path.exists():
    raise FileNotFoundError(f"No existe el archivo: {file_path}")

settings.duckdb_path.parent.mkdir(exist_ok=True)

con = duckdb.connect(str(settings.duckdb_path))

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
