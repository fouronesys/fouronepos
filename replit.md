# Overview

This multi-terminal Point of Sale (POS) system is designed for bars in the Dominican Republic, focusing on sales, inventory, and purchasing management. A core objective is full fiscal compliance with the DGII (Dominican Tax Authority), including NCF management and 606/607 tax reporting. It supports various user roles and is optimized for multi-device use, especially tablets and mobile devices, aiming to enhance operational efficiency and fiscal transparency.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Frontend
The application uses Flask with Jinja2 templates for server-side rendering and Bootstrap 5 for a responsive, mobile-first UI. It incorporates role-based views and vanilla JavaScript for dynamic features like cart management, real-time stock validation, and interactive elements for tab and bill-splitting functionalities.

## Backend
Developed with Flask, the backend is structured using modular Blueprints for distinct functionalities such as authentication, administration, waiter operations, API, inventory, and DGII compliance. It leverages Flask sessions for user state management, bcrypt for secure password hashing, and SQLAlchemy ORM for database interactions. Key features include real-time stock validation, a flexible tab system for open orders, and comprehensive bill splitting (equal, by item, custom).

## Database
PostgreSQL is the primary database, managed via SQLAlchemy ORM. Critical entities include Users (with role-based access), Sales (tracking transactions, NCFs, customer fiscal info, and split sales), Products (categories, stock, suppliers), Purchases, NCF Sequences, Tax Types, and Tables.

## Authentication & Authorization
The system employs session-based authentication with bcrypt for password hashing. Authorization is role-based, ensuring route-level protection, automatic session management, and secure password policies.

## Fiscal Compliance
A robust fiscal compliance module for the Dominican Republic is integrated, featuring atomic NCF assignment, sequential NCF generation with range validation, tracking of cancelled NCFs, and support for multiple NCF types (consumo, crédito fiscal, gubernamental). It generates official DGII 606/607 CSV reports for purchases and sales and includes RNC validation utilities. Both fiscal and non-fiscal receipts can be generated. The system correctly handles various tax types (ITBIS 18% exclusive/inclusive, 16% reduced, exent) and service charges (Propina 10%) according to Dominican regulations, ensuring accurate tax calculations and product configurations.

### Tax Category System (FASE 1-2)
The system uses a categorization system for tax types with enum `TaxCategory`:
- **TAX**: Fiscal taxes (ITBIS 18%, 16%, Exento) - sum for tax calculation base
- **SERVICE_CHARGE**: Service charges (Propina 10%) - applied after tax calculation
- **OTHER**: Other custom charges

### Business Validation Rules (FASE 3)
Strict validation rules ensure fiscal compliance:
1. **Single ITBIS per Product**: Products can only have ONE tax type of category TAX to prevent incorrect rate summation
2. **No Mixed Tax Modes**: Products cannot mix inclusive and exclusive tax types
3. **Active Tax Types**: Products with active status must have active tax types only
4. All validations are enforced at API level (POST/PUT `/api/products`)

### Fiscal Audit System (FASE 3)
A comprehensive internal audit system monitors fiscal configuration:
- **Real-time Dashboard** (`/fiscal-audit/dashboard`): Visual compliance monitoring for administrators
- **Compliance Scoring**: 0-100 point system identifying configuration issues
- **Issue Detection**: Identifies products without tax, multiple ITBIS, mixed tax modes, and inactive tax types
- **JSON APIs**: `/fiscal-audit/api/summary` and `/fiscal-audit/api/products/issues` for programmatic access
- **ITBIS Distribution**: Analytics showing tax type distribution across inventory

# External Dependencies

- **Flask**: Web application framework.
- **PostgreSQL**: Primary relational database system.
- **bcrypt**: Password hashing library.
- **Bootstrap 5**: Frontend CSS framework for responsive design.
- **Bootstrap Icons**: Icon library for UI elements.
- **DGII Compliance**: Integration with Dominican Republic tax authority regulations for NCF management and 606/607 tax reporting.
- **RNC Validation**: Utility for validating Dominican Republic taxpayer identification numbers.
- **Thermal Printer Support**: Implements ESC/POS protocol for printing receipts on 80mm and 58mm thermal printers.

# Documentation & Training

- **GUIA_TIPOS_IMPUESTOS.md**: Technical guide for tax type configuration and fiscal calculations
- **GUIA_USUARIO_IMPUESTOS.md**: Simplified user training material for end-users and operators (FASE 3)
- **ERRORES_LOGICA_FUNCIONAL.md**: Complete improvement plan documentation (FASE 1-3 completed)
- **tests/test_fiscal_calculations.py**: Comprehensive test suite for fiscal calculations (12 tests, 100% passing)

# Recent Changes (October 2025)

## FASE 3 Optimizations (Completed)
- Implemented strict business validation rules preventing multiple ITBIS per product and mixed tax modes
- Created comprehensive fiscal audit dashboard with compliance scoring and issue detection
- Developed user training material (GUIA_USUARIO_IMPUESTOS.md) for operators
- Fixed critical bugs: division by zero in audit dashboard, multi-ITBIS aggregation
- Registered fiscal_audit blueprint with real-time monitoring APIs
- All changes architect-reviewed and production-ready