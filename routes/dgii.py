# DGII Report Routes - Dominican Republic Tax Compliance
from flask import Blueprint, request, jsonify, send_file, current_app
from flask import render_template, session, redirect, url_for, flash
import csv
import io
import tempfile
import os
from datetime import datetime, timedelta
import calendar

from models import db, User, Sale, Purchase, Product, Supplier, NCFSequence

bp = Blueprint('dgii', __name__, url_prefix='/dgii')


def require_admin():
    """Check if user is authenticated and is an admin"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user = User.query.get(session['user_id'])
    if not user or not user.active:
        session.clear()
        return redirect(url_for('auth.login'))
    
    if user.role.value != 'administrador':
        flash('Acceso denegado. Se requieren permisos de administrador.', 'error')
        return redirect(url_for('admin.dashboard'))
    
    return user

# DGII 606 Layout - Compras (Purchases)
# Layout for purchases from suppliers with tax details
DGII_606_HEADERS = [
    'RNC_CEDULA',           # RNC/Cédula del Proveedor
    'TIPO_IDENTIFICACION',  # Tipo de identificación (1=RNC, 2=Cédula)
    'NUMERO_COMPROBANTE_FISCAL',  # NCF del Comprobante
    'NUMERO_COMPROBANTE_MODIFICADO',  # NCF del comprobante que modifica (si aplica)
    'FECHA_COMPROBANTE',    # Fecha del comprobante (YYYYMMDD)
    'FECHA_PAGO',          # Fecha de pago (YYYYMMDD)
    'MONTO_FACTURADO',     # Monto total facturado
    'ITBIS_FACTURADO',     # ITBIS facturado
    'ITBIS_RETENIDO',      # ITBIS retenido por el comprador
    'ITBIS_SUJETO_PROPORCION',  # ITBIS sujeto a proporcionalidad
    'ITBIS_LLEVADO_COSTO',  # ITBIS llevado al costo
    'ITBIS_POR_ADELANTAR',  # ITBIS por adelantar
    'ITBIS_PERCIBIDO_COMPRAS',  # ITBIS percibido en compras
    'TIPO_RETENCION_ISR',   # Tipo de retención ISR
    'MONTO_RETENCION_ISR',  # Monto retención ISR
    'TIPO_ANULACION'        # Tipo de anulación
]

# DGII 607 Layout - Ventas (Sales)  
# Layout for sales to customers with tax details
DGII_607_HEADERS = [
    'RNC_CEDULA',           # RNC/Cédula del Cliente
    'TIPO_IDENTIFICACION',  # Tipo de identificación (1=RNC, 2=Cédula)
    'NUMERO_COMPROBANTE_FISCAL',  # NCF del Comprobante
    'NUMERO_COMPROBANTE_MODIFICADO',  # NCF del comprobante que modifica (si aplica)
    'FECHA_COMPROBANTE',    # Fecha del comprobante (YYYYMMDD)
    'MONTO_FACTURADO',     # Monto total facturado
    'ITBIS_FACTURADO',     # ITBIS facturado
    'ITBIS_RETENIDO',      # ITBIS retenido al vendedor
    'ITBIS_PERCIBIDO',     # ITBIS percibido
    'RETENCION_RENTA',     # Retención de renta
    'ISC',                 # Impuesto Selectivo al Consumo
    'OTROS_IMPUESTOS',     # Otros impuestos/tasas
    'MONTO_PROPINA_LEGAL', # Monto propina legal
    'TIPO_ANULACION'       # Tipo de anulación
]


@bp.route('/')
def reports():
    """DGII Reports dashboard"""
    user = require_admin()
    if not isinstance(user, User):
        return redirect(url_for('auth.login'))
    
    # Get available months for dropdown
    current_date = datetime.now()
    available_months = []
    
    # Last 12 months
    for i in range(12):
        month_date = current_date - timedelta(days=30*i)
        month_info = {
            'year': month_date.year,
            'month': month_date.month,
            'name': calendar.month_name[month_date.month],
            'value': f"{month_date.year}-{month_date.month:02d}"
        }
        available_months.append(month_info)
    
    # Get summary stats for current month
    current_month_start = current_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if current_date.month == 12:
        next_month_start = current_date.replace(year=current_date.year + 1, month=1, day=1)
    else:
        next_month_start = current_date.replace(month=current_date.month + 1, day=1)
    
    # Current month sales count
    sales_count = Sale.query.filter(
        Sale.created_at >= current_month_start,
        Sale.created_at < next_month_start
    ).count()
    
    # Current month purchases count  
    purchases_count = Purchase.query.filter(
        Purchase.created_at >= current_month_start,
        Purchase.created_at < next_month_start
    ).count()
    
    return render_template('dgii/reports.html',
                         available_months=available_months,
                         current_month=current_date.strftime("%B %Y"),
                         sales_count=sales_count,
                         purchases_count=purchases_count)


@bp.route('/export/606', methods=['POST'])
def export_606():
    """Export DGII 606 (Purchases) CSV"""
    user = require_admin()
    if not isinstance(user, User):
        return jsonify({'error': 'No autorizado'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Datos no proporcionados'}), 400
    
    year = data.get('year')
    month = data.get('month')
    
    if not year or not month:
        return jsonify({'error': 'Año y mes son requeridos'}), 400
    
    try:
        year = int(year)
        month = int(month)
        
        # Date range for the month
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        # Get purchases for the period
        purchases = Purchase.query.filter(
            Purchase.created_at >= start_date,
            Purchase.created_at < end_date
        ).join(Supplier).all()
        
        # Generate CSV
        output = io.StringIO()
        writer = csv.writer(output, delimiter='|')
        
        # Write header
        writer.writerow(DGII_606_HEADERS)
        
        # Write purchase records
        for purchase in purchases:
            supplier = purchase.supplier
            
            # Determine identification type
            if supplier.rnc and len(supplier.rnc) == 9:
                tipo_id = '1'  # RNC
                rnc_cedula = supplier.rnc
            elif supplier.rnc and len(supplier.rnc) == 11:
                tipo_id = '2'  # Cédula  
                rnc_cedula = supplier.rnc
            else:
                tipo_id = '1'  # Default to RNC
                rnc_cedula = supplier.rnc or '000000000'
            
            # Format dates as YYYYMMDD
            fecha_comprobante = purchase.created_at.strftime('%Y%m%d')
            fecha_pago = purchase.created_at.strftime('%Y%m%d')  # Assume same date
            
            # Calculate amounts
            monto_facturado = purchase.total_amount
            itbis_facturado = purchase.tax_amount or 0
            
            # Write row
            row = [
                rnc_cedula,                    # RNC_CEDULA
                tipo_id,                       # TIPO_IDENTIFICACION
                purchase.ncf_supplier or '',   # NUMERO_COMPROBANTE_FISCAL
                '',                           # NUMERO_COMPROBANTE_MODIFICADO
                fecha_comprobante,            # FECHA_COMPROBANTE
                fecha_pago,                   # FECHA_PAGO
                f"{monto_facturado:.2f}",     # MONTO_FACTURADO
                f"{itbis_facturado:.2f}",     # ITBIS_FACTURADO
                '0.00',                       # ITBIS_RETENIDO
                '0.00',                       # ITBIS_SUJETO_PROPORCION
                '0.00',                       # ITBIS_LLEVADO_COSTO
                '0.00',                       # ITBIS_POR_ADELANTAR
                '0.00',                       # ITBIS_PERCIBIDO_COMPRAS
                '',                           # TIPO_RETENCION_ISR
                '0.00',                       # MONTO_RETENCION_ISR
                ''                            # TIPO_ANULACION
            ]
            writer.writerow(row)
        
        # Create temporary file
        csv_content = output.getvalue()
        output.close()
        
        # Generate filename
        filename = f"606_{year}_{month:02d}.csv"
        
        # Return file
        return jsonify({
            'success': True,
            'filename': filename,
            'records': len(purchases),
            'csv_data': csv_content,
            'message': f'Reporte 606 generado: {len(purchases)} compras para {calendar.month_name[month]} {year}'
        })
        
    except Exception as e:
        return jsonify({'error': f'Error generando reporte 606: {str(e)}'}), 400


@bp.route('/export/607', methods=['POST'])
def export_607():
    """Export DGII 607 (Sales) CSV"""
    user = require_admin()
    if not isinstance(user, User):
        return jsonify({'error': 'No autorizado'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Datos no proporcionados'}), 400
    
    year = data.get('year')
    month = data.get('month')
    
    if not year or not month:
        return jsonify({'error': 'Año y mes son requeridos'}), 400
    
    try:
        year = int(year)
        month = int(month)
        
        # Date range for the month
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        # Get sales for the period
        sales = Sale.query.filter(
            Sale.created_at >= start_date,
            Sale.created_at < end_date
        ).all()
        
        # Generate CSV
        output = io.StringIO()
        writer = csv.writer(output, delimiter='|')
        
        # Write header
        writer.writerow(DGII_607_HEADERS)
        
        # Write sales records
        for sale in sales:
            # Most sales are to general public (no specific customer)
            rnc_cedula = sale.customer_id or '00000000000'  # Default for general public
            tipo_id = '2'  # Default to Cédula for general public
            
            # Format date as YYYYMMDD
            fecha_comprobante = sale.sale_date.strftime('%Y%m%d')
            
            # Calculate amounts
            monto_facturado = sale.total_amount
            itbis_facturado = sale.tax_amount or 0
            
            # Write row
            row = [
                rnc_cedula,                    # RNC_CEDULA
                tipo_id,                       # TIPO_IDENTIFICACION
                sale.ncf,                      # NUMERO_COMPROBANTE_FISCAL
                '',                            # NUMERO_COMPROBANTE_MODIFICADO
                fecha_comprobante,             # FECHA_COMPROBANTE
                f"{monto_facturado:.2f}",      # MONTO_FACTURADO
                f"{itbis_facturado:.2f}",      # ITBIS_FACTURADO
                '0.00',                        # ITBIS_RETENIDO
                '0.00',                        # ITBIS_PERCIBIDO
                '0.00',                        # RETENCION_RENTA
                '0.00',                        # ISC
                '0.00',                        # OTROS_IMPUESTOS
                '0.00',                        # MONTO_PROPINA_LEGAL
                ''                             # TIPO_ANULACION
            ]
            writer.writerow(row)
        
        # Create CSV content
        csv_content = output.getvalue()
        output.close()
        
        # Generate filename
        filename = f"607_{year}_{month:02d}.csv"
        
        # Return file data
        return jsonify({
            'success': True,
            'filename': filename,
            'records': len(sales),
            'csv_data': csv_content,
            'message': f'Reporte 607 generado: {len(sales)} ventas para {calendar.month_name[month]} {year}'
        })
        
    except Exception as e:
        return jsonify({'error': f'Error generando reporte 607: {str(e)}'}), 400


@bp.route('/preview/606/<int:year>/<int:month>')
def preview_606(year, month):
    """Preview DGII 606 data before export"""
    user = require_admin()
    if not isinstance(user, User):
        return redirect(url_for('auth.login'))
    
    try:
        # Date range for the month
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        # Get purchases for the period
        purchases = Purchase.query.filter(
            Purchase.created_at >= start_date,
            Purchase.created_at < end_date
        ).join(Supplier).all()
        
        return render_template('dgii/preview_606.html',
                             purchases=purchases,
                             year=year,
                             month=month,
                             month_name=calendar.month_name[month])
        
    except Exception as e:
        flash(f'Error cargando vista previa: {str(e)}', 'error')
        return redirect(url_for('dgii.reports'))


@bp.route('/preview/607/<int:year>/<int:month>')
def preview_607(year, month):
    """Preview DGII 607 data before export"""
    user = require_admin()
    if not isinstance(user, User):
        return redirect(url_for('auth.login'))
    
    try:
        # Date range for the month
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        # Get sales for the period
        sales = Sale.query.filter(
            Sale.created_at >= start_date,
            Sale.created_at < end_date
        ).all()
        
        return render_template('dgii/preview_607.html',
                             sales=sales,
                             year=year,
                             month=month,
                             month_name=calendar.month_name[month])
        
    except Exception as e:
        flash(f'Error cargando vista previa: {str(e)}', 'error')
        return redirect(url_for('dgii.reports'))