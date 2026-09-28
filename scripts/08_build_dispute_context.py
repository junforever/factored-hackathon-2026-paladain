import os
from pathlib import Path

from dotenv import load_dotenv

import duckdb

load_dotenv()

Path("duckdb").mkdir(exist_ok=True)

con = duckdb.connect(f"duckdb/{os.getenv('DUCKDB_NAME')}")

con.execute("PRAGMA threads=4;")
con.execute("PRAGMA memory_limit='4GB';")

print("Construyendo tabla de contexto de disputas...")

# Creamos la tabla "golden dataset"
con.execute("DROP TABLE IF EXISTS sandbox_dispute_cases;")

query = """
CREATE TABLE sandbox_dispute_cases AS
SELECT
    co.complaint_id,
    co.customer_id,
    co.creation_date AS complaint_date,
    co.status AS complaint_status,
    co.sla_breached,
    co.resolution_days,
    co.description AS complaint_description,
    
    -- Contexto del Cliente
    c.country,
    c.segment,
    c.detected_accent,
    c.customer_status,
    
    -- Contexto del Producto (Tarjeta/Cuenta)
    p.product_id,
    p.product_type,
    p.product_number,
    p.product_status,
    
    -- Contexto de la Transacción Sospechosa (Buscamos la más cercana a la queja)
    t.transaction_id,
    t.transaction_date,
    t.amount,
    t.currency,
    t.merchant_name,
    t.transaction_status,
    t.is_fraud AS system_flagged_fraud,
    t.fraud_score
    
FROM raw_complaints co
JOIN raw_customers c ON co.customer_id = c.customer_id
JOIN raw_products p ON co.affected_product_id = p.product_id
LEFT JOIN raw_transactions t 
    ON co.affected_product_id = t.product_id
    AND t.transaction_date <= co.creation_date
    AND t.transaction_date >= co.creation_date - INTERVAL 30 DAY
WHERE co.category = 'Transactions'
  AND co.subcategory = 'Cargo no reconocido'
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY co.complaint_id 
    ORDER BY t.transaction_date DESC
) = 1;
"""

con.execute(query)

print("\nTabla sandbox_dispute_cases creada.")

print("\nResumen del Sandbox:")
print(
    con.sql("""
    SELECT
        COUNT(*) AS total_cases,
        COUNT(DISTINCT customer_id) AS unique_customers,
        COUNT(DISTINCT country) AS countries,
        ROUND(AVG(CASE WHEN system_flagged_fraud THEN 1.0 ELSE 0.0 END) * 100, 2) AS pct_flagged_as_fraud,
        ROUND(AVG(resolution_days), 1) AS avg_resolution_days
    FROM sandbox_dispute_cases;
    """)
)

print("\nMuestra de 3 casos:")
print(
    con.sql("""
    SELECT
        complaint_id,
        country,
        product_type,
        merchant_name,
        amount,
        currency,
        system_flagged_fraud,
        complaint_status
    FROM sandbox_dispute_cases
    LIMIT 3;
    """)
)

con.close()
