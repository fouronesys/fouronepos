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
    Generador de recibos fiscales para RD
    Optimizado para impresoras térmicas 58mm y 80mm
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
        styles = getSampleStyleSheet()

        styles.add(ParagraphStyle(
            name='CompanyName',
            fontSize=13,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            spaceAfter=4
        ))
        styles.add(ParagraphStyle(
            name='CompanyInfo',
            fontSize=7,
            alignment=TA_CENTER,
            fontName='Helvetica'
        ))
        styles.add(ParagraphStyle(
            name='ReceiptHeader',
            fontSize=10,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            spaceBefore=4,
            spaceAfter=4
        ))
        styles.add(ParagraphStyle(
            name='Item',
            fontSize=8,
            alignment=TA_CENTER,
            fontName='Helvetica'
        ))
        styles.add(ParagraphStyle(
            name='Total',
            fontSize=10,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            textColor=colors.black,
            spaceBefore=4,
            spaceAfter=4
        ))
        styles.add(ParagraphStyle(
            name='Footer',
            fontSize=7,
            alignment=TA_CENTER,
            fontName='Helvetica'
        ))
        return styles

    # ----------- CONSTRUCCIÓN DEL RECIBO PDF -----------

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
        content.extend(self._build_company_header(company_info))
        content.extend(self._build_receipt_details(sale_data))
        content.extend(self._build_items_list(sale_data))
        content.extend(self._build_totals_section(sale_data))
        content.extend(self._build_footer(company_info))

        doc.build(content)
        return output_path

    def _build_company_header(self, company_info: Dict[str, str]) -> List:
        content = []

        logo_path = company_info.get('logo', '')
        if logo_path:
            # Convert web URL to file system path
            if logo_path.startswith('/'):
                file_path = logo_path.lstrip('/')
            else:
                file_path = logo_path
            
            if os.path.exists(file_path):
                try:
                    logo_w, logo_h = (14*mm, 10*mm) if self.format_type == '58mm' else (20*mm, 15*mm)
                    logo = Image(file_path, width=logo_w, height=logo_h)
                    logo.hAlign = 'CENTER'
                    content.append(logo)
                    content.append(Spacer(1, 2*mm))
                except:
                    pass

        content.append(Paragraph(company_info['name'], self.styles['CompanyName']))

        for field in ['rnc', 'address', 'phone', 'email']:
            if company_info.get(field):
                value = company_info[field]
                label = "RNC: " if field == 'rnc' else "Tel: " if field == 'phone' else ""
                content.append(Paragraph(f"{label}{value}", self.styles['CompanyInfo']))

        content.append(Spacer(1, 3*mm))
        return content

    def _build_receipt_details(self, sale_data: Dict[str, Any]) -> List:
        content = []

        sale_date = sale_data.get('created_at', datetime.now())
        if isinstance(sale_date, str):
            sale_date = datetime.fromisoformat(sale_date.replace('Z', '+00:00'))

        content.append(Paragraph(f"Fecha: {sale_date.strftime('%d/%m/%Y %H:%M:%S')}", self.styles['Item']))
        content.append(Paragraph(f"Venta No: {sale_data.get('id', 'N/A')}", self.styles['Item']))

        if sale_data.get('ncf'):
            content.append(Paragraph(f"NCF: {sale_data['ncf']}", self.styles['Item']))

        metodo = {
            'efectivo': 'Efectivo',
            'tarjeta': 'Tarjeta',
            'transferencia': 'Transferencia'
        }.get(sale_data.get('payment_method', 'efectivo'), sale_data.get('payment_method', 'Efectivo'))

        content.append(Paragraph(f"Método de pago: {metodo}", self.styles['Item']))
        return content

    def _build_items_list(self, sale_data: Dict[str, Any]) -> List:
        """Build items list with line-by-line tax display for included taxes"""
        content = []
        
        content.append(Paragraph("-" * (self.text_width if hasattr(self, 'text_width') else 32), self.styles['Item']))
        
        items = sale_data.get('items', [])
        for item in items:
            qty = item.get("quantity", 1)
            name = item.get("product_name", item.get("name", "Producto"))
            price = item.get("price", 0)
            total = qty * price
            tax_rate = item.get("tax_rate", 0)
            is_tax_included = item.get("is_tax_included", False)
            
            # Truncate name based on format
            max_name_len = 20 if self.format_type == '58mm' else 25
            if len(name) > max_name_len:
                name = name[:max_name_len-3] + "..."
            
            # Format item line
            content.append(Paragraph(f"{qty}x {name}", self.styles['Item']))
            content.append(Paragraph(f"    {format_currency_rd(price)} c/u = {format_currency_rd(total)}", self.styles['Item']))
            
            # Show tax line for included taxes
            if is_tax_included and tax_rate > 0:
                # Calculate included tax amount per line
                tax_amount = total - (total / (1 + tax_rate))
                tax_percentage = int(tax_rate * 100)
                content.append(Paragraph(f"    (ITBIS {tax_percentage}%)      {format_currency_rd(tax_amount)}", self.styles['Item']))
        
        content.append(Paragraph("-" * (self.text_width if hasattr(self, 'text_width') else 32), self.styles['Item']))
        return content

    def _build_totals_section(self, sale_data: Dict[str, Any]) -> List:
        content = []
        subtotal = sale_data.get('subtotal', 0)
        tax = sale_data.get('tax_amount', 0)
        total = sale_data.get('total', subtotal + tax)
        
        # Check if there are any items with included taxes
        items = sale_data.get('items', [])
        has_included_tax = any(item.get('is_tax_included', False) and item.get('tax_rate', 0) > 0 for item in items)
        has_added_tax = any(not item.get('is_tax_included', False) and item.get('tax_rate', 0) > 0 for item in items)

        content.append(Paragraph(f"Subtotal: {format_currency_rd(subtotal)}", self.styles['Item']))
        
        # Show tax information based on type
        if tax > 0.01:
            if has_included_tax and not has_added_tax:
                # Only included taxes
                content.append(Paragraph(f"ITBIS (incl.): {format_currency_rd(tax)}", self.styles['Item']))
            elif has_added_tax and not has_included_tax:
                # Only added taxes - calculate percentage
                tax_percentage = round((tax / subtotal) * 100) if subtotal > 0 else 0
                content.append(Paragraph(f"ITBIS ({tax_percentage}%): {format_currency_rd(tax)}", self.styles['Item']))
            else:
                # Mixed taxes
                content.append(Paragraph(f"ITBIS: {format_currency_rd(tax)}", self.styles['Item']))
        elif tax == 0:
            content.append(Paragraph("Sin impuestos", self.styles['Item']))
            
        content.append(Paragraph(f"<b>TOTAL: {format_currency_rd(total)}</b>", self.styles['Total']))
        return content

    def _build_fiscal_info(self, sale_data: Dict[str, Any], company_info: Dict[str, str]) -> List:
        content = [Paragraph("INFORMACIÓN FISCAL", self.styles['ReceiptHeader'])]

        if company_info.get('rnc'):
            content.append(Paragraph(f"RNC Empresa: {company_info['rnc']}", self.styles['Footer']))

        if sale_data.get('ncf'):
            ncf = sale_data['ncf']
            tipo = "Crédito Fiscal" if ncf.startswith("B") else "Consumidor Final" if ncf.startswith("E") else "Comprobante Fiscal"
            content.append(Paragraph(f"NCF: {ncf}", self.styles['Footer']))
            content.append(Paragraph(f"Tipo: {tipo}", self.styles['Footer']))

        content.append(Paragraph(f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", self.styles['Footer']))
        return content

    def _build_footer(self, company_info: Dict[str, str]) -> List:
        content = []
        if company_info.get('message'):
            content.append(Paragraph(company_info['message'], self.styles['Footer']))
        if company_info.get('footer'):
            content.append(Paragraph(company_info['footer'], self.styles['Footer']))

        content.append(Paragraph("Este recibo es válido para efectos fiscales según la DGII", self.styles['Footer']))
        return content

    # ----------- RECIBO EN TEXTO PARA IMPRESORAS TÉRMICAS -----------

    def generate_thermal_receipt(self, sale_data: Dict[str, Any]) -> str:
        company_info = get_company_info_for_receipt()
        r = []
        c = lambda t: t.center(self.text_width)

        r.append("=" * self.text_width)
        r.append(c(company_info['name']))
        if company_info.get('rnc'): r.append(c(f"RNC: {company_info['rnc']}"))
        if company_info.get('address'): r.append(c(company_info['address']))
        if company_info.get('phone'): r.append(c(f"Tel: {company_info['phone']}"))
        r.append("=" * self.text_width)
        r.append("-" * self.text_width)

        sale_date = sale_data.get('created_at', datetime.now())
        if isinstance(sale_date, str):
            sale_date = datetime.fromisoformat(sale_date.replace('Z', '+00:00'))
        r.append(f"Fecha: {sale_date.strftime('%d/%m/%Y %H:%M:%S')}")
        r.append(f"Venta No: {sale_data.get('id','N/A')}")
        if sale_data.get('ncf'): r.append(f"NCF: {sale_data['ncf']}")
        r.append(f"Método: {sale_data.get('payment_method','Efectivo').title()}")
        r.append("-" * self.text_width)
        r.append("Cant  Descripción           Total")
        r.append("-" * self.text_width)

        for item in sale_data.get('items', []):
            qty = item.get('quantity', 1)
            name = item.get('product_name', item.get('name', 'Producto'))[:18]
            total = qty * item.get('price', 0)
            tax_rate = item.get('tax_rate', 0)
            is_tax_included = item.get('is_tax_included', False)
            
            line = f"{qty:<3} {name:<18}{format_currency_rd(total):>8}"
            r.append(line)
            
            # Show tax line for included taxes
            if is_tax_included and tax_rate > 0:
                # Calculate included tax amount per line
                tax_amount = total - (total / (1 + tax_rate))
                tax_percentage = int(tax_rate * 100)
                tax_line = f"   (ITBIS {tax_percentage}%)       {format_currency_rd(tax_amount):>8}"
                r.append(tax_line)

        r.append("-" * self.text_width)
        subtotal = sale_data.get('subtotal', 0)
        # FIX: Don't calculate default ITBIS - use actual tax_amount from sale data
        tax = sale_data.get('tax_amount', 0)  # Use 0 as default instead of calculating
        total = sale_data.get('total', subtotal + tax)

        # Calculate tax rate for display (avoid division by zero)
        tax_rate_display = "Sin impuestos"
        if subtotal > 0 and tax > 0:
            tax_percentage = round((tax / subtotal) * 100)
            tax_rate_display = f"ITBIS ({tax_percentage}%)"

        r.append(f"{'Subtotal:':<20}{format_currency_rd(subtotal):>12}")
        # Only show tax line if there is actual tax (greater than 0.01 to avoid rounding issues)
        if tax > 0.01:
            r.append(f"{tax_rate_display + ':':<20}{format_currency_rd(tax):>12}")
        elif tax == 0:
            r.append(f"{'Sin impuestos':<20}{'':>12}")
        r.append("=" * self.text_width)
        r.append(f"{'TOTAL:':<20}{format_currency_rd(total):>12}")
        r.append("=" * self.text_width)

        if company_info.get('message'): r.append(c(company_info['message']))
        if company_info.get('footer'): r.append(c(company_info['footer']))
        r.append(c("Válido para efectos fiscales - DGII"))
        r.append(c(f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"))
        r.append("=" * self.text_width)
        return "\n".join(r)

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