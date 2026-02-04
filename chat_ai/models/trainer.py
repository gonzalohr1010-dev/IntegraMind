"""
trainer.py - Auto-Training Pipeline for ERP Neural Models

Este módulo se encarga de:
1. Extraer datos de PostgreSQL (ej. historial de transacciones)
2. Preprocesar y Normalizar (MinMaxScaling)
3. Entrenar la red neuronal LSTM
4. Guardar el modelo y metadatos
"""
import torch
import torch.nn as nn
import pandas as pd
import numpy as np
import logging
import os
import pickle
from datetime import datetime, timedelta
from sklearn.preprocessing import MinMaxScaler
from torch.utils.data import DataLoader, TensorDataset

from chat_ai.db import get_db_manager
from chat_ai.models.forecaster import TimeSeriesLSTM

logger = logging.getLogger(__name__)

class ModelTrainer:
    def __init__(self, model_name: str = "finance_forecaster"):
        self.model_name = model_name
        self.db = get_db_manager()
        self.models_dir = os.path.join(os.path.dirname(__file__), "saved_models")
        os.makedirs(self.models_dir, exist_ok=True)
        
        self.model_path = os.path.join(self.models_dir, f"{model_name}.pth")
        self.scaler_path = os.path.join(self.models_dir, f"{model_name}_scaler.pkl")
        
        # Hyperparameters
        self.sequence_length = 30  # Usar 30 días pasados para predecir el siguiente
        self.hidden_size = 64
        self.num_layers = 2
        self.epochs = 50 # Entrenamiento rápido
        self.learning_rate = 0.001

    def fetch_data(self):
        """Extrae transacciones diarias de la DB"""
        query = """
            SELECT 
                DATE(transaction_date) as date,
                SUM(total_amount) as daily_total
            FROM fi_transactions
            WHERE status != 'cancelled'
            GROUP BY DATE(transaction_date)
            ORDER BY date ASC
        """
        results = self.db.execute_query(query)
        
        if not results:
            logger.warning("No data found for training.")
            return None
            
        df = pd.DataFrame(results)
        df['date'] = pd.to_datetime(df['date'])
        df['daily_total'] = df['daily_total'].astype(float)
        
        # Rellenar fechas faltantes con 0
        idx = pd.date_range(df['date'].min(), df['date'].max())
        df = df.set_index('date').reindex(idx, fill_value=0.0).reset_index()
        df.rename(columns={'index': 'date'}, inplace=True)
        
        return df

    def prepare_sequences(self, data: np.ndarray):
        """Crea ventanas deslizantes (X) y targets (y)"""
        X, y = [], []
        for i in range(len(data) - self.sequence_length):
            X.append(data[i:(i + self.sequence_length)])
            y.append(data[i + self.sequence_length])
        return np.array(X), np.array(y)

    def train(self):
        """Pipeline completo de entrenamiento"""
        logger.info(f"🚀 Starting Auto-Training for {self.model_name}...")
        
        # 1. Data Ingestion
        df = self.fetch_data()
        if df is None or len(df) < (self.sequence_length + 10):
            logger.warning("⚠️  Not enough data to train neural network yet.")
            return False

        # 2. Preprocessing
        scaler = MinMaxScaler(feature_range=(0, 1))
        data_normalized = scaler.fit_transform(df[['daily_total']].values)
        
        X, y = self.prepare_sequences(data_normalized)
        
        # Convert to Tensors
        X_train = torch.tensor(X, dtype=torch.float32)
        y_train = torch.tensor(y, dtype=torch.float32)
        
        dataset = TensorDataset(X_train, y_train)
        loader = DataLoader(dataset, batch_size=16, shuffle=True)
        
        # 3. Model Initialization
        model = TimeSeriesLSTM(
            input_size=1,
            hidden_size=self.hidden_size,
            num_layers=self.num_layers
        )
        
        criterion = nn.MSELoss()
        optimizer = torch.optim.Adam(model.parameters(), lr=self.learning_rate)
        
        # 4. Training Loop
        model.train()
        for epoch in range(self.epochs):
            epoch_loss = 0
            for batch_X, batch_y in loader:
                optimizer.zero_grad()
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()
            
            if (epoch+1) % 10 == 0:
                logger.info(f"Epoch [{epoch+1}/{self.epochs}], Loss: {epoch_loss:.6f}")

        # 5. Save Artifacts
        torch.save(model.state_dict(), self.model_path)
        with open(self.scaler_path, 'wb') as f:
            pickle.dump(scaler, f)
            
        logger.info(f"✅ Model saved to {self.model_path}")
        return True

    def predict_next_days(self, days: int = 7):
        """Usar el modelo entrenado para predecir el futuro"""
        if not os.path.exists(self.model_path):
            return None
            
        # Cargar modelo
        model = TimeSeriesLSTM(input_size=1, hidden_size=self.hidden_size, num_layers=self.num_layers)
        model.load_state_dict(torch.load(self.model_path))
        model.eval()
        
        with open(self.scaler_path, 'rb') as f:
            scaler = pickle.load(f)
            
        # Obtener datos recientes
        df = self.fetch_data()
        if df is None: return []
        
        recent_data = df['daily_total'].values[-self.sequence_length:]
        current_seq = scaler.transform(recent_data.reshape(-1, 1)) # (30, 1)
        
        predictions = []
        
        # Predecir iterativamente
        with torch.no_grad():
            for _ in range(days):
                # Preparar tensor (1, seq_len, 1)
                seq_tensor = torch.tensor(current_seq, dtype=torch.float32).unsqueeze(0)
                
                # Predecir
                next_val_norm = model(seq_tensor).item()
                
                # Guardar valor real (des-normalizado)
                next_val = scaler.inverse_transform([[next_val_norm]])[0][0]
                predictions.append(max(0, next_val)) # No ventas negativas
                
                # Actualizar secuencia (rolling window)
                next_val_norm_arr = np.array([[next_val_norm]])
                current_seq = np.append(current_seq[1:], next_val_norm_arr, axis=0)
                
        return predictions

if __name__ == "__main__":
    # Test manual
    logging.basicConfig(level=logging.INFO)
    trainer = ModelTrainer()
    trainer.train()
    
    # Generar algunos datos sintéticos para probar si no hay DB
    # (Solo si se ejecuta directamente y falla fetch_data)
    pass
