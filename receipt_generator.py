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
    Generator for Dominican Republic fiscal receipts
    Compliant with DGII regulations and NCF requirements
    """
    
    def __init__(self):
        """Initialize the receipt generator with default settings"""
        self.page_size = (80 * mm, 200 * mm)  # Standard thermal paper size 80mm
        self.margin = 3 * mm
        self.styles = self._create_styles()
        
    def _create_styles(self):
        """Create custom styles for the receipt"""
        styles = getSampleStyleSheet()
        
        # Company name style
        styles.add(ParagraphStyle(
            name='CompanyName',
            parent=styles['Title'],
            fontSize=12,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            spaceAfter=6,
            spaceBefore=0
        ))
        
        # Company info style
        styles.add(ParagraphStyle(
            name='CompanyInfo',
            parent=styles['Normal'],
            fontSize=8,
            alignment=TA_CENTER,
            fontName='Helvetica',
            spaceAfter=3,
            spaceBefore=0
        ))
        
        # Receipt header style
        styles.add(ParagraphStyle(
            name='ReceiptHeader',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            spaceAfter=6,
            spaceBefore=6
        ))
        
        # Item style for products
        styles.add(ParagraphStyle(
            name='Item',
            parent=styles['Normal'],
            fontSize=8,
            alignment=TA_LEFT,
            fontName='Helvetica',
            spaceAfter=2,
            spaceBefore=0
        ))
        
        # Total style
        styles.add(ParagraphStyle(
            name='Total',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_RIGHT,
            fontName='Helvetica-Bold',
            spaceAfter=3,
            spaceBefore=3
        ))
        
        # Footer style
        styles.add(ParagraphStyle(
            name='Footer',
            parent=styles['Normal'],
            fontSize=7,
            alignment=TA_CENTER,
            fontName='Helvetica',
            spaceAfter=2,
            spaceBefore=2
        ))
        
        return styles
    
    def generate_fiscal_receipt(self, sale_data: Dict[str, Any], output_path: Optional[str] = None) -> str:
        """
        Generate a fiscal receipt PDF for a sale
        
        Args:
            sale_data: Dictionary containing sale information
            output_path: Optional path to save the PDF, if None, saves to default location
            
        Returns:
            Path to the generated PDF file
        """
        
        # Get company information
        company_info = get_company_info_for_receipt()
        
        # Prepare filename and path
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            sale_id = sale_data.get('id', 'unknown')
            filename = f"recibo_fiscal_{sale_id}_{timestamp}.pdf"
            output_path = os.path.join('static', 'receipts', filename)
            
            # Create receipts directory if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Create PDF document
        doc = SimpleDocTemplate(
            output_path,
            pagesize=self.page_size,
            rightMargin=self.margin,
            leftMargin=self.margin,
            topMargin=self.margin,
            bottomMargin=self.margin
        )
        
        # Build the receipt content
        content = []
        
        # Company header
        content.extend(self._build_company_header(company_info))
        
        # Receipt details
        content.extend(self._build_receipt_details(sale_data))
        
        # Items table
        content.extend(self._build_items_table(sale_data))
        
        # Totals section
        content.extend(self._build_totals_section(sale_data))
        
        # Fiscal information
        content.extend(self._build_fiscal_info(sale_data, company_info))
        
        # Footer
        content.extend(self._build_footer(company_info))
        
        # Build the PDF
        doc.build(content)
        
        return output_path
    
    def _build_company_header(self, company_info: Dict[str, str]) -> List:
        """Build the company header section"""
        content = []
        
        # Company logo (if available)
        if company_info.get('logo') and os.path.exists(company_info['logo']):
            try:
                logo = Image(company_info['logo'], width=20*mm, height=15*mm)
                logo.hAlign = 'CENTER'
                content.append(logo)
                content.append(Spacer(1, 3*mm))
            except:
                pass  # Skip logo if there's an error
        
        # Company name
        content.append(Paragraph(company_info['name'], self.styles['CompanyName']))
        
        # Company RNC
        if company_info.get('rnc'):
            content.append(Paragraph(f"RNC: {company_info['rnc']}", self.styles['CompanyInfo']))
        
        # Company address
        if company_info.get('address'):
            content.append(Paragraph(company_info['address'], self.styles['CompanyInfo']))
        
        # Company phone
        if company_info.get('phone'):
            content.append(Paragraph(f"Tel: {company_info['phone']}", self.styles['CompanyInfo']))
        
        # Company email
        if company_info.get('email'):
            content.append(Paragraph(company_info['email'], self.styles['CompanyInfo']))
        
        content.append(Spacer(1, 5*mm))
        
        return content
    
    def _build_receipt_details(self, sale_data: Dict[str, Any]) -> List:
        """Build the receipt details section"""
        content = []
        
        # Receipt title
        content.append(Paragraph("RECIBO FISCAL", self.styles['ReceiptHeader']))
        
        # Sale date and time
        sale_date = sale_data.get('created_at', datetime.now())
        if isinstance(sale_date, str):
            sale_date = datetime.fromisoformat(sale_date.replace('Z', '+00:00'))
        
        date_str = sale_date.strftime("%d/%m/%Y %H:%M:%S")
        content.append(Paragraph(f"Fecha: {date_str}", self.styles['Item']))
        
        # Sale ID
        content.append(Paragraph(f"Venta No: {sale_data.get('id', 'N/A')}", self.styles['Item']))
        
        # NCF (Número de Comprobante Fiscal)
        if sale_data.get('ncf'):
            content.append(Paragraph(f"NCF: {sale_data['ncf']}", self.styles['Item']))
        
        # Payment method
        payment_method = sale_data.get('payment_method', 'efectivo')
        payment_method_es = {
            'efectivo': 'Efectivo',
            'tarjeta': 'Tarjeta',
            'transferencia': 'Transferencia'
        }.get(payment_method, payment_method.title())
        
        content.append(Paragraph(f"Método de pago: {payment_method_es}", self.styles['Item']))
        
        content.append(Spacer(1, 3*mm))
        
        return content
    
    def _build_items_table(self, sale_data: Dict[str, Any]) -> List:
        """Build the items table section"""
        content = []
        
        # Table header
        content.append(Paragraph("ARTÍCULOS", self.styles['ReceiptHeader']))
        
        # Prepare table data
        table_data = [
            ['Cant.', 'Descripción', 'Precio', 'Total']
        ]
        
        items = sale_data.get('items', [])
        for item in items:
            quantity = item.get('quantity', 1)
            name = item.get('product_name', item.get('name', 'Producto'))
            price = item.get('price', 0)
            total = quantity * price
            
            # Truncate long product names
            if len(name) > 20:
                name = name[:17] + "..."
            
            table_data.append([
                str(quantity),
                name,
                format_currency_rd(price),
                format_currency_rd(total)
            ])
        
        # Create table
        table = Table(table_data, colWidths=[10*mm, 30*mm, 15*mm, 15*mm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (1, 1), (1, -1), 'LEFT'),  # Product names left-aligned
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        content.append(table)
        content.append(Spacer(1, 3*mm))
        
        return content
    
    def _build_totals_section(self, sale_data: Dict[str, Any]) -> List:
        """Build the totals section"""
        content = []
        
        # Calculate totals
        subtotal = sale_data.get('subtotal', 0)
        tax_amount = sale_data.get('tax_amount', 0)
        total = sale_data.get('total', subtotal + tax_amount)
        
        # If tax_amount is not provided, calculate ITBIS (18%)
        if not tax_amount and subtotal:
            tax_amount = calculate_itbis(subtotal)
            total = subtotal + tax_amount
        
        # Subtotal
        content.append(Paragraph(f"Subtotal: {format_currency_rd(subtotal)}", self.styles['Item']))
        
        # ITBIS (Dominican tax)
        content.append(Paragraph(f"ITBIS (18%): {format_currency_rd(tax_amount)}", self.styles['Item']))
        
        # Total
        content.append(Paragraph(f"<b>TOTAL: {format_currency_rd(total)}</b>", self.styles['Total']))
        
        content.append(Spacer(1, 3*mm))
        
        return content
    
    def _build_fiscal_info(self, sale_data: Dict[str, Any], company_info: Dict[str, str]) -> List:
        """Build the fiscal information section"""
        content = []
        
        content.append(Paragraph("INFORMACIÓN FISCAL", self.styles['ReceiptHeader']))
        
        # Company RNC
        if company_info.get('rnc'):
            content.append(Paragraph(f"RNC Empresa: {company_info['rnc']}", self.styles['Footer']))
        
        # NCF information
        if sale_data.get('ncf'):
            content.append(Paragraph(f"NCF: {sale_data['ncf']}", self.styles['Footer']))
            
            # NCF type explanation
            ncf = sale_data['ncf']
            if ncf.startswith('B'):
                ncf_type = "Crédito Fiscal"
            elif ncf.startswith('E'):
                ncf_type = "Consumidor Final"
            else:
                ncf_type = "Comprobante Fiscal"
            
            content.append(Paragraph(f"Tipo: {ncf_type}", self.styles['Footer']))
        
        # Date and time of generation
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        content.append(Paragraph(f"Generado: {now}", self.styles['Footer']))
        
        content.append(Spacer(1, 3*mm))
        
        return content
    
    def _build_footer(self, company_info: Dict[str, str]) -> List:
        """Build the footer section"""
        content = []
        
        # Custom message
        if company_info.get('message'):
            content.append(Paragraph(company_info['message'], self.styles['Footer']))
        
        # Footer information
        if company_info.get('footer'):
            content.append(Paragraph(company_info['footer'], self.styles['Footer']))
        
        # Legal disclaimer
        content.append(Spacer(1, 2*mm))
        content.append(Paragraph(
            "Este recibo es válido para efectos fiscales según las regulaciones de la DGII",
            self.styles['Footer']
        ))
        
        return content
    
    def generate_thermal_receipt(self, sale_data: Dict[str, Any]) -> str:
        """
        Generate a thermal printer compatible receipt (plain text)
        For ESC/POS thermal printers
        
        Args:
            sale_data: Dictionary containing sale information
            
        Returns:
            Plain text receipt formatted for thermal printing
        """
        
        company_info = get_company_info_for_receipt()
        receipt_lines = []
        
        # Header
        receipt_lines.append("=" * 40)
        receipt_lines.append(company_info['name'].center(40))
        
        if company_info.get('rnc'):
            receipt_lines.append(f"RNC: {company_info['rnc']}".center(40))
        
        if company_info.get('address'):
            receipt_lines.append(company_info['address'].center(40))
        
        if company_info.get('phone'):
            receipt_lines.append(f"Tel: {company_info['phone']}".center(40))
        
        receipt_lines.append("=" * 40)
        receipt_lines.append("RECIBO FISCAL".center(40))
        receipt_lines.append("=" * 40)
        
        # Sale details
        sale_date = sale_data.get('created_at', datetime.now())
        if isinstance(sale_date, str):
            sale_date = datetime.fromisoformat(sale_date.replace('Z', '+00:00'))
        
        receipt_lines.append(f"Fecha: {sale_date.strftime('%d/%m/%Y %H:%M:%S')}")
        receipt_lines.append(f"Venta No: {sale_data.get('id', 'N/A')}")
        
        if sale_data.get('ncf'):
            receipt_lines.append(f"NCF: {sale_data['ncf']}")
        
        payment_method = sale_data.get('payment_method', 'efectivo')
        payment_method_es = {
            'efectivo': 'Efectivo',
            'tarjeta': 'Tarjeta', 
            'transferencia': 'Transferencia'
        }.get(payment_method, payment_method.title())
        
        receipt_lines.append(f"Método: {payment_method_es}")
        receipt_lines.append("-" * 40)
        
        # Items
        receipt_lines.append("ARTÍCULOS")
        receipt_lines.append("-" * 40)
        
        items = sale_data.get('items', [])
        for item in items:
            quantity = item.get('quantity', 1)
            name = item.get('product_name', item.get('name', 'Producto'))
            price = item.get('price', 0)
            total = quantity * price
            
            # Format item line
            item_line = f"{quantity}x {name[:25]}"
            price_line = f"{format_currency_rd(price)} = {format_currency_rd(total)}"
            
            receipt_lines.append(item_line)
            receipt_lines.append(" " * (40 - len(price_line)) + price_line)
        
        receipt_lines.append("-" * 40)
        
        # Totals
        subtotal = sale_data.get('subtotal', 0)
        tax_amount = sale_data.get('tax_amount', 0)
        total = sale_data.get('total', subtotal + tax_amount)
        
        if not tax_amount and subtotal:
            tax_amount = calculate_itbis(subtotal)
            total = subtotal + tax_amount
        
        subtotal_line = f"Subtotal: {format_currency_rd(subtotal)}"
        tax_line = f"ITBIS (18%): {format_currency_rd(tax_amount)}"
        total_line = f"TOTAL: {format_currency_rd(total)}"
        
        receipt_lines.append(" " * (40 - len(subtotal_line)) + subtotal_line)
        receipt_lines.append(" " * (40 - len(tax_line)) + tax_line)
        receipt_lines.append("=" * 40)
        receipt_lines.append(" " * (40 - len(total_line)) + total_line)
        receipt_lines.append("=" * 40)
        
        # Footer
        if company_info.get('message'):
            receipt_lines.append(company_info['message'].center(40))
        
        if company_info.get('footer'):
            receipt_lines.append(company_info['footer'].center(40))
        
        receipt_lines.append("")
        receipt_lines.append("Válido para efectos fiscales - DGII".center(40))
        receipt_lines.append(f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}".center(40))
        receipt_lines.append("=" * 40)
        
        return "\n".join(receipt_lines)


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