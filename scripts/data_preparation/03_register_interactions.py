import os
from pathlib import Path

from dotenv import load_dotenv

import duckdb

load_dotenv()

Path("duckdb").mkdir(exist_ok=True)

con = duckdb.connect(f"duckdb/{os.getenv('DUCKDB_NAME')}")

con.execute("PRAGMA threads=4;")
con.execute("PRAGMA memory_limit='4GB';")

data_path = Path("data/call_center_interactions")

if not any(data_path.glob("**/*.csv")):
    raise FileNotFoundError("No se encontraron CSV en data/call_center_interactions")

pattern = (data_path / "**" / "*.csv").as_posix()

print("Leyendo archivos desde:", pattern)

con.execute("DROP VIEW IF EXISTS raw_call_center_interactions;")

con.execute(f"""
CREATE VIEW raw_call_center_interactions AS
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

print("\nVista raw_call_center_interactions creada.")

print("\nConteo general:")
print(
    con.sql("""
    SELECT
        COUNT(*) AS row_count,
        COUNT(DISTINCT interaction_id) AS distinct_interactions
    FROM raw_call_center_interactions;
    """)
)

print("\nTop 10 categorías de contacto (reason_category):")
print(
    con.sql("""
    SELECT
        reason_category,
        COUNT(*) AS volume,
        ROUND(AVG(CASE WHEN was_resolved THEN 1 ELSE 0 END) * 100, 2) AS fcr_pct,
        ROUND(AVG(CASE WHEN was_escalated THEN 1 ELSE 0 END) * 100, 2) AS escalation_pct
    FROM raw_call_center_interactions
    GROUP BY reason_category
    ORDER BY volume DESC
    LIMIT 10;
    """)
)

con.close()
