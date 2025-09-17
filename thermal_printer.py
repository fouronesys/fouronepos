"""
Módulo de Impresión Térmica para POS
Maneja la impresión automática de recibos en impresoras térmicas
usando la librería python-escpos
"""

import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from escpos.printer import Usb, Serial, Network, File
from receipt_generator import generate_thermal_receipt_text

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ThermalPrinterConfig:
    """Configuración de impresora térmica"""
    
    def __init__(self):
        # Default printer settings (can be overridden via environment variables)
        self.printer_type = os.environ.get('PRINTER_TYPE', 'file')  # 'usb', 'serial', 'network', 'file'
        
        # USB Printer settings
        self.usb_vendor_id = int(os.environ.get('PRINTER_USB_VENDOR_ID', '0x04b8'), 16)
        self.usb_product_id = int(os.environ.get('PRINTER_USB_PRODUCT_ID', '0x0202'), 16)
        
        # Serial Printer settings
        self.serial_port = os.environ.get('PRINTER_SERIAL_PORT', '/dev/ttyUSB0')
        self.serial_baudrate = int(os.environ.get('PRINTER_SERIAL_BAUDRATE', '9600'))
        
        # Network Printer settings
        self.network_host = os.environ.get('PRINTER_NETWORK_HOST', '192.168.1.100')
        self.network_port = int(os.environ.get('PRINTER_NETWORK_PORT', '9100'))
        
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
                self.printer = Network(
                    host=self.config.network_host,
                    port=self.config.network_port
                )
                logger.info(f"Inicializada impresora Red: {self.config.network_host}:{self.config.network_port}")
                
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
    
    def test_print(self) -> bool:
        """
        Imprime un recibo de prueba
        
        Returns:
            bool: True si la prueba fue exitosa
        """
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
        
        if not self.printer:
            logger.error("No hay impresora disponible para prueba")
            return False
        
        try:
            self.printer.text(test_receipt)
            if self.config.auto_cut:
                try:
                    self.printer.cut()
                except:
                    pass
            
            logger.info("Prueba de impresión completada")
            return True
            
        except Exception as e:
            logger.error(f"Error en prueba de impresión: {str(e)}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """
        Obtiene el estado de la impresora
        
        Returns:
            Dict con información del estado
        """
        return {
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


# Helper function removed - datetime imported at top


# Global printer instance
_thermal_printer = None

def get_thermal_printer() -> ThermalPrinter:
    """
    Obtiene la instancia global de la impresora térmica
    
    Returns:
        ThermalPrinter instance
    """
    global _thermal_printer
    if _thermal_printer is None:
        _thermal_printer = ThermalPrinter()
    return _thermal_printer

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

def test_thermal_printer() -> bool:
    """
    Función conveniente para probar la impresora
    
    Returns:
        bool: True si la prueba fue exitosa
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