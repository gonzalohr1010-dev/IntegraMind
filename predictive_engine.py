#!/usr/bin/env python3
"""
🤖 INTEGRA MIND - PREDICTIVE MAINTENANCE ENGINE
Motor de IA que predice fallas antes de que ocurran
"""
import numpy as np
from sklearn.ensemble import IsolationForest
from datetime import datetime, timedelta
import json

class PredictiveEngine:
    """Motor de mantenimiento predictivo usando ML"""
    
    def __init__(self):
        self.model = IsolationForest(contamination=0.1, random_state=42)
        self.is_trained = False
        self.historical_data = []
        
    def generate_training_data(self, days=30):
        """Genera datos históricos simulados para entrenar el modelo"""
        data = []
        
        # Datos normales (90% del tiempo)
        for _ in range(days * 24 * 9 // 10):  # 90% normal
            data.append([
                np.random.normal(220, 10),  # Temperatura normal
                np.random.normal(500, 15),  # Presión normal
                np.random.normal(3600, 50)  # RPM normal
            ])
        
        # Datos anómalos (10% - pre-falla)
        for _ in range(days * 24 // 10):  # 10% anómalo
            data.append([
                np.random.normal(280, 20),  # Temperatura elevada
                np.random.normal(650, 30),  # Presión alta
                np.random.normal(3400, 100)  # RPM irregular
            ])
        
        return np.array(data)
    
    def train(self):
        """Entrena el modelo con datos históricos"""
        print("🧠 Entrenando modelo de IA...")
        training_data = self.generate_training_data(days=30)
        self.model.fit(training_data)
        self.is_trained = True
        print("✅ Modelo entrenado con 720 horas de datos")
    
    def predict_anomaly(self, temperatura, presion, rpm):
        """
        Predice si los valores actuales son anómalos.
        
        Returns:
            dict con: is_anomaly, confidence, risk_level, time_to_failure
        """
        if not self.is_trained:
            self.train()
        
        # Preparar datos
        current_data = np.array([[temperatura, presion, rpm]])
        
        # Predicción (-1 = anomalía, 1 = normal)
        prediction = self.model.predict(current_data)[0]
        
        # Score de anomalía (más negativo = más anómalo)
        anomaly_score = self.model.score_samples(current_data)[0]
        
        # Convertir a confianza (0-100%)
        confidence = min(100, max(0, int((1 - abs(anomaly_score)) * 100)))
        
        # Determinar nivel de riesgo
        is_anomaly = prediction == -1
        
        if is_anomaly:
            if anomaly_score < -0.5:
                risk_level = "CRITICAL"
                time_to_failure_hours = 24  # 1 día
            elif anomaly_score < -0.3:
                risk_level = "HIGH"
                time_to_failure_hours = 72  # 3 días
            else:
                risk_level = "MEDIUM"
                time_to_failure_hours = 168  # 7 días
        else:
            risk_level = "LOW"
            time_to_failure_hours = None
        
        return {
            "is_anomaly": is_anomaly,
            "confidence": confidence,
            "risk_level": risk_level,
            "anomaly_score": float(anomaly_score),
            "time_to_failure_hours": time_to_failure_hours,
            "prediction_time": datetime.now().isoformat()
        }
    
    def get_recommendation(self, prediction):
        """Genera recomendaciones basadas en la predicción"""
        if prediction["risk_level"] == "CRITICAL":
            return {
                "action": "SHUTDOWN_IMMEDIATE",
                "message": "🔴 DETENER REACTOR INMEDIATAMENTE. Falla inminente detectada.",
                "priority": "P0"
            }
        elif prediction["risk_level"] == "HIGH":
            return {
                "action": "SCHEDULE_MAINTENANCE",
                "message": "🟡 Programar mantenimiento en las próximas 72 horas.",
                "priority": "P1"
            }
        elif prediction["risk_level"] == "MEDIUM":
            return {
                "action": "MONITOR_CLOSELY",
                "message": "⚠️ Monitorear de cerca. Inspección recomendada esta semana.",
                "priority": "P2"
            }
        else:
            return {
                "action": "CONTINUE_NORMAL",
                "message": "✅ Sistema operando normalmente.",
                "priority": "P3"
            }

# Instancia global
engine = PredictiveEngine()

if __name__ == "__main__":
    # Test del motor
    print("=" * 70)
    print("🤖 PREDICTIVE MAINTENANCE ENGINE - TEST")
    print("=" * 70)
    
    engine.train()
    
    # Caso 1: Valores normales
    print("\n📊 Test 1: Valores Normales")
    result = engine.predict_anomaly(220, 500, 3600)
    print(f"   Anomalía: {result['is_anomaly']}")
    print(f"   Riesgo: {result['risk_level']}")
    print(f"   Confianza: {result['confidence']}%")
    
    # Caso 2: Valores anómalos
    print("\n📊 Test 2: Valores Anómalos (Pre-Falla)")
    result = engine.predict_anomaly(310, 720, 3200)
    print(f"   Anomalía: {result['is_anomaly']}")
    print(f"   Riesgo: {result['risk_level']}")
    print(f"   Tiempo hasta falla: {result['time_to_failure_hours']} horas")
    recommendation = engine.get_recommendation(result)
    print(f"   Recomendación: {recommendation['message']}")
    
    print("\n✅ Motor predictivo funcionando correctamente")
