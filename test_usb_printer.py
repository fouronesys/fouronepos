#!/usr/bin/env python3
"""
Script de diagnóstico para impresoras USB
Ejecuta esto en tu PC local para identificar problemas
"""

import sys

print("=== DIAGNÓSTICO DE IMPRESORA USB ===\n")

# 1. Verificar que python-escpos está instalado
print("1️⃣ Verificando python-escpos...")
try:
    import escpos
    from escpos.printer import Usb
    print(f"   ✅ python-escpos versión: {escpos.__version__}")
except ImportError as e:
    print(f"   ❌ Error: {e}")
    print("   Instala con: pip install python-escpos")
    sys.exit(1)

# 2. Verificar permisos USB (Linux/Mac)
print("\n2️⃣ Verificando sistema operativo...")
import platform
os_name = platform.system()
print(f"   Sistema: {os_name}")

if os_name == "Linux":
    print("\n   Para Linux, necesitas permisos USB:")
    print("   - Agregar tu usuario al grupo 'lp': sudo usermod -a -G lp $USER")
    print("   - O ejecutar como root: sudo python3 script.py")
    
# 3. Listar dispositivos USB
print("\n3️⃣ Buscando impresoras USB conectadas...")
try:
    import usb.core
    devices = usb.core.find(find_all=True)
    
    print("\n   Dispositivos USB encontrados:")
    found_printer = False
    for device in devices:
        # Clase 7 = Printer
        if device.bDeviceClass == 7 or any(
            intf.bInterfaceClass == 7 
            for cfg in device 
            for intf in cfg
        ):
            found_printer = True
            print(f"\n   ✅ IMPRESORA DETECTADA:")
            print(f"      Vendor ID:  0x{device.idVendor:04x}")
            print(f"      Product ID: 0x{device.idProduct:04x}")
            try:
                print(f"      Fabricante: {usb.util.get_string(device, device.iManufacturer)}")
                print(f"      Producto:   {usb.util.get_string(device, device.iProduct)}")
            except:
                pass
    
    if not found_printer:
        print("\n   ❌ No se encontraron impresoras USB")
        print("   Verifica que:")
        print("   - La impresora está encendida")
        print("   - El cable USB está conectado")
        print("   - Los drivers están instalados")
        
except ImportError:
    print("   ❌ pyusb no está instalado")
    print("   Instala con: pip install pyusb")
except Exception as e:
    print(f"   ❌ Error: {e}")

# 4. Instrucciones para configurar
print("\n" + "="*50)
print("📋 INSTRUCCIONES DE CONFIGURACIÓN:")
print("="*50)
print("""
1. Instala las dependencias:
   pip install python-escpos pyusb

2. En Linux, instala libusb:
   sudo apt-get install libusb-1.0-0

3. Configura permisos (Linux):
   sudo usermod -a -G lp $USER
   
4. Crea regla udev (Linux):
   Crea archivo: /etc/udev/rules.d/99-escpos.rules
   Contenido: SUBSYSTEM=="usb", ATTR{idVendor}=="XXXX", ATTR{idProduct}=="YYYY", MODE="0666"
   (Reemplaza XXXX e YYYY con los IDs de tu impresora)
   
5. En Windows:
   - Instala los drivers de la impresora
   - Puede requerir ejecutar como Administrador

6. Actualiza las variables de entorno en tu configuración:
   PRINTER_TYPE=usb
   PRINTER_USB_VENDOR_ID=0xXXXX
   PRINTER_USB_PRODUCT_ID=0xYYYY
""")

print("\n💡 Tip: Ejecuta este script en tu PC local, no en Replit")
