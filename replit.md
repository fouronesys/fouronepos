# Overview

This is a comprehensive Point of Sale (POS) system designed for bars in the Dominican Republic. It supports multi-terminal operations and ensures fiscal compliance with DGII (Dominican Tax Authority) requirements, including NCF (Comprobantes de Crédito Fiscal) management and tax reporting (606/607 formats). The system handles inventory, purchases, and offers multi-device support, optimized for tablets and mobile use, with role-based access for administrators, cashiers, and waiters.

## Recent Changes (Oct 2025)

**Preparación para Despliegue en CapRover - COMPLETADA** (Oct 7, 2025)

Sistema completamente preparado y optimizado para despliegue en producción:

*Limpieza de Base de Datos:*
- Base de datos limpiada exitosamente manteniendo solo datos esenciales
- ✅ Preservados: 3 usuarios, 2 cajas registradoras, 5 categorías, 3 productos
- ✅ Eliminados: Ventas, clientes, proveedores, mesas, secuencias NCF, tipos de impuestos, compras, ajustes de stock, sesiones de caja

*Correcciones y Optimizaciones:*
- Solucionado warning de SQLAlchemy en models.py (agregado overlaps="parent_sale")
- Corregido rate limiting excesivo en favicon y service worker (@limiter.exempt)
- Eliminados scripts de prueba temporales (test_atomic_ncf.py, test_ncf_race_condition_fix.py)
- Verificada integridad de todas las relaciones entre modelos

*Configuración de Despliegue:*
- Dockerfile optimizado con gunicorn (4 workers, port 5000)
- captain-definition configurado correctamente para CapRover
- .gitignore y .dockerignore actualizados con patrones completos
- Documentación de despliegue en CAPROVER_DEPLOYMENT.md

*Variables de Entorno Requeridas:*
- DATABASE_URL (PostgreSQL connection string)
- SESSION_SECRET (minimum 32 characters)
- ENVIRONMENT=production

*Sistema Verificado:*
- ✅ Aplicación inicia sin errores ni warnings
- ✅ Todas las rutas funcionan correctamente
- ✅ Base de datos conectada y limpia
- ✅ Rate limiting configurado apropiadamente
- ✅ Listo para despliegue en producción

**FASE 1: Validación de Stock en Tiempo Real - COMPLETADA** (Oct 4, 2025)

Implementación completa de validación de stock en tiempo real según PLAN_MEJORAS_BAR.md:

*Backend:*
- Endpoint GET /api/products/{id}/stock ya existía, retorna estado de disponibilidad con stock_status y is_available
- Endpoint GET /api/products actualizado para incluir product_type y min_stock en respuesta JSON
- Validación de stock en POST /api/sales/{id}/items ya estaba correctamente implementada con locks transaccionales y mensajes de error detallados

*Frontend - Sistema de Badges:*
- **Productos Consumibles**: Badge azul "Disponible" (stock no rastreado, siempre disponible)
- **Productos Inventariables con stock <= 0**: Badge rojo "❌ Agotado" + producto deshabilitado
- **Productos Inventariables con stock <= min_stock**: Badge amarillo "⚠️ Stock: X"
- **Productos Inventariables con stock > min_stock**: Badge verde "✅ Stock: X"

*Archivos Actualizados:*
- routes/api.py: Agregado product_type y min_stock al endpoint /api/products
- templates/admin/pos.html: Lógica de badges actualizada para respetar product_type
- templates/waiter/menu.html: Lógica de badges actualizada para respetar product_type  
- templates/waiter/table_detail.html: Lógica de badges actualizada para respetar product_type

*Beneficios Logrados:*
- Usuarios ven disponibilidad en tiempo real antes de agregar al carrito
- Productos consumibles no se marcan incorrectamente como agotados
- Alertas visuales para productos con poco stock
- Productos agotados se deshabilitan automáticamente evitando errores al pagar

**FASE 2: Sistema de Tabs - COMPLETADA** (Oct 4, 2025)

Implementación completa de sistema de tabs según PLAN_MEJORAS_BAR.md:

*Backend - Migraciones:*
- Agregados campos parent_sale_id (FK a sales) y split_type a tabla Sales
- Nuevos status disponibles: 'tab_open' (tab activo) y 'split_parent' (venta dividida)
- Migración ejecutada: migrate_tabs_and_splits.py

*Backend - Endpoints API:*
- POST /api/tabs/open: Crear nuevo tab para mesa/cliente con validación
- GET /api/tabs/active: Listar todos los tabs abiertos con detalles y totales
- GET /api/tabs/{id}: Obtener detalles específicos de un tab
- POST /api/tabs/{id}/close: Cerrar tab y convertir a venta pendiente para cobro

*Backend - Item Management:*
- POST /api/sales/{id}/items: Actualizado para permitir status 'pending' O 'tab_open'
- DELETE /api/sales/{id}/items/{item_id}: Actualizado para permitir 'pending' O 'tab_open'
- PUT /api/sales/{id}/items/{item_id}/quantity: Actualizado para permitir 'pending' O 'tab_open'
- Tabs reutilizan endpoints existentes de sales (no duplicación)

*Backend - Restricciones:*
- Endpoints de cocina (send-to-kitchen, kitchen-status) restringidos solo a 'pending'
- Tabs NO van a cocina según plan, bypass completo de workflow de preparación
- Finalización de venta solo permite 'pending' (tabs deben cerrarse primero)

*Frontend - Waiter UI:*
- templates/waiter/tables.html: Botón "Abrir Tab" con modal para customer_name
- templates/waiter/table_detail.html: Vista diferenciada para tabs vs órdenes regulares
- Badge visual "Tab Abierto" en azul cuando status='tab_open'
- Botón "Cerrar Tab y Cobrar" convierte tab a pending para que cajero cobre
- Botón "Enviar a Cocina" oculto para tabs (no aplica)

*Archivos Actualizados:*
- models.py: Campos parent_sale_id y split_type agregados
- routes/api.py: Endpoints de tabs, validaciones actualizadas
- routes/waiter.py: Búsqueda actualizada para incluir 'tab_open'
- templates/waiter/tables.html: UI de apertura de tabs
- templates/waiter/table_detail.html: UI de manejo de tabs activos

*Beneficios Logrados:*
- Meseros pueden mantener cuentas abiertas mientras clientes consumen
- Agregar items a tab sin cerrar venta permite flujo natural de bar
- Cierre de tab genera venta pending lista para cajero cobrar y asignar NCF
- Validación de stock funciona igual en tabs y ventas regulares

**FASE 3: Sistema de División de Cuenta - COMPLETADA** (Oct 4, 2025)

Implementación completa de división de cuenta según PLAN_MEJORAS_BAR.md:

*Backend - Endpoint API:*
- POST /api/sales/{sale_id}/split: Endpoint principal de división de cuenta
- Tres modos de división implementados:
  - **equal**: División equitativa entre N personas con distribución proporcional
  - **by_items**: División asignando items específicos a cada persona
  - **custom**: División personalizada por porcentaje o monto fijo

*Backend - Lógica de División:*
- Funciones helper: _split_equal, _split_by_items, _split_custom
- Creación de ventas hijas vinculadas vía parent_sale_id
- Cálculo proporcional de subtotales e impuestos con manejo de redondeo
- Validaciones completas: evita doble división, valida totales, verifica asignaciones
- Manejo de errores con rollback automático

*Backend - Validaciones:*
- Prevención de división de ventas ya divididas (split_parent status)
- Verificación de ventas vacías sin items
- Validación de suma de porcentajes/montos según tipo de división
- Validación de items asignados en división by_items

*Frontend - UI de División:*
- Modal interactivo en templates/waiter/table_detail.html
- Selector de tipo de división con formularios dinámicos
- División Equitativa: Input para número de personas
- División por Items: Selector múltiple de items con asignación por persona
- División Personalizada: Opciones de porcentaje o monto fijo por persona
- Preview de divisiones con totales calculados
- Validaciones del lado del cliente
- Integración completa con API endpoint

*Archivos Actualizados:*
- routes/api.py: Endpoint /split y funciones helper con asignación de atributos
- templates/waiter/table_detail.html: Modal de división con JavaScript interactivo
- models.py: Uso de campos parent_sale_id y split_type existentes
- PLAN_MEJORAS_BAR.md: Documentación de Fase 3 actualizada

*Beneficios Logrados:*
- Meseros pueden dividir cuentas de forma flexible según necesidad del cliente
- División equitativa automática con manejo de redondeo
- División por items permite asignación precisa de consumos individuales
- División personalizada soporta casos especiales (uno paga más, etc.)
- Cada división genera venta independiente lista para cobro y NCF
- Validaciones previenen errores y garantizan consistencia de totales

**FASE 4: Simplificación de Flujo Meseros - COMPLETADA** (Oct 4, 2025)

Implementación completa de simplificación de flujo según PLAN_MEJORAS_BAR.md:

*Eliminación de Workflow de Cocina:*
- Removido botón "Enviar a Cocina" de template de meseros
- Eliminada función JavaScript sendToKitchen() 
- Endpoints de cocina marcados como DEPRECATED en routes/api.py:
  - /sales/{id}/kitchen-status (PUT)
  - /sales/{id}/send-to-kitchen (POST)

*Actualización de Templates:*
- templates/waiter/table_detail.html: Botón y función de cocina eliminados
- templates/admin/pos.html: Funciones de estado actualizadas para mostrar estados relevantes:
  - 'pending' → Badge amarillo "Pendiente"
  - 'tab_open' → Badge azul "Tab Abierto"
  - 'completed' → Badge verde "Completado"
  - 'cancelled' → Badge gris "Cancelado"

*Flujo Simplificado:*
- Mesero crea pedido → Agrega items → Cierra mesa
- Cajero recibe pedido → Cobra → Asigna NCF → Finaliza
- Sin pasos intermedios de cocina innecesarios
- Flujo directo optimizado para operación de bar

*Archivos Actualizados:*
- templates/waiter/table_detail.html: Referencias a cocina eliminadas
- templates/admin/pos.html: Estados de cocina reemplazados por estados de bar
- routes/api.py: Endpoints de cocina marcados como deprecados
- PLAN_MEJORAS_BAR.md: Documentación de Fase 4 actualizada

*Beneficios Logrados:*
- Flujo más rápido y directo para meseros
- Menos clics y pasos innecesarios
- UI más limpia sin referencias a cocina
- Código más mantenible con endpoints deprecados claramente marcados
- Experiencia optimizada para operación de bar

**TODAS LAS FASES COMPLETADAS ✅**

**Corrección de Generación de Recibos para Ventas Sin Comprobante** (Oct 7, 2025)

*Problema Identificado:*
- Los endpoints de recibos (view, PDF, thermal) rechazaban ventas sin NCF asignado
- Error: "Esta venta no tiene NCF válido para generar recibo fiscal"
- Impedía generar recibos para ventas con "Sin comprobante" (que correctamente NO tienen NCF)

*Solución Implementada:*
- Eliminada validación `if not sale.ncf` en 3 endpoints de recibos
- Agregado comentario explicativo sobre NCF opcional para "sin_comprobante"
- Los recibos ahora se generan correctamente incluso sin NCF

*Cumplimiento Fiscal Mantenido:*
- finalize_sale sigue garantizando NCF obligatorio para tipos fiscales (crédito, gubernamental)
- Solo ventas "sin_comprobante" completadas pueden carecer de NCF
- Plantillas de recibos ya manejaban correctamente ncf=None

*Archivos Actualizados:*
- routes/api.py: Validación corregida en endpoints de recibos (líneas 1267-1271, 1314-1318, 1364-1368)

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Frontend Architecture
The application uses a server-side rendered architecture with Flask and Jinja2 templating, leveraging Bootstrap 5 for a responsive, mobile-first UI. It features role-based views and uses vanilla JavaScript for dynamic functionalities like cart management and real-time updates.

## Backend Architecture
Built with Flask, the backend employs a modular Blueprint structure for organizing routes (auth, admin, waiter, API, inventory, DGII compliance). It uses Flask sessions for management, bcrypt for password security, and SQLAlchemy ORM for business logic and database interactions.

## Database Design
PostgreSQL is the primary database, managed via SQLAlchemy ORM. Key entities include Users (with role-based access), Sales (tracking transactions, NCF assignments, and customer fiscal info), Products (with categories, stock, and suppliers), Purchases, NCF Sequences, and Tables.

## Authentication & Authorization
The system uses a session-based login with bcrypt for password hashing. Authorization is role-based, with route-level protection, automatic logout, and secure password requirements.

## Fiscal Compliance System
Includes atomic NCF assignment, sequential NCF generation with range validation, tracking of cancelled NCFs, and support for multiple NCF types (consumo, crédito fiscal, gubernamental). It also generates official DGII 606/607 CSV reports for purchases and sales, incorporating RNC validation utilities.

# External Dependencies

## Core Framework Dependencies
- **Flask**: Web application framework
- **PostgreSQL**: Primary database system
- **bcrypt**: Password hashing and security
- **Bootstrap 5**: Frontend CSS framework
- **Bootstrap Icons**: Icon library

## Development & Production Tools
- **Render Platform**: Deployment target
- **Environment Variables**: For security (SESSION_SECRET) and database connection (DATABASE_URL)
- **Migration Scripts**: Custom Python scripts for database schema updates.

## Business Integrations
- **DGII Compliance**: Dominican Republic tax authority reporting
- **RNC Validation**: Dominican Republic taxpayer identification validation
- **Thermal Printer Support**: ESC/POS protocol for receipt printing (80mm and 58mm).