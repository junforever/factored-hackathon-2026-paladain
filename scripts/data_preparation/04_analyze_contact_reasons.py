import os

from dotenv import load_dotenv

import duckdb

load_dotenv()

con = duckdb.connect(f"duckdb/{os.getenv('DUCKDB_NAME')}", read_only=True)

query = """
SELECT
    reason_category,
    contact_reason,
    COUNT(*) AS volume,
    ROUND(AVG(CASE WHEN was_resolved THEN 1 ELSE 0 END) * 100, 2) AS fcr_pct,
    ROUND(AVG(duration_seconds), 0) AS avg_duration_sec,
    ROUND(SUM(duration_seconds) / 3600.0, 2) AS total_agent_hours
FROM raw_call_center_interactions
WHERE reason_category IN ('Transaccional', 'Queja')
  AND contact_reason IS NOT NULL
GROUP BY reason_category, contact_reason
ORDER BY total_agent_hours DESC
LIMIT 15;
"""

print("Top 15 motivos específicos por impacto (Horas de Agente):")
print(con.sql(query))

con.close()
