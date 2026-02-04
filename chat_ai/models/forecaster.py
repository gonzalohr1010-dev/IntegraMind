"""
forecaster.py - Universal Time Series Forecaster (LSTM)

Red neuronal LSTM genérica en PyTorch para predecir series temporales
(Ventas, Inventario, Cashflow, Usuarios, etc.)
"""
import torch
import torch.nn as nn
import numpy as np
from typing import Tuple

class TimeSeriesLSTM(nn.Module):
    """
    Long Short-Term Memory Network para Forecasting
    """
    def __init__(self, input_size: int = 1, hidden_size: int = 50, num_layers: int = 2, output_size: int = 1):
        super(TimeSeriesLSTM, self).__init__()
        
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        
        # LSTM Layer: Captura patrones temporales complejos
        self.lstm = nn.LSTM(
            input_size, 
            hidden_size, 
            num_layers, 
            batch_first=True,
            dropout=0.2
        )
        
        # Fully Connected Layer: Proyecta la salida al valor real
        self.fc = nn.Linear(hidden_size, output_size)
    
    def forward(self, x):
        """
        x shape: (batch_size, sequence_length, input_size)
        """
        # Inicializar hidden state y cell state
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        
        # Forward propagate LSTM
        out, _ = self.lstm(x, (h0, c0))
        
        # Tomar solo el output del último paso de tiempo
        out = out[:, -1, :]
        
        # Pasar por capa lineal
        out = self.fc(out)
        return out

    def predict(self, sequence: np.ndarray, scaler=None) -> float:
        """Helper para predecir un solo valor dado un historial"""
        self.eval()
        with torch.no_grad():
            # Convertir a tensor
            tensor_x = torch.tensor(sequence, dtype=torch.float32).unsqueeze(0).unsqueeze(2) 
            # shape: (1, seq_len, 1)
            
            prediction = self.forward(tensor_x).item()
            
            # Des-normalizar si hay scaler
            if scaler:
                prediction = scaler.inverse_transform([[prediction]])[0][0]
                
            return prediction

    def save(self, path: str):
        torch.save(self.state_dict(), path)
        
    def load(self, path: str):
        self.load_state_dict(torch.load(path))
        self.eval()
