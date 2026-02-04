"""
🏭 INTEGRA MIND - PLC DATA BRIDGE (Simplified)
Módulo que simula datos del PLC para el API de Integra Mind
"""
import logging
import random
from datetime import datetime

logger = logging.getLogger(__name__)

class PLCBridge:
    """Puente simulado entre el PLC y el sistema Integra Mind"""
    
    def __init__(self, host='127.0.0.1', port=5020):
        self.host = host
        self.port = port
        self.is_connected = True  # Siempre conectado en modo simulación
        logger.info(f"✅ PLC Bridge inicializado en modo SIMULACIÓN")
        
    def connect(self):
        """Establece conexión con el PLC (simulado)"""
        self.is_connected = True
        logger.info(f"✅ Conectado al PLC simulado")
        return True
    
    def disconnect(self):
        """Cierra la conexión con el PLC"""
        self.is_connected = False
        logger.info("Conexión con PLC cerrada")
    
    def read_reactor_data(self):
        """
        Lee los datos del reactor desde el PLC (simulados).
        
        Retorna:
            dict con los valores simulados
        """
        if not self.is_connected:
            return None
        
        # Generar datos simulados realistas
        base_temp = 350
        base_pressure = 650
        
        return {
            'temperatura_reactor_c': base_temp + random.randint(-20, 40),
            'presion_valvula_psi': base_pressure + random.randint(-50, 100),
            'turbina_estado': 1  # 0=OFF, 1=ON
        }
    
    def write_setpoint(self, register, value):
        """
        Escribe un valor en un registro del PLC (simulado).
        
        Args:
            register: Número de registro (0-99)
            value: Valor a escribir (0-65535)
        
        Returns:
            bool: True si se escribió correctamente
        """
        if not self.is_connected:
            logger.warning("No conectado al PLC")
            return False
        
        logger.info(f"✅ Registro {register} actualizado a {value} (simulado)")
        return True
    
    def get_status_dict(self):
        """
        Retorna el estado del PLC en formato compatible con el API de Energy.
        
        Returns:
            dict: Estado completo para el dashboard
        """
        data = self.read_reactor_data()
        
        if not data:
            return {
                'status': 'disconnected',
                'message': 'PLC no disponible'
            }
        
        # Convertir datos del PLC al formato del dashboard
        return {
            'status': 'connected',
            'current_demand_mw': 850 + random.randint(-50, 50),
            'capacity_mw': 1000,
            'utilization_percent': 85 + random.randint(-5, 10),
            'frequency_hz': 50.0 + random.uniform(-0.1, 0.1),
            'renewable_percent': 30.0 + random.uniform(-2, 5),
            'temperatura_reactor': data['temperatura_reactor_c'],
            'presion_valvula': data['presion_valvula_psi'],
            'turbina_activa': data['turbina_estado'] == 1,
            'grid_losses_mw': 5.0 + random.uniform(-0.5, 1.0),
            'timestamp': datetime.now().isoformat()
        }

# Instancia global (singleton)
plc_bridge = PLCBridge()

# Conectar al inicio
plc_bridge.connect()
