# Overview

This is a comprehensive Point of Sale (POS) system designed for bars in the Dominican Republic. It supports multi-terminal operations and ensures fiscal compliance with DGII (Dominican Tax Authority) requirements, including NCF (Comprobantes de Crédito Fiscal) management and tax reporting (606/607 formats). The system handles inventory, purchases, and offers multi-device support, optimized for tablets and mobile use, with role-based access for administrators, cashiers, and waiters.

## Recent Changes (Oct 2025)

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

**Pendiente: FASE 2 (Sistema de Tabs), FASE 3 (División de Cuenta), FASE 4 (Simplificar Flujo Meseros)**

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