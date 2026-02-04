#!/usr/bin/env python3
"""
🏭 INTEGRA MIND - PLC VIRTUAL SIMULATOR
Simula un Controlador Lógico Programable usando Modbus TCP
Compatible con Pymodbus 2.x
"""
import logging
from pymodbus.server.sync import StartTcpServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext

# Configurar logging
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.INFO)

def run_server():
    """Inicia el servidor Modbus TCP"""
    
    # === 1. DEFINIR LA MEMORIA DEL PLC (Registros Holding) ===
    # Reg 0 = Temperatura Reactor (°C) = 220
    # Reg 1 = Presión Válvula (PSI) = 500
    # Reg 2 = Estado Turbina (0=Off, 1=On) = 1
    
    store = ModbusSlaveContext(
        di=ModbusSequentialDataBlock(0, [0]*100),  # Discrete Inputs
        co=ModbusSequentialDataBlock(0, [0]*100),  # Coils (Salidas Digitales)
        hr=ModbusSequentialDataBlock(0, [220, 500, 1] + [0]*97),  # Holding Registers
        ir=ModbusSequentialDataBlock(0, [0]*100)   # Input Registers
    )
    
    context = ModbusServerContext(slaves=store, single=True)
    
    # === 2. IDENTIFICACIÓN DEL DISPOSITIVO ===
    identity = ModbusDeviceIdentification()
    identity.VendorName = 'Integra Mind'
    identity.ProductCode = 'SIM-PLC-001'
    identity.VendorUrl = 'http://integramind.ai'
    identity.ProductName = 'Virtual Industrial Controller'
    identity.ModelName = 'Reactor Monitor v1.0'
    identity.MajorMinorRevision = '2.5.3'
    
    # === 3. IMPRIMIR INFO E INICIAR ===
    print("=" * 70)
    print("🏭 INTEGRA MIND - PLC VIRTUAL INICIADO")
    print("=" * 70)
    print("📦 PyModbus Version: 2.5.3")
    print("📡 Protocolo: Modbus TCP/IP")
    print("🌐 Dirección: 127.0.0.1:5020")
    print()
    print("🧠 REGISTROS INICIALES (Holding Registers):")
    print("   [HR-0] Temperatura Reactor: 220 °C")
    print("   [HR-1] Presión Válvula:     500 PSI")
    print("   [HR-2] Estado Turbina:      1 (ON)")
    print()
    print("💡 Para leer estos valores desde Python:")
    print("   from pymodbus.client.sync import ModbusTcpClient")
    print("   client = ModbusTcpClient('127.0.0.1', port=5020)")
    print("   result = client.read_holding_registers(0, 3)")
    print("   print(result.registers)  # [220, 500, 1]")
    print("=" * 70)
    print("✅ Servidor en ejecución... (Ctrl+C para detener)")
    print()
    
    # Iniciar el servidor (bloqueante)
    StartTcpServer(context, identity=identity, address=("127.0.0.1", 5020))

if __name__ == "__main__":
    try:
        run_server()
    except KeyboardInterrupt:
        print("\n🛑 Servidor PLC detenido")
    except Exception as e:
        print(f"❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
