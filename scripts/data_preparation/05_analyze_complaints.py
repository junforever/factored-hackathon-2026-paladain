import os

from dotenv import load_dotenv

import duckdb

load_dotenv()

con = duckdb.connect(f"duckdb/{os.getenv('DUCKDB_NAME')}", read_only=True)

query = """
SELECT
    category,
    COALESCE(subcategory, '(sin subcategoría)') AS subcategory,
    COUNT(*) AS volume,
    ROUND(AVG(CASE WHEN sla_breached THEN 1.0 ELSE 0.0 END) * 100, 2) AS sla_breach_pct,
    ROUND(AVG(resolution_days), 1) AS avg_resolution_days,
    ROUND(AVG(CASE WHEN priority IN ('High', 'Critical') THEN 1.0 ELSE 0.0 END) * 100, 2) AS high_critical_pct,
    ROUND(AVG(CASE WHEN status IN ('Open', 'In Process', 'Escalated') THEN 1.0 ELSE 0.0 END) * 100, 2) AS open_or_escalated_pct
FROM raw_complaints
GROUP BY category, subcategory
ORDER BY volume DESC
LIMIT 25;
"""

print("Top 25 quejas por categoría/subcategoría:")
print(con.sql(query))
con.close()
