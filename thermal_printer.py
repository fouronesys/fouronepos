"""
Módulo de Impresión Térmica para POS
Maneja la impresión automática de recibos en impresoras térmicas
usando la librería python-escpos
"""

import os
import logging
import subprocess
import re
from datetime import datetime
from typing import Optional, Dict, Any, List

# Configure logging first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Monkey-patch for python-escpos 3.1 compatibility
# The library internally tries to import DeviceNotFoundError which doesn't exist in 3.1
try:
    import escpos.exceptions
    if not hasattr(escpos.exceptions, 'DeviceNotFoundError'):
        # Create DeviceNotFoundError as an alias for USBNotFoundError or Error
        if hasattr(escpos.exceptions, 'USBNotFoundError'):
            escpos.exceptions.DeviceNotFoundError = escpos.exceptions.USBNotFoundError
        else:
            escpos.exceptions.DeviceNotFoundError = escpos.exceptions.Error
        logger.info("Monkey-patched DeviceNotFoundError for python-escpos 3.1 compatibility")
except Exception as e:
    logger.warning(f"Could not monkey-patch escpos.exceptions: {e}")

try:
    from escpos.printer import Usb, Serial, Network, File
    from escpos.exceptions import Error as EscposException
    ESCPOS_AVAILABLE = True
    logger.info("python-escpos loaded successfully")
except Exception as e:
    ESCPOS_AVAILABLE = False
    logger.warning(f"python-escpos no disponible o tiene problemas de compatibilidad: {e}")
    EscposException = Exception
    
    # Create placeholder classes when escpos is not available
    class Usb:
        def __init__(self, *args, **kwargs): pass
        def text(self, *args, **kwargs): pass
        def cut(self): pass
        def cashdraw(self, *args, **kwargs): pass
    
    class Serial:
        def __init__(self, *args, **kwargs): pass
        def text(self, *args, **kwargs): pass
        def cut(self): pass
        def cashdraw(self, *args, **kwargs): pass
    
    class Network:
        def __init__(self, *args, **kwargs): pass
        def text(self, *args, **kwargs): pass
        def cut(self): pass
        def cashdraw(self, *args, **kwargs): pass
    
    class File:
        def __init__(self, *args, **kwargs): pass
        def text(self, *args, **kwargs): pass
        def cut(self): pass
        def cashdraw(self, *args, **kwargs): pass

from receipt_generator import generate_thermal_receipt_text

class ThermalPrinterConfig:
    """Configuración de impresora térmica"""
    
    def __init__(self):
        # Default printer settings (can be overridden via environment variables)
        self.printer_type = os.environ.get('PRINTER_TYPE', 'file')  # 'usb', 'serial', 'network', 'bluetooth', 'file'
        
        # USB Printer settings
        self.usb_vendor_id = int(os.environ.get('PRINTER_USB_VENDOR_ID', '0x04b8'), 16)
        self.usb_product_id = int(os.environ.get('PRINTER_USB_PRODUCT_ID', '0x0202'), 16)
        
        # Serial Printer settings
        self.serial_port = os.environ.get('PRINTER_SERIAL_PORT', '/dev/ttyUSB0')
        self.serial_baudrate = int(os.environ.get('PRINTER_SERIAL_BAUDRATE', '9600'))
        
        # Network Printer settings
        self.network_host = os.environ.get('PRINTER_NETWORK_HOST', '192.168.1.100')
        self.network_port = int(os.environ.get('PRINTER_NETWORK_PORT', '9100'))
        
        # Bluetooth Printer settings
        self.bluetooth_mac = os.environ.get('PRINTER_BLUETOOTH_MAC', '')
        self.bluetooth_port = os.environ.get('PRINTER_BLUETOOTH_PORT', '/dev/rfcomm0')
        
        # File printer settings (for testing)
        self.file_path = os.environ.get('PRINTER_FILE_PATH', 'receipts_output.txt')
        
        # Printer capabilities
        self.paper_width = int(os.environ.get('PRINTER_PAPER_WIDTH', '80'))  # 80mm or 58mm
        self.auto_cut = os.environ.get('PRINTER_AUTO_CUT', 'true').lower() == 'true'
        self.auto_open_drawer = os.environ.get('PRINTER_AUTO_OPEN_DRAWER', 'false').lower() == 'true'

class ThermalPrinter:
    """Manejador de impresión térmica"""
    
    def __init__(self, config: Optional[ThermalPrinterConfig] = None):
        self.config = config or ThermalPrinterConfig()
        self.printer = None
        self._initialize_printer()
    
    def _initialize_printer(self):
        """Inicializa la conexión con la impresora"""
        try:
            if self.config.printer_type == 'usb':
                self.printer = Usb(
                    self.config.usb_vendor_id,
                    self.config.usb_product_id
                )
                logger.info(f"Inicializada impresora USB: {self.config.usb_vendor_id:04x}:{self.config.usb_product_id:04x}")
                
            elif self.config.printer_type == 'serial':
                self.printer = Serial(
                    devfile=self.config.serial_port,
                    baudrate=self.config.serial_baudrate
                )
                logger.info(f"Inicializada impresora Serial: {self.config.serial_port}")
                
            elif self.config.printer_type == 'network':
                # Test network connectivity first
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                try:
                    result = sock.connect_ex((self.config.network_host, self.config.network_port))
                    sock.close()
                    if result != 0:
                        raise ConnectionError(f"No se puede conectar a {self.config.network_host}:{self.config.network_port}. La impresora no es accesible desde el servidor.")
                except socket.timeout:
                    raise ConnectionError(f"Timeout al conectar a {self.config.network_host}:{self.config.network_port}. La impresora no responde.")
                except socket.gaierror:
                    raise ConnectionError(f"No se puede resolver el host {self.config.network_host}. Verifica la dirección IP.")
                
                self.printer = Network(
                    host=self.config.network_host,
                    port=self.config.network_port
                )
                logger.info(f"Inicializada impresora Red: {self.config.network_host}:{self.config.network_port}")
                
            elif self.config.printer_type == 'bluetooth':
                if not self.config.bluetooth_mac:
                    raise ValueError("Se requiere dirección MAC para impresora Bluetooth")
                
                try:
                    self.printer = Serial(
                        devfile=self.config.bluetooth_port,
                        baudrate=self.config.serial_baudrate,
                        timeout=2.0
                    )
                    logger.info(f"Inicializada impresora Bluetooth: {self.config.bluetooth_mac} en {self.config.bluetooth_port}")
                except Exception as bt_error:
                    logger.error(f"Error conectando Bluetooth, intentar bindear dispositivo primero: {str(bt_error)}")
                    raise
                
            else:  # file printer (default for testing)
                # Create output directory if it doesn't exist
                os.makedirs('static/receipts_output', exist_ok=True)
                output_file = os.path.join('static/receipts_output', self.config.file_path)
                self.printer = File(output_file)
                logger.info(f"Inicializada impresora Archivo: {output_file}")
                
        except Exception as e:
            logger.error(f"Error inicializando impresora {self.config.printer_type}: {str(e)}")
            # Fallback to file printer
            try:
                os.makedirs('static/receipts_output', exist_ok=True)
                output_file = os.path.join('static/receipts_output', 'fallback_receipts.txt')
                self.printer = File(output_file)
                logger.info(f"Fallback a impresora archivo: {output_file}")
            except Exception as fallback_error:
                logger.error(f"Error en fallback: {str(fallback_error)}")
                self.printer = None
    
    def print_receipt(self, sale_data: Dict[str, Any]) -> bool:
        """
        Imprime un recibo térmico
        
        Args:
            sale_data: Datos de la venta para generar el recibo
            
        Returns:
            bool: True si la impresión fue exitosa, False en caso contrario
        """
        if not self.printer:
            logger.error("No hay impresora disponible")
            return False
        
        try:
            # Generate receipt text
            receipt_text = generate_thermal_receipt_text(sale_data)
            
            # Print receipt
            self.printer.text(receipt_text)
            
            # Add extra line breaks for tear-off
            self.printer.text("\n\n")
            
            # Cut paper if supported
            if self.config.auto_cut:
                try:
                    self.printer.cut()
                except Exception as cut_error:
                    logger.warning(f"Error cortando papel: {str(cut_error)}")
            
            # Open cash drawer if configured
            if self.config.auto_open_drawer:
                try:
                    self.printer.cashdraw(2)  # Standard cash drawer command
                except Exception as drawer_error:
                    logger.warning(f"Error abriendo cajón: {str(drawer_error)}")
            
            logger.info(f"Recibo impreso exitosamente para venta {sale_data.get('id', 'N/A')}")
            return True
            
        except Exception as e:
            logger.error(f"Error imprimiendo recibo: {str(e)}")
            return False
    
    def test_print(self) -> Dict[str, Any]:
        """
        Imprime un recibo de prueba y verifica la conexión
        
        Returns:
            Dict con el resultado de la prueba: {
                'success': bool,
                'message': str,
                'error': str (opcional)
            }
        """
        # Verificar que hay impresora configurada
        if not self.printer:
            error_msg = "No hay impresora disponible. Verifica la configuración."
            logger.error(error_msg)
            return {
                'success': False,
                'message': error_msg,
                'error': 'PRINTER_NOT_CONFIGURED'
            }
        
        # Para impresoras de red, verificar conectividad primero
        if self.config.printer_type == 'network':
            import socket
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                result = sock.connect_ex((self.config.network_host, self.config.network_port))
                sock.close()
                
                if result != 0:
                    error_msg = f"❌ No se puede conectar a la impresora en {self.config.network_host}:{self.config.network_port}. La impresora no es accesible desde este servidor."
                    logger.error(error_msg)
                    return {
                        'success': False,
                        'message': error_msg,
                        'error': 'NETWORK_UNREACHABLE',
                        'details': 'La impresora está en una red privada y el servidor no puede alcanzarla. Necesitas usar una impresora accesible desde internet o instalar un servidor local de impresión.'
                    }
            except socket.timeout:
                error_msg = f"❌ Timeout al conectar a {self.config.network_host}:{self.config.network_port}. La impresora no responde."
                logger.error(error_msg)
                return {
                    'success': False,
                    'message': error_msg,
                    'error': 'CONNECTION_TIMEOUT'
                }
            except Exception as e:
                error_msg = f"❌ Error verificando conectividad: {str(e)}"
                logger.error(error_msg)
                return {
                    'success': False,
                    'message': error_msg,
                    'error': 'CONNECTION_ERROR'
                }
        
        # Intentar imprimir
        test_receipt = """
========================================
           PRUEBA DE IMPRESORA
========================================

Esta es una prueba de impresión.
Si puede leer este mensaje, la
impresora está funcionando correctamente.

========================================
        """ + f"""
Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
========================================

        """
        
        try:
            self.printer.text(test_receipt)
            if self.config.auto_cut:
                try:
                    self.printer.cut()
                except:
                    pass
            
            success_msg = f"✅ Prueba de impresión enviada exitosamente a {self.config.printer_type}"
            logger.info(success_msg)
            return {
                'success': True,
                'message': success_msg
            }
            
        except Exception as e:
            error_msg = f"❌ Error al imprimir: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'message': error_msg,
                'error': 'PRINT_ERROR',
                'details': str(e)
            }
    
    def get_status(self) -> Dict[str, Any]:
        """
        Obtiene el estado de la impresora con verificación de conectividad
        
        Returns:
            Dict con información del estado y conectividad
        """
        status = {
            'printer_type': self.config.printer_type,
            'paper_width': f"{self.config.paper_width}mm",
            'auto_cut': self.config.auto_cut,
            'auto_open_drawer': self.config.auto_open_drawer,
            'initialized': self.printer is not None,
            'config': {
                'usb_ids': f"{self.config.usb_vendor_id:04x}:{self.config.usb_product_id:04x}" if self.config.printer_type == 'usb' else None,
                'serial_port': self.config.serial_port if self.config.printer_type == 'serial' else None,
                'network_address': f"{self.config.network_host}:{self.config.network_port}" if self.config.printer_type == 'network' else None,
                'file_path': self.config.file_path if self.config.printer_type == 'file' else None
            }
        }
        
        # Para impresoras de red, verificar conectividad
        if self.config.printer_type == 'network' and self.printer is not None:
            import socket
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex((self.config.network_host, self.config.network_port))
                sock.close()
                
                if result == 0:
                    status['connectivity'] = 'connected'
                    status['connectivity_message'] = f"✅ Conectado a {self.config.network_host}:{self.config.network_port}"
                else:
                    status['connectivity'] = 'unreachable'
                    status['connectivity_message'] = f"❌ No se puede alcanzar {self.config.network_host}:{self.config.network_port}"
            except Exception as e:
                status['connectivity'] = 'error'
                status['connectivity_message'] = f"❌ Error verificando conectividad: {str(e)}"
        else:
            status['connectivity'] = 'unknown'
            status['connectivity_message'] = 'Verificación de conectividad no disponible para este tipo de impresora'
        
        return status


# Helper function removed - datetime imported at top


# Global printer instance
_thermal_printer = None

def get_thermal_printer(force_reload: bool = False) -> ThermalPrinter:
    """
    Obtiene la instancia global de la impresora térmica
    
    Args:
        force_reload: Si True, fuerza la recarga de la configuración
        
    Returns:
        ThermalPrinter instance
    """
    global _thermal_printer
    if _thermal_printer is None or force_reload:
        _thermal_printer = ThermalPrinter()
    return _thermal_printer

def reset_thermal_printer():
    """
    Invalida el singleton de la impresora térmica para forzar recarga de configuración
    """
    global _thermal_printer
    _thermal_printer = None
    logger.info("Singleton de impresora térmica invalidado")

def print_receipt_auto(sale_data: Dict[str, Any]) -> bool:
    """
    Función conveniente para imprimir recibo automáticamente
    
    Args:
        sale_data: Datos de la venta
        
    Returns:
        bool: True si la impresión fue exitosa
    """
    printer = get_thermal_printer()
    return printer.print_receipt(sale_data)

def test_thermal_printer() -> Dict[str, Any]:
    """
    Función conveniente para probar la impresora
    
    Returns:
        Dict con el resultado de la prueba
    """
    printer = get_thermal_printer()
    return printer.test_print()

def get_thermal_printer_status() -> Dict[str, Any]:
    """
    Función conveniente para obtener el estado de la impresora
    
    Returns:
        Dict con información del estado
    """
    printer = get_thermal_printer()
    return printer.get_status()


def scan_bluetooth_devices(scan_duration: int = 8) -> List[Dict[str, str]]:
    """
    Escanea dispositivos Bluetooth cercanos usando bluetoothctl
    
    Args:
        scan_duration: Duración del escaneo en segundos
        
    Returns:
        Lista de dispositivos encontrados con MAC y nombre
    """
    devices = []
    
    try:
        bluetoothctl_path = subprocess.run(
            ['which', 'bluetoothctl'],
            capture_output=True,
            text=True,
            timeout=2
        )
        
        if bluetoothctl_path.returncode != 0:
            logger.warning("bluetoothctl no disponible - retornando dispositivos de prueba")
            return [{
                'mac_address': '00:11:22:33:44:55',
                'name': 'Demo Thermal Printer (Bluetooth no disponible en este sistema)',
                'type': 'demo'
            }]
    except (FileNotFoundError, subprocess.SubprocessError):
        logger.warning("Comando 'which' no disponible - retornando dispositivos de prueba")
        return [{
            'mac_address': '00:11:22:33:44:55',
            'name': 'Demo Thermal Printer (Bluetooth no soportado)',
            'type': 'demo'
        }]
    
    try:
        logger.info(f"Iniciando escaneo Bluetooth por {scan_duration} segundos...")
        
        process = subprocess.Popen(
            ['bluetoothctl', 'scan', 'on'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        import time
        time.sleep(scan_duration)
        
        process.terminate()
        process.wait(timeout=2)
        
        result = subprocess.run(
            ['bluetoothctl', 'devices'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                match = re.match(r'Device\s+([0-9A-F:]{17})\s+(.+)', line, re.IGNORECASE)
                if match:
                    mac_address = match.group(1)
                    device_name = match.group(2).strip()
                    
                    if 'print' in device_name.lower() or 'thermal' in device_name.lower() or 'pos' in device_name.lower():
                        devices.append({
                            'mac_address': mac_address,
                            'name': device_name,
                            'type': 'printer_detected'
                        })
                    else:
                        devices.append({
                            'mac_address': mac_address,
                            'name': device_name,
                            'type': 'unknown'
                        })
            
            logger.info(f"Escaneo completado. Encontrados {len(devices)} dispositivos")
        else:
            logger.error(f"Error escaneando dispositivos: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        logger.error("Timeout escaneando dispositivos Bluetooth")
    except Exception as e:
        logger.error(f"Error en escaneo Bluetooth: {str(e)}")
    
    return devices


def bind_bluetooth_printer(mac_address: str, rfcomm_port: str = '/dev/rfcomm0') -> Dict[str, Any]:
    """
    Bindea una impresora Bluetooth a un puerto RFCOMM
    
    Args:
        mac_address: Dirección MAC de la impresora
        rfcomm_port: Puerto RFCOMM a usar (default: /dev/rfcomm0)
        
    Returns:
        Dict con resultado de la operación
    """
    if not re.match(r'^([0-9A-F]{2}:){5}[0-9A-F]{2}$', mac_address, re.IGNORECASE):
        return {
            'success': False,
            'message': 'Dirección MAC inválida'
        }
    
    try:
        logger.info(f"Bindeando impresora {mac_address} a {rfcomm_port}...")
        
        try:
            rfcomm_path = subprocess.run(
                ['which', 'rfcomm'],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            if rfcomm_path.returncode != 0:
                return {
                    'success': False,
                    'message': 'rfcomm no disponible en el sistema. Bluetooth no soportado en este entorno.'
                }
        except (FileNotFoundError, subprocess.SubprocessError):
            return {
                'success': False,
                'message': 'Herramientas Bluetooth no disponibles. Este entorno no soporta Bluetooth.'
            }
        
        unbind_result = subprocess.run(
            ['rfcomm', 'release', rfcomm_port],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        bind_result = subprocess.run(
            ['rfcomm', 'bind', rfcomm_port, mac_address],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if bind_result.returncode == 0:
            logger.info(f"Impresora bindeada exitosamente en {rfcomm_port}")
            return {
                'success': True,
                'message': f'Impresora conectada en {rfcomm_port}',
                'port': rfcomm_port,
                'mac_address': mac_address
            }
        else:
            error_msg = bind_result.stderr or 'Error desconocido'
            if 'Permission denied' in error_msg or 'not permitted' in error_msg:
                error_msg = 'Permisos insuficientes. Ejecute el sistema con privilegios de Bluetooth.'
            logger.error(f"Error bindeando impresora: {error_msg}")
            return {
                'success': False,
                'message': f'Error al conectar: {error_msg}'
            }
            
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'message': 'Timeout al conectar la impresora'
        }
    except Exception as e:
        logger.error(f"Error en bind_bluetooth_printer: {str(e)}")
        return {
            'success': False,
            'message': f'Error: {str(e)}'
        }


def check_bluetooth_available() -> Dict[str, Any]:
    """
    Verifica si Bluetooth está disponible en el sistema
    
    Returns:
        Dict con información de disponibilidad
    """
    try:
        result = subprocess.run(
            'which bluetoothctl',
            shell=True,
            capture_output=True,
            text=True,
            timeout=2
        )
        
        bluetoothctl_available = result.returncode == 0
        
        if bluetoothctl_available:
            status_result = subprocess.run(
                'bluetoothctl show',
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            powered = 'Powered: yes' in status_result.stdout
            
            return {
                'available': True,
                'powered': powered,
                'message': 'Bluetooth disponible' if powered else 'Bluetooth apagado - active el adaptador'
            }
        else:
            return {
                'available': False,
                'powered': False,
                'message': 'Bluetooth no está instalado en el sistema'
            }
            
    except Exception as e:
        logger.error(f"Error verificando Bluetooth: {str(e)}")
        return {
            'available': False,
            'powered': False,
            'message': f'Error verificando Bluetooth: {str(e)}'
        }