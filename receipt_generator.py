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

        # Add customer information for fiscal receipts
        if sale_data.get('customer_name') or sale_data.get('customer_rnc'):
            content.append(Spacer(1, 2*mm))
            content.append(Paragraph("--- INFORMACIÓN DEL CLIENTE ---", self.styles['ReceiptHeader']))
            
            if sale_data.get('customer_name'):
                content.append(Paragraph(f"Cliente: {sale_data['customer_name']}", self.styles['Item']))
            
            if sale_data.get('customer_rnc'):
                rnc_label = "RNC:" if len(sale_data['customer_rnc']) == 9 else "Cédula:"
                content.append(Paragraph(f"{rnc_label} {sale_data['customer_rnc']}", self.styles['Item']))

        return content

    def _build_items_list(self, sale_data: Dict[str, Any]) -> List:
        """Build items list with line-by-line tax display for included taxes using new TaxType system"""
        content = []
        
        content.append(Paragraph("-" * (self.text_width if hasattr(self, 'text_width') else 32), self.styles['Item']))
        
        items = sale_data.get('items', [])
        for item in items:
            qty = item.get("quantity", 1)
            name = item.get("product_name", item.get("name", "Producto"))
            price = item.get("price", 0)
            total = qty * price
            
            # Truncate name based on format
            max_name_len = 20 if self.format_type == '58mm' else 25
            if len(name) > max_name_len:
                name = name[:max_name_len-3] + "..."
            
            # Format item line
            content.append(Paragraph(f"{qty}x {name}", self.styles['Item']))
            content.append(Paragraph(f"    {format_currency_rd(price)} c/u = {format_currency_rd(total)}", self.styles['Item']))
            
            # Show tax calculation for each product (NEW ENHANCED SYSTEM)
            tax_types = item.get('tax_types', [])
            if tax_types:
                for tax_type in tax_types:
                    rate = tax_type.get('rate', 0)
                    if rate > 0:
                        tax_name = tax_type.get('name', 'ITBIS')
                        tax_percentage = int(rate * 100)
                        
                        if tax_type.get('is_inclusive', False):
                            # Inclusive tax - extract from total
                            tax_amount = total - (total / (1 + rate))
                            base_amount = total / (1 + rate)
                            content.append(Paragraph(f"    Base: {format_currency_rd(base_amount)} + {tax_name} {tax_percentage}%: {format_currency_rd(tax_amount)}", self.styles['Item']))
                        else:
                            # Exclusive tax - add to total  
                            tax_amount = total * rate
                            content.append(Paragraph(f"    Subtotal: {format_currency_rd(total)} + {tax_name} {tax_percentage}%: {format_currency_rd(tax_amount)}", self.styles['Item']))
            else:
                # Fallback to legacy system for backward compatibility
                tax_rate = item.get("tax_rate", 0)
                if tax_rate > 0:
                    is_tax_included = item.get("is_tax_included", False)
                    tax_percentage = int(tax_rate * 100)
                    
                    if is_tax_included:
                        # Calculate included tax amount per line
                        tax_amount = total - (total / (1 + tax_rate))
                        base_amount = total / (1 + tax_rate)
                        content.append(Paragraph(f"    Base: {format_currency_rd(base_amount)} + ITBIS {tax_percentage}%: {format_currency_rd(tax_amount)}", self.styles['Item']))
                    else:
                        # Exclusive tax
                        tax_amount = total * tax_rate
                        content.append(Paragraph(f"    Subtotal: {format_currency_rd(total)} + ITBIS {tax_percentage}%: {format_currency_rd(tax_amount)}", self.styles['Item']))
        
        content.append(Paragraph("-" * (self.text_width if hasattr(self, 'text_width') else 32), self.styles['Item']))
        return content

    def _build_totals_section(self, sale_data: Dict[str, Any]) -> List:
        content = []
        subtotal = sale_data.get('subtotal', 0)
        tax = sale_data.get('tax_amount', 0)
        total = sale_data.get('total', subtotal + tax)
        
        # Analyze tax types across all items (NEW SYSTEM)
        items = sale_data.get('items', [])
        inclusive_taxes = {}  # {tax_name: total_amount}
        exclusive_taxes = {}  # {tax_name: total_amount}
        
        # Calculate taxes by type
        for item in items:
            qty = item.get('quantity', 1)
            price = item.get('price', 0)
            item_total = qty * price
            
            tax_types = item.get('tax_types', [])
            if tax_types:
                for tax_type in tax_types:
                    rate = tax_type.get('rate', 0)
                    name = tax_type.get('name', 'ITBIS')
                    
                    if rate > 0:
                        if tax_type.get('is_inclusive', False):
                            # Included tax - extract from price
                            tax_amount = item_total - (item_total / (1 + rate))
                            inclusive_taxes[name] = inclusive_taxes.get(name, 0) + tax_amount
                        else:
                            # Exclusive tax - add to price
                            tax_amount = item_total * rate
                            exclusive_taxes[name] = exclusive_taxes.get(name, 0) + tax_amount
            else:
                # Fallback to legacy system
                tax_rate = item.get('tax_rate', 0)
                is_tax_included = item.get('is_tax_included', False)
                if tax_rate > 0:
                    if is_tax_included:
                        tax_amount = item_total - (item_total / (1 + tax_rate))
                        inclusive_taxes['ITBIS'] = inclusive_taxes.get('ITBIS', 0) + tax_amount
                    else:
                        tax_amount = item_total * tax_rate
                        exclusive_taxes['ITBIS'] = exclusive_taxes.get('ITBIS', 0) + tax_amount
        
        content.append(Paragraph(f"Subtotal: {format_currency_rd(subtotal)}", self.styles['Item']))
        
        # Show inclusive taxes (these don't add to total)
        for tax_name, tax_amount in inclusive_taxes.items():
            if tax_amount > 0.01:
                content.append(Paragraph(f"{tax_name} (incl.): {format_currency_rd(tax_amount)}", self.styles['Item']))
        
        # Show exclusive taxes (these add to total)
        for tax_name, tax_amount in exclusive_taxes.items():
            if tax_amount > 0.01:
                content.append(Paragraph(f"{tax_name}: {format_currency_rd(tax_amount)}", self.styles['Item']))
        
        # Show service charge/propina if applied (NEW)
        service_charge_amount = sale_data.get('service_charge_amount', 0)
        if service_charge_amount > 0.01:
            content.append(Paragraph(f"Propina legal (10%): {format_currency_rd(service_charge_amount)}", self.styles['Item']))
        
        # Show no taxes message if no taxes or service charges found
        if not inclusive_taxes and not exclusive_taxes and service_charge_amount <= 0.01:
            content.append(Paragraph("Sin impuestos", self.styles['Item']))
            
        content.append(Paragraph(f"<b>TOTAL: {format_currency_rd(total)}</b>", self.styles['Total']))
        
        # Show cash received and change for cash payments
        cash_received = sale_data.get('cash_received')
        change_amount = sale_data.get('change_amount')
        if cash_received is not None and change_amount is not None and change_amount > 0:
            content.append(Paragraph(f"Efectivo recibido: {format_currency_rd(cash_received)}", self.styles['Item']))
            content.append(Paragraph(f"<b>Cambio: {format_currency_rd(change_amount)}</b>", self.styles['Total']))
        
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
        
        # Add customer information for fiscal receipts in thermal format
        if sale_data.get('customer_name') or sale_data.get('customer_rnc'):
            r.append("-" * self.text_width)
            r.append(c("INFORMACIÓN DEL CLIENTE"))
            if sale_data.get('customer_name'):
                r.append(f"Cliente: {sale_data['customer_name']}")
            if sale_data.get('customer_rnc'):
                rnc_label = "RNC:" if len(sale_data['customer_rnc']) == 9 else "Cédula:"
                r.append(f"{rnc_label} {sale_data['customer_rnc']}")
        
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
        
        # Show cash received and change for cash payments
        cash_received = sale_data.get('cash_received')
        change_amount = sale_data.get('change_amount')
        if cash_received is not None and change_amount is not None and change_amount > 0:
            r.append(f"{'Efectivo recibido:':<20}{format_currency_rd(cash_received):>12}")
            r.append(f"{'Cambio:':<20}{format_currency_rd(change_amount):>12}")
            
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


def generate_sales_report_pdf(sales: List[Any], period_name: str, start_date: datetime, end_date: datetime) -> str:
    """
    Generate a comprehensive sales report PDF
    
    Args:
        sales: List of Sale objects
        period_name: Name of the period (e.g., "Día 23/10/2025")
        start_date: Start date of the period
        end_date: End date of the period
        
    Returns:
        Path to generated PDF
    """
    import os
    from utils import get_company_info_for_receipt
    
    company_info = get_company_info_for_receipt()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"reporte_ventas_{timestamp}.pdf"
    output_path = os.path.join('static', 'receipts', filename)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    
    content = []
    styles = getSampleStyleSheet()
    
    styles.add(ParagraphStyle(
        name='ReportTitle',
        fontSize=16,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
        spaceAfter=12
    ))
    
    styles.add(ParagraphStyle(
        name='SectionHeader',
        fontSize=12,
        alignment=TA_LEFT,
        fontName='Helvetica-Bold',
        spaceAfter=6,
        spaceBefore=12
    ))
    
    styles.add(ParagraphStyle(
        name='NormalText',
        fontSize=9,
        alignment=TA_LEFT,
        fontName='Helvetica'
    ))
    
    styles.add(ParagraphStyle(
        name='CompanyInfo',
        fontSize=9,
        alignment=TA_CENTER,
        fontName='Helvetica'
    ))
    
    content.append(Paragraph(company_info.get('business_name', 'Four One POS'), styles['ReportTitle']))
    content.append(Paragraph(f"RNC: {company_info.get('rnc', 'N/A')}", styles['CompanyInfo']))
    content.append(Paragraph(f"{company_info.get('address', '')}", styles['CompanyInfo']))
    content.append(Spacer(1, 12))
    
    content.append(Paragraph(f"Reporte de Ventas - {period_name}", styles['ReportTitle']))
    content.append(Paragraph(
        f"Período: {start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}", 
        styles['CompanyInfo']
    ))
    content.append(Paragraph(
        f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", 
        styles['CompanyInfo']
    ))
    content.append(Spacer(1, 20))
    
    total_sales = len(sales)
    total_amount = sum(sale.total for sale in sales)
    total_tax = sum(sale.tax_amount for sale in sales)
    total_subtotal = sum(sale.subtotal for sale in sales)
    
    summary_data = [
        ['Total de Ventas:', str(total_sales)],
        ['Subtotal:', format_currency_rd(total_subtotal)],
        ['Impuestos:', format_currency_rd(total_tax)],
        ['Total:', format_currency_rd(total_amount)],
        ['Promedio por Venta:', format_currency_rd(total_amount / total_sales) if total_sales > 0 else '$0.00']
    ]
    
    summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightblue),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    
    content.append(Paragraph("Resumen General", styles['SectionHeader']))
    content.append(summary_table)
    content.append(Spacer(1, 20))
    
    payment_methods = {}
    for sale in sales:
        method = sale.payment_method or 'Efectivo'
        if method not in payment_methods:
            payment_methods[method] = {'count': 0, 'total': 0}
        payment_methods[method]['count'] += 1
        payment_methods[method]['total'] += sale.total
    
    if payment_methods:
        content.append(Paragraph("Ventas por Método de Pago", styles['SectionHeader']))
        payment_data = [['Método de Pago', 'Cantidad', 'Total']]
        for method, data in payment_methods.items():
            payment_data.append([
                method.capitalize(),
                str(data['count']),
                format_currency_rd(data['total'])
            ])
        
        payment_table = Table(payment_data, colWidths=[2*inch, 1.5*inch, 2*inch])
        payment_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
        ]))
        content.append(payment_table)
        content.append(Spacer(1, 20))
    
    content.append(Paragraph("Detalle de Ventas", styles['SectionHeader']))
    
    sales_data = [['#', 'Fecha/Hora', 'NCF', 'Cliente', 'Subtotal', 'ITBIS', 'Total']]
    
    for idx, sale in enumerate(sales, 1):
        sales_data.append([
            str(idx),
            sale.created_at.strftime('%d/%m/%Y %H:%M'),
            sale.ncf[:13] + '...' if sale.ncf and len(sale.ncf) > 15 else sale.ncf or 'N/A',
            sale.customer_name[:20] + '...' if sale.customer_name and len(sale.customer_name) > 22 else sale.customer_name or 'General',
            format_currency_rd(sale.subtotal),
            format_currency_rd(sale.tax_amount),
            format_currency_rd(sale.total)
        ])
    
    sales_table = Table(sales_data, colWidths=[0.4*inch, 1.3*inch, 1.2*inch, 1.5*inch, 1*inch, 0.9*inch, 1*inch])
    sales_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.beige])
    ]))
    
    content.append(sales_table)
    content.append(Spacer(1, 30))
    
    content.append(Paragraph("_" * 50, styles['NormalText']))
    content.append(Paragraph("Firma Autorizada", styles['NormalText']))
    
    doc.build(content)
    return output_path