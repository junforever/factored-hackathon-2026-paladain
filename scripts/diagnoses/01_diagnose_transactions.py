"""
Diagnóstico: entender por qué get_recent_transactions devolvió 0 filas.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

import duckdb

load_dotenv()

DB_PATH = Path(f"duckdb/{os.getenv('DUCKDB_NAME')}")

TEST_CUSTOMER = "CLI-9W3CREKG73Q7"
TEST_PRODUCT = "PRD-8DIMA5HG33OA"
TEST_TX = "TRX-QC7056S3IRCCE9A73PKI"

con = duckdb.connect(str(DB_PATH), read_only=True)

print("=" * 60)
print("1. ¿Existe la transacción del sandbox en raw_transactions?")
print("=" * 60)
print(
    con.execute(
        """
    SELECT transaction_id, customer_id, product_id, transaction_date, amount
    FROM raw_transactions
    WHERE transaction_id = ?
""",
        [TEST_TX],
    ).df()
)

print("\n" + "=" * 60)
print("2. Transacciones del cliente (sin filtro de fecha)")
print("=" * 60)
print(
    con.execute(
        """
    SELECT COUNT(*) AS total_tx_del_cliente,
           MIN(transaction_date) AS primera,
           MAX(transaction_date) AS ultima
    FROM raw_transactions
    WHERE customer_id = ?
""",
        [TEST_CUSTOMER],
    ).df()
)

print("\n" + "=" * 60)
print("3. Transacciones del producto (sin filtro de fecha)")
print("=" * 60)
print(
    con.execute(
        """
    SELECT COUNT(*) AS total_tx_del_producto,
           MIN(transaction_date) AS primera,
           MAX(transaction_date) AS ultima
    FROM raw_transactions
    WHERE product_id = ?
""",
        [TEST_PRODUCT],
    ).df()
)

print("\n" + "=" * 60)
print("4. Transacciones del cliente en la ventana 2023-05-29 a 2023-06-28")
print("=" * 60)
print(
    con.execute(
        """
    SELECT transaction_id, transaction_date, amount, currency, product_id
    FROM raw_transactions
    WHERE customer_id = ?
      AND transaction_date >= TIMESTAMP '2023-05-29 00:00:00'
      AND transaction_date <= TIMESTAMP '2023-06-28 23:59:59'
    ORDER BY transaction_date DESC
""",
        [TEST_CUSTOMER],
    ).df()
)

con.close()
