"""
finance.py - Módulo Financiero (FI/CO) ERP IA

Maneja:
- Plan de Cuentas (Accounts)
- Transacciones (Journal Entries)
- Validaciones de partida doble
- Presupuestos
"""
from __future__ import annotations

import logging
from typing import List, Dict, Optional, Any
from datetime import date, datetime, timedelta
from decimal import Decimal
from pydantic import BaseModel, Field

from .db import get_db_manager

logger = logging.getLogger(__name__)

# --- Modelos Pydantic para Validación ---

class AccountCreate(BaseModel):
    code: str
    name: str
    type: str  # asset, liability, equity, revenue, expense
    parent_id: Optional[int] = None
    currency: str = "USD"
    metadata: Dict[str, Any] = {}

class TransactionLineCreate(BaseModel):
    account_id: int
    debit: float = 0.0
    credit: float = 0.0
    notes: Optional[str] = None
    dimension_tags: Dict[str, Any] = {}

class TransactionCreate(BaseModel):
    date: date
    description: str
    lines: List[TransactionLineCreate]
    currency: str = "USD"
    metadata: Dict[str, Any] = {}


class FinanceManager:
    """Gestor de lógica financiera"""

    def __init__(self):
        self.db = get_db_manager()

    # --- Cuentas ---

    def create_account(self, account: AccountCreate) -> Dict[str, Any]:
        """Crear una nueva cuenta contable"""
        query = """
            INSERT INTO fi_accounts (code, name, type, parent_id, currency, metadata)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, code, name
        """
        params = (
            account.code, 
            account.name, 
            account.type, 
            account.parent_id, 
            account.currency, 
            account.metadata
        ) # Postgres adapta el dict a JSONB automáticamente con psycopg2.extras.Json si configurado, o str
        
        # Nota: DatabaseManager.execute_query usa dict cursor
        # Para RETURNING en INSERT con psycopg2 simple, execute_query maneja cursor.fetchall() si hay results
        try:
            # Pydantic dicts to json string for safety if needed, check db.py impl
            import json
            meta_json = json.dumps(account.metadata)
            
            # Using execute_query from db.py
            results = self.db.execute_query(query, (
                account.code, account.name, account.type, account.parent_id, account.currency, meta_json
            ))
            logger.info(f"✅ Cuenta creada: {account.code} - {account.name}")
            return results[0]
        except Exception as e:
            logger.error(f"❌ Error creando cuenta: {e}")
            raise

    def get_accounts(self) -> List[Dict[str, Any]]:
        """Listar todas las cuentas"""
        return self.db.execute_query("SELECT * FROM fi_accounts ORDER BY code")

    def get_account_balance(self, account_id: int) -> float:
        """Obtener saldo actual de una cuenta (calculado o cacheado)"""
        # Por ahora devolvemos el campo balance. En el futuro podríamos recalcular.
        res = self.db.execute_query("SELECT balance FROM fi_accounts WHERE id = %s", (account_id,))
        return float(res[0]['balance']) if res else 0.0

    # --- Transacciones ---

    def create_transaction(self, tx: TransactionCreate, created_by: str = "system") -> Dict[str, Any]:
        """
        Crear asientos contables (Transacción + Líneas)
        Realiza validación de partida doble (Debits == Credits).
        """
        # 1. Validar Partida Doble
        total_debit = sum(line.debit for line in tx.lines)
        total_credit = sum(line.credit for line in tx.lines)
        
        if abs(total_debit - total_credit) > 0.01: # Tolerancia por redondeo
            raise ValueError(f"Asiento desbalanceado: Debit {total_debit} != Credit {total_credit}")

        if total_debit == 0:
             raise ValueError("El asiento no puede ser cero.")

        import json
        
        # Generar número de transacción único con microsegundos y random
        import random
        tx_number = f"TX-{datetime.now().strftime('%Y%m%d%H%M%S%f')}-{random.randint(100,999)}"

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                try:
                    # 2. Insertar Header
                    cur.execute("""
                        INSERT INTO fi_transactions 
                        (transaction_number, transaction_date, description, total_amount, currency, status, created_by, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        tx_number,
                        tx.date,
                        tx.description,
                        total_debit, # El monto total de la operación es la suma de débitos
                        tx.currency,
                        'posted', # Directamente posted por ahora
                        created_by,
                        json.dumps(tx.metadata)
                    ))
                    
                    tx_id = cur.fetchone()[0] # En psycopg2 estándar devuelve tupla

                    # 3. Insertar Líneas
                    for line in tx.lines:
                        cur.execute("""
                            INSERT INTO fi_transaction_lines
                            (transaction_id, account_id, debit, credit, notes, dimension_tags)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (
                            tx_id,
                            line.account_id,
                            line.debit,
                            line.credit,
                            line.notes,
                            json.dumps(line.dimension_tags)
                        ))
                        
                        # 4. Actualizar Saldo de Cuenta (Simplificado)
                        # Dependiendo del tipo de cuenta, DEBE sumar o restar.
                        # Asset/Expense: +Debit -Credit
                        # Liability/Equity/Revenue: +Credit -Debit
                        # Para simplificar, obtenemos tipo de cuenta y actualizamos.
                        
                        # Primero averiguar tipo
                        cur.execute("SELECT type FROM fi_accounts WHERE id = %s", (line.account_id,))
                        acct_type = cur.fetchone()[0]
                        
                        balance_change = 0.0
                        if acct_type in ('asset', 'expense'):
                            balance_change = line.debit - line.credit
                        else:
                            balance_change = line.credit - line.debit
                            
                        cur.execute("""
                            UPDATE fi_accounts 
                            SET balance = balance + %s 
                            WHERE id = %s
                        """, (balance_change, line.account_id))

                    logger.info(f"✅ Transacción creada: {tx_number}")
                    return {"id": tx_id, "transaction_number": tx_number, "status": "posted"}

                except Exception as e:
                    logger.error(f"❌ Rollback transaction: {e}")
                    conn.rollback()
                    raise e
    
    def get_transactions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Listar últimas transacciones con sus líneas"""
        # Obtenemos headers
        txs = self.db.execute_query("""
            SELECT * FROM fi_transactions 
            ORDER BY transaction_date DESC, created_at DESC 
            LIMIT %s
        """, (limit,))
        
        # Para cada tx, obtener líneas (esto es N+1 query, optimizable después con un JOIN grande)
        for tx in txs:
            lines = self.db.execute_query("""
                SELECT l.*, a.code as account_code, a.name as account_name 
                FROM fi_transaction_lines l
                JOIN fi_accounts a ON l.account_id = a.id
                WHERE l.transaction_id = %s
            """, (tx['id'],))
            tx['lines'] = lines
            
        return txs

    def predict_cashflow(self, days: int = 7) -> Dict[str, Any]:
        """
        Usa la Red Neuronal para predecir el flujo de caja futuro.
        Si no hay modelo entrenado, dispara un entrenamiento en background.
        """
        try:
            from chat_ai.models.trainer import ModelTrainer
            trainer = ModelTrainer()
            
            # Intenta predecir
            predictions = trainer.predict_next_days(days)
            
            if not predictions:
                logger.info("Modelo no encontrado o sin datos, iniciando entrenamiento...")
                # En un entorno real, esto iría a una cola de tareas (Celery/Redis Queue)
                # Aquí lo hacemos sincrónico rápido o devolvemos aviso
                if trainer.train():
                     predictions = trainer.predict_next_days(days)
                else:
                    return {"status": "not_enough_data", "predictions": []}
            
            # Formatear fechas futuras
            result = []
            start_date = date.today()
            for i, val in enumerate(predictions):
                future_date = start_date + timedelta(days=i+1)
                result.append({
                    "date": future_date.isoformat(),
                    "predicted_revenue": round(val, 2)
                })
                
            return {"status": "success", "predictions": result}
            
        except Exception as e:
            logger.error(f"Error en predicción neuronal: {e}")
            return {"status": "error", "message": str(e)}

# Instancia global
finance_manager = FinanceManager()
