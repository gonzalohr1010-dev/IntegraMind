#!/usr/bin/env python3
"""
🎭 INTEGRA MIND - PLC DYNAMICS SIMULATOR
Simula el comportamiento dinámico de un reactor industrial.
Escribe valores cambiantes al PLC para crear una experiencia realista.
"""
import time
import math
import random
from pymodbus.client.sync import ModbusTcpClient

class ReactorSimulator:
    """Simula el comportamiento dinámico de un reactor nuclear/térmico"""
    
    def __init__(self, plc_host='127.0.0.1', plc_port=5020):
        self.client = ModbusTcpClient(plc_host, port=plc_port)
        self.time_offset = 0
        
        # Parámetros de operación normal
        self.base_temp = 220  # °C
        self.base_pressure = 500  # PSI
        self.turbine_on = True
        
        # Variables para simulación suave
        self.temp_trend = 0  # Tendencia de temperatura
        self.pressure_noise = 0
        
    def connect(self):
        """Conecta al PLC"""
        if self.client.connect():
            print("✅ Conectado al PLC Virtual")
            return True
        else:
            print("❌ No se pudo conectar al PLC")
            return False
    
    def write_register(self, address, value):
        """Escribe un valor en un registro del PLC"""
        try:
            result = self.client.write_register(address=address, value=int(value), unit=1)
            if result.isError():
                print(f"⚠️ Error escribiendo registro {address}")
                return False
            return True
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def simulate_temperature(self):
        """
        Simula temperatura del reactor con comportamiento realista:
        - Oscilación natural (seno)
        - Deriva lenta (tendencia)
        - Ruido aleatorio
        """
        # Componente cíclica (oscilación natural del sistema)
        cycle = 15 * math.sin(self.time_offset / 20)
        
        # Deriva lenta (tendencia que cambia cada ~2 minutos)
        if random.random() < 0.01:  # 1% de probabilidad cada ciclo
            self.temp_trend = random.uniform(-10, 10)
        
        # Ruido pequeño
        noise = random.uniform(-3, 3)
        
        # Temperatura resultante
        temp = self.base_temp + cycle + self.temp_trend + noise
        
        # Mantener en rango seguro (180-300°C normalmente)
        temp = max(180, min(300, temp))
        
        return int(temp)
    
    def simulate_pressure(self):
        """
        Simula presión de válvula con variaciones realistas
        """
        # Ruido de presión más errático
        if random.random() < 0.05:
            self.pressure_noise = random.uniform(-20, 20)
        
        # Oscilación rápida
        fast_osc = 10 * math.sin(self.time_offset / 3)
        
        pressure = self.base_pressure + fast_osc + self.pressure_noise
        
        # Mantener en rango (400-700 PSI normalmente)
        pressure = max(400, min(700, pressure))
        
        return int(pressure)
    
    def simulate_turbine(self):
        """
        Simula estado de turbina (puede apagarse/encenderse ocasionalmente)
        """
        # 0.5% de probabilidad de cambiar estado
        if random.random() < 0.005:
            self.turbine_on = not self.turbine_on
            status = "ENCENDIDA" if self.turbine_on else "APAGADA"
            print(f"⚙️ Turbina {status}")
        
        return 1 if self.turbine_on else 0
    
    def run_simulation(self):
        """Ejecuta el loop principal de simulación"""
        print("=" * 70)
        print("🎭 REACTOR DYNAMICS SIMULATOR INICIADO")
        print("=" * 70)
        print("Este script simula el comportamiento dinámico de un reactor.")
        print("Los valores cambiarán gradualmente para simular operación real.")
        print("=" * 70)
        print()
        
        try:
            cycle_count = 0
            while True:
                cycle_count += 1
                self.time_offset += 1
                
                # Calcular valores
                temp = self.simulate_temperature()
                pressure = self.simulate_pressure()
                turbine = self.simulate_turbine()
                
                # Escribir al PLC
                self.write_register(0, temp)      # Temperatura en HR-0
                self.write_register(1, pressure)  # Presión en HR-1
                self.write_register(2, turbine)   # Turbina en HR-2
                
                # Mostrar estado cada 10 ciclos
                if cycle_count % 10 == 0:
                    print(f"📊 [CICLO {cycle_count:04d}] Reactor actualizado:")
                    print(f"   🌡️  Temperatura: {temp}°C")
                    print(f"   💨 Presión:      {pressure} PSI")
                    print(f"   ⚙️  Turbina:      {'ON' if turbine else 'OFF'}")
                    print()
                
                # Esperar 1 segundo antes del próximo ciclo
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n🛑 Simulación detenida por el usuario")
        finally:
            self.client.close()
            print("👋 Conexión cerrada")

def main():
    simulator = ReactorSimulator()
    
    if simulator.connect():
        simulator.run_simulation()
    else:
        print("⚠️ Asegúrate de que plc_simulator.py está corriendo")

if __name__ == "__main__":
    main()
