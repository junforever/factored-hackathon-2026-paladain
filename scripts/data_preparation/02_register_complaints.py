from pathlib import Path

import duckdb
from ai_banking_customer_service.config import settings

settings.duckdb_path.parent.mkdir(exist_ok=True)

con = duckdb.connect(str(settings.duckdb_path))

con.execute("PRAGMA threads=4;")
con.execute("PRAGMA memory_limit='4GB';")

data_path = Path("data/complaints")

if not any(data_path.glob("**/*.csv")):
    raise FileNotFoundError("No se encontraron CSV en data/complaints")

pattern = (data_path / "**" / "*.csv").as_posix()

print("Leyendo archivos desde:", pattern)

con.execute("DROP VIEW IF EXISTS raw_complaints;")

con.execute(f"""
CREATE VIEW raw_complaints AS
SELECT *
FROM read_csv(
    '{pattern}',
    auto_detect=true,
    union_by_name=true,
    filename=true,
    hive_partitioning=true,
    ignore_errors=true
);
""")

print("\nVista raw_complaints creada.")

print("\nConteo general:")
print(
    con.sql("""
    SELECT
        COUNT(*) AS row_count,
        COUNT(DISTINCT complaint_id) AS distinct_complaint_ids
    FROM raw_complaints;
    """)
)

print("\nConteo por año:")
print(
    con.sql("""
    SELECT
        year,
        COUNT(*) AS complaint_count
    FROM raw_complaints
    GROUP BY year
    ORDER BY year;
    """)
)

con.close()
