"""
Dominican Republic Fiscal Receipt Generator
Generador de recibos fiscales para República Dominicana

This module handles the generation of fiscal receipts in PDF format
compliant with DGII (Dominican Tax Authority) requirements.
"""

import io
import os
from datetime import datetime
from typing import Dict, List, Any, Optional

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch, mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.colors import black, blue, red

from utils import format_currency_rd, calculate_itbis, get_company_info_for_receipt


class DominicanReceiptGenerator:
    """
    Generador simplificado de recibos fiscales para RD
    Optimizado para impresoras térmicas 58mm y 80mm
    Información fiscal solo al inicio, sin tablas complicadas
    """

    def __init__(self, format_type='80mm'):
        if format_type == '58mm':
            self.page_size = (58 * mm, 200 * mm)
            self.margin = 2 * mm
            self.text_width = 32
        else:
            self.page_size = (80 * mm, 200 * mm)
            self.margin = 3 * mm
            self.text_width = 40

        self.format_type = format_type
        self.styles = self._create_styles()

    def _create_styles(self):
        """Create paragraph styles for the receipt"""
        from reportlab.lib.styles import StyleSheet1
        
        # Create a new stylesheet to avoid conflicts
        styles = StyleSheet1()
        
        # Add base styles
        styles.add(ParagraphStyle('Normal', fontSize=8, fontName='Helvetica'))
        styles.add(ParagraphStyle('Title', fontSize=12, alignment=TA_CENTER, fontName='Helvetica-Bold'))
        styles.add(ParagraphStyle('Info', fontSize=7, alignment=TA_CENTER, fontName='Helvetica'))
        styles.add(ParagraphStyle('Item', fontSize=8, alignment=TA_LEFT, fontName='Helvetica'))
        styles.add(ParagraphStyle('Total', fontSize=10, alignment=TA_RIGHT, fontName='Helvetica-Bold'))
        styles.add(ParagraphStyle('Footer', fontSize=7, alignment=TA_CENTER, fontName='Helvetica'))
        return styles

    # ----------- RECIBO PDF -----------

    def generate_fiscal_receipt(self, sale_data: Dict[str, Any], output_path: Optional[str] = None) -> str:
        company_info = get_company_info_for_receipt()

        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            sale_id = sale_data.get('id', 'unknown')
            filename = f"recibo_fiscal_{sale_id}_{timestamp}.pdf"
            output_path = os.path.join('static', 'receipts', filename)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

        doc = SimpleDocTemplate(
            output_path,
            pagesize=self.page_size,
            rightMargin=self.margin,
            leftMargin=self.margin,
            topMargin=self.margin,
            bottomMargin=self.margin
        )

        content = []
        content.extend(self._build_header(company_info, sale_data))
        content.extend(self._build_items(sale_data))
        content.extend(self._build_totals(sale_data))
        content.extend(self._build_footer(company_info))

        doc.build(content)
        return output_path

    def _build_header(self, company_info: Dict[str, str], sale_data: Dict[str, Any]) -> List:
        content = []
        # Información fiscal al inicio
        content.append(Paragraph(company_info['name'], self.styles['Title']))
        if company_info.get('rnc'):
            content.append(Paragraph(f"RNC: {company_info['rnc']}", self.styles['Info']))
        if company_info.get('address'):
            content.append(Paragraph(company_info['address'], self.styles['Info']))
        if company_info.get('phone'):
            content.append(Paragraph(f"Tel: {company_info['phone']}", self.styles['Info']))
        content.append(Spacer(1, 2*mm))

        # Recibo
        content.append(Paragraph("RECIBO FISCAL", self.styles['Title']))

        # Datos de la venta
        sale_date = sale_data.get('created_at', datetime.now())
        if isinstance(sale_date, str):
            sale_date = datetime.fromisoformat(sale_date.replace('Z', '+00:00'))
        content.append(Paragraph(f"Fecha: {sale_date.strftime('%d/%m/%Y %H:%M:%S')}", self.styles['Item']))
        content.append(Paragraph(f"Venta No: {sale_data.get('id', 'N/A')}", self.styles['Item']))
        if sale_data.get('ncf'):
            content.append(Paragraph(f"NCF: {sale_data['ncf']}", self.styles['Item']))

        payment_method = sale_data.get('payment_method', 'efectivo').title()
        content.append(Paragraph(f"Método de pago: {payment_method}", self.styles['Item']))
        content.append(Spacer(1, 2*mm))
        return content

    def _build_items(self, sale_data: Dict[str, Any]) -> List:
        content = [Paragraph("DETALLE DE COMPRA", self.styles['Title'])]
        for item in sale_data.get('items', []):
            qty = item.get('quantity', 1)
            name = item.get('product_name', item.get('name', 'Producto'))
            price = item.get('price', 0)
            total = qty * price
            line = f"{qty} x {name}  @ {format_currency_rd(price)} = {format_currency_rd(total)}"
            content.append(Paragraph(line, self.styles['Item']))
        content.append(Spacer(1, 2*mm))
        return content

    def _build_totals(self, sale_data: Dict[str, Any]) -> List:
        content = []
        subtotal = sale_data.get('subtotal', 0)
        tax = sale_data.get('tax_amount', calculate_itbis(subtotal))
        total = sale_data.get('total', subtotal + tax)

        content.append(Paragraph(f"Subtotal: {format_currency_rd(subtotal)}", self.styles['Item']))
        content.append(Paragraph(f"ITBIS (18%): {format_currency_rd(tax)}", self.styles['Item']))
        content.append(Paragraph(f"TOTAL: {format_currency_rd(total)}", self.styles['Total']))
        content.append(Spacer(1, 2*mm))
        return content

    def _build_footer(self, company_info: Dict[str, str]) -> List:
        content = []
        if company_info.get('message'):
            content.append(Paragraph(company_info['message'], self.styles['Footer']))
        content.append(Paragraph("Válido para efectos fiscales - DGII", self.styles['Footer']))
        content.append(Paragraph(f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}", self.styles['Footer']))
        return content

    # ----------- RECIBO TÉRMICO -----------

    def generate_thermal_receipt(self, sale_data: Dict[str, Any]) -> str:
        company_info = get_company_info_for_receipt()
        lines = []
        width = self.text_width
        c = lambda t: t.center(width)

        # Encabezado fiscal
        lines.append(c(company_info['name']))
        if company_info.get('rnc'):
            lines.append(c(f"RNC: {company_info['rnc']}"))
        if company_info.get('address'):
            lines.append(c(company_info['address']))
        if company_info.get('phone'):
            lines.append(c(f"Tel: {company_info['phone']}"))
        lines.append("-"*width)
        lines.append(c("RECIBO FISCAL"))

        # Venta
        sale_date = sale_data.get('created_at', datetime.now())
        if isinstance(sale_date, str):
            sale_date = datetime.fromisoformat(sale_date.replace('Z', '+00:00'))
        lines.append(f"Fecha: {sale_date.strftime('%d/%m/%Y %H:%M:%S')}")
        lines.append(f"Venta No: {sale_data.get('id','N/A')}")
        if sale_data.get('ncf'):
            lines.append(f"NCF: {sale_data['ncf']}")
        lines.append(f"Método: {sale_data.get('payment_method','Efectivo').title()}")
        lines.append("-"*width)

        # Items
        for item in sale_data.get('items', []):
            qty = item.get('quantity', 1)
            name = item.get('product_name', item.get('name', 'Producto'))[:20]
            total = qty * item.get('price',0)
            lines.append(f"{qty} x {name} = {format_currency_rd(total)}")

        # Totales
        subtotal = sale_data.get('subtotal', 0)
        tax = sale_data.get('tax_amount', calculate_itbis(subtotal))
        total = sale_data.get('total', subtotal + tax)
        lines.append("-"*width)
        lines.append(f"Subtotal: {format_currency_rd(subtotal)}")
        lines.append(f"ITBIS (18%): {format_currency_rd(tax)}")
        lines.append(f"TOTAL: {format_currency_rd(total)}")
        lines.append("-"*width)

        if company_info.get('message'):
            lines.append(c(company_info['message']))
        lines.append(c("Válido para efectos fiscales - DGII"))
        lines.append(c(f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"))

        return "\n".join(lines)

# Helper functions for easy use
def generate_pdf_receipt(sale_data: Dict[str, Any], output_path: Optional[str] = None) -> str:
    """
    Convenience function to generate a PDF receipt
    
    Args:
        sale_data: Sale information dictionary
        output_path: Optional output path
        
    Returns:
        Path to generated PDF
    """
    generator = DominicanReceiptGenerator()
    return generator.generate_fiscal_receipt(sale_data, output_path)


def generate_thermal_receipt_text(sale_data: Dict[str, Any]) -> str:
    """
    Convenience function to generate thermal receipt text
    
    Args:
        sale_data: Sale information dictionary
        
    Returns:
        Formatted text for thermal printing
    """
    generator = DominicanReceiptGenerator()
    return generator.generate_thermal_receipt(sale_data)