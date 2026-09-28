"""
Diagnóstico: ¿de quién es el producto afectado?
¿El mismatch customer_id es puntual o sistémico en el sandbox?
"""

import os
from pathlib import Path

from dotenv import load_dotenv

import duckdb

load_dotenv()

DB_PATH = Path(f"duckdb/{os.getenv('DUCKDB_NAME')}")
SANDBOX_PATH = Path(os.getenv("SANDBOX_PATH"))

TEST_PRODUCT = "PRD-8DIMA5HG33OA"
TEST_CUSTOMER_COMPLAINT = "CLI-9W3CREKG73Q7"
TEST_CUSTOMER_TX = "CLI-XKEMVQW8Y68S"

con = duckdb.connect(str(DB_PATH), read_only=True)

print("=" * 60)
print("1. ¿Quién es el dueño del producto en la tabla products?")
print("=" * 60)
print(
    con.execute(
        """
    SELECT product_id, customer_id AS owner_customer_id, product_type, product_status
    FROM raw_products
    WHERE product_id = ?
""",
        [TEST_PRODUCT],
    ).df()
)

print("\n" + "=" * 60)
print("2. ¿Es sistémico? Para TODO el sandbox, compara si la transacción")
print("   encontrada tiene el mismo customer_id que la queja.")
print("=" * 60)
print(
    con.execute(f"""
    WITH sandbox_with_tx AS (
        SELECT
            s.complaint_id,
            s.customer_id AS complaint_customer,
            s.product_id,
            s.transaction_id
        FROM read_parquet('{SANDBOX_PATH.as_posix()}') s
        WHERE s.transaction_id IS NOT NULL
    )
    SELECT
        CASE
            WHEN t.customer_id = swt.complaint_customer THEN 'MATCH'
            WHEN t.customer_id IS NULL THEN 'TX_CUSTOMER_NULL'
            ELSE 'MISMATCH'
        END AS integrity_status,
        COUNT(*) AS casos
    FROM sandbox_with_tx swt
    LEFT JOIN raw_transactions t
        ON swt.transaction_id = t.transaction_id
    GROUP BY 1
    ORDER BY casos DESC
""").df()
)

con.close()
