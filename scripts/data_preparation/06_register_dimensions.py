from pathlib import Path

import duckdb
from ai_banking_customer_service.config import settings

settings.duckdb_path.parent.mkdir(exist_ok=True)

con = duckdb.connect(str(settings.duckdb_path))

con.execute("PRAGMA threads=4;")
con.execute("PRAGMA memory_limit='4GB';")

dimensions = ["customers", "products"]

for table in dimensions:
    data_path = Path(f"data/{table}")

    pattern = (data_path / "**" / "*.csv").as_posix()
    if not any(data_path.glob("**/*.csv")):
        pattern = f"{data_path}.csv"
        if not Path(pattern).is_file():
            raise FileNotFoundError(
                f"No se encontraron archivos CSV para '{table}' en {data_path} ni {pattern}"
            )

    print(f"Leyendo {table} desde: {pattern}")

    con.execute(f"DROP VIEW IF EXISTS raw_{table};")

    con.execute(f"""
    CREATE VIEW raw_{table} AS
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

    row_count = con.execute(f"SELECT COUNT(*) FROM raw_{table};").fetchone()[0]
    print(f"[OK] Vista raw_{table} creada con {row_count:,} filas.\n")

con.close()
