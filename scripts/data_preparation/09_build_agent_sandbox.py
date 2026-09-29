import duckdb
from ai_banking_customer_service.config import settings

settings.sandbox_full_path.parent.mkdir(parents=True, exist_ok=True)

con = duckdb.connect(str(settings.duckdb_path))

print("Aplicando reglas de negocio y exportando sandbox final...")

con.execute("DROP TABLE IF EXISTS agent_sandbox_final;")

query = """
CREATE TABLE agent_sandbox_final AS
SELECT
    *,
    -- Estimación de monto en USD para reglas de negocio
    -- En producción usaríamos la tabla daily_exchange_rates, aquí usamos tasas fijas para el sandbox
    CASE
        WHEN currency = 'USD' THEN amount
        WHEN currency = 'MXN' THEN amount / 17.0
        WHEN currency = 'COP' THEN amount / 4000.0
        WHEN currency = 'ARS' THEN amount / 900.0
        ELSE amount
    END AS amount_usd_estimated,
    
    -- REGLAS DE DECISIÓN DETERMINÍSTICAS (Fuera del prompt del LLM)
    CASE
        -- CASO 1: Tarjeta + Comercio conocido + Monto bajo -> Automatizar bloqueo y disputa
        WHEN product_type LIKE '%Tarjeta%' 
             AND merchant_name IS NOT NULL 
             AND (CASE WHEN currency='USD' THEN amount ELSE amount/1000 END) < 500
             AND complaint_status IN ('Open', 'In Process')
        THEN 'AUTO_BLOCK_AND_DISPUTE'
        
        -- CASO 2: Cuenta Corriente/Ahorro -> Siempre escalar (riesgo de congelamiento de fondos)
        WHEN product_type LIKE '%Cuenta%'
        THEN 'ESCALATE_TO_HUMAN'
        
        -- CASO 3: Monto alto (>= $500 USD aprox) -> Escalar a supervisor
        WHEN (CASE WHEN currency='USD' THEN amount ELSE amount/1000 END) >= 500
        THEN 'ESCALATE_TO_HUMAN'
        
        -- CASO 4: Falta información del comercio -> Pedir más detalles al cliente
        WHEN merchant_name IS NULL
        THEN 'ASK_FOR_DETAILS_THEN_DECIDE'
        
        -- DEFAULT: Escalar por seguridad
        ELSE 'ESCALATE_TO_HUMAN'
    END AS recommended_action
    
FROM sandbox_dispute_cases;
"""

con.execute(query)

# Exportar a Parquet para consumo rápido del agente
con.execute(f"""
COPY agent_sandbox_final 
TO '{settings.sandbox_full_path.as_posix()}' 
(FORMAT PARQUET, COMPRESSION ZSTD);
""")

print("\nSandbox final creado y exportado.")

print("\nDistribución de acciones recomendadas:")
print(
    con.sql("""
    SELECT
        recommended_action,
        COUNT(*) AS cases,
        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct
    FROM agent_sandbox_final
    GROUP BY recommended_action
    ORDER BY cases DESC;
    """)
)

con.close()
