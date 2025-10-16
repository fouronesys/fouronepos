# Overview

This is a comprehensive multi-terminal Point of Sale (POS) system designed for bars in the Dominican Republic. Its primary purpose is to manage sales, inventory, and purchases while ensuring full fiscal compliance with the DGII (Dominican Tax Authority), including NCF management and 606/607 tax reporting. The system supports various user roles (administrators, cashiers, waiters) and is optimized for multi-device use, particularly tablets and mobile devices.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Frontend Architecture
The application utilizes a server-side rendered approach with Flask and Jinja2 templates, employing Bootstrap 5 for a responsive, mobile-first user interface. It features role-based views and uses vanilla JavaScript for dynamic functionalities such as cart management, real-time stock validation, and interactive UI elements for tab management and bill splitting.

## Backend Architecture
Built with Flask, the backend is organized using a modular Blueprint structure for different functionalities (authentication, administration, waiter operations, API, inventory, DGII compliance). It uses Flask sessions for managing user states, bcrypt for secure password hashing, and SQLAlchemy ORM for database interactions and business logic. Core features include real-time stock validation, a flexible tab system for open orders, and comprehensive bill splitting capabilities (equal, by item, custom).

## Database Design
PostgreSQL serves as the primary database, managed through SQLAlchemy ORM. Key entities include Users (with role-based access), Sales (tracking transactions, NCF assignments, customer fiscal information, and supporting split sales/tabs), Products (managing categories, stock levels, and suppliers), Purchases, NCF Sequences, Tax Types, and Tables.

## Authentication & Authorization
The system implements session-based authentication with bcrypt for password hashing. Authorization is role-based, ensuring route-level protection, automatic session management, and secure password policies.

## Fiscal Compliance System
The system integrates a robust fiscal compliance module for the Dominican Republic. This includes atomic NCF assignment, sequential NCF generation with range validation, tracking of cancelled NCFs, and support for multiple NCF types (consumo, crédito fiscal, gubernamental). It generates official DGII 606/607 CSV reports for purchases and sales and incorporates RNC validation utilities. Receipts can be generated for both fiscal and non-fiscal sales.

# External Dependencies

## Core Framework Dependencies
- **Flask**: Web application framework
- **PostgreSQL**: Primary relational database system
- **bcrypt**: Password hashing library
- **Bootstrap 5**: Frontend CSS framework for responsive design
- **Bootstrap Icons**: Icon library for UI elements

## Business Integrations
- **DGII Compliance**: Integration with Dominican Republic tax authority regulations for NCF management and tax reporting (606/607 formats).
- **RNC Validation**: Utility for validating Dominican Republic taxpayer identification numbers.
- **Thermal Printer Support**: Implements ESC/POS protocol for printing receipts on 80mm and 58mm thermal printers.

# Recent Updates

## Mejoras al Sistema POS y Análisis de Lógica Funcional (Oct 16, 2025)

### Tax Types Configurados
- **ITBIS 18%** - Tasa estándar exclusiva (se agrega al precio)
- **ITBIS 16%** - Tasa reducida para lácteos, café, azúcares, cacao
- **ITBIS 18% Incluído** - Nuevo: Impuesto ya incluido en precio (cálculo regresivo: Precio/1.18)
- **ITBIS Exento** - Productos exentos (0%)
- **Propina 10%** - Según normativa dominicana
- **Sin Impuesto** - Para productos sin impuestos

### Mejoras POS Implementadas
1. **Tipo de Comprobante por Defecto:** "Consumo" seleccionado automáticamente
2. **Propina 10%:** Activada por defecto (cumplimiento normativa)
3. **Mensajes de Error NCF:** Mejorados con nombres legibles y tipos disponibles
4. **Cálculo ITBIS Incluído:** Soporta desglose automático en recibos

### Análisis de Lógica Funcional
**Documento Creado:** `ERRORES_LOGICA_FUNCIONAL.md`

**Problemas Críticos Identificados:**
- Suma incorrecta de múltiples tax types (necesita separar impuestos de cargos)
- Mezcla de impuestos inclusivos/exclusivos en mismo producto
- Productos sin tax types usan fallback que puede ser incorrecto
- Propina manejada en dos sistemas paralelos (requiere unificación)

**Recomendaciones Clave:**
- Validar que productos DEBEN tener tax type (no permitir guardar sin)
- Separar arquitectura: Impuestos (ITBIS) vs Cargos (Propina)
- Crear tests unitarios para cálculos fiscales
- Auditar productos existentes sin tax types

### Archivos Modificados
- `templates/admin/pos.html` - Defaults optimizados
- `routes/api.py` - Mensajes de error mejorados
- `tax_types` tabla - Nuevo ITBIS 18% Incluído (id=13)