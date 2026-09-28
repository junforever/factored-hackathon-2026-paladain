import os
from pathlib import Path

from dotenv import load_dotenv

import duckdb

load_dotenv()

Path("duckdb").mkdir(exist_ok=True)

con = duckdb.connect(f"duckdb/{os.getenv('DUCKDB_NAME')}")

con.execute("PRAGMA threads=4;")
con.execute("PRAGMA memory_limit='4GB';")

data_path = Path("data/transactions")

if not any(data_path.glob("**/*.csv")):
    raise FileNotFoundError("No se encontraron CSV en data/transactions")

pattern = (data_path / "**" / "*.csv").as_posix()

print("Leyendo transactions desde:", pattern)
print("Esto puede tardar porque tiene ~5M filas.")

con.execute("DROP VIEW IF EXISTS raw_transactions;")

con.execute(f"""
CREATE VIEW raw_transactions AS
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

print("\nVista raw_transactions creada.")

print("\nConteo general:")
print(
    con.sql("""
    SELECT
        COUNT(*) AS row_count,
        COUNT(DISTINCT transaction_id) AS distinct_transactions,
        COUNT(DISTINCT customer_id) AS distinct_customers
    FROM raw_transactions;
    """)
)

print("\nFraude por año:")
print(
    con.sql("""
    SELECT
        year,
        COUNT(*) AS transactions,
        SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END) AS fraud_transactions,
        ROUND(AVG(CASE WHEN is_fraud THEN 1.0 ELSE 0.0 END) * 100, 3) AS fraud_pct
    FROM raw_transactions
    GROUP BY year
    ORDER BY year;
    """)
)

con.close()
