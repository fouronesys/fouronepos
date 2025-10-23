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
A robust fiscal compliance module for the Dominican Republic is integrated, featuring atomic NCF assignment, sequential NCF generation with range validation, tracking of cancelled NCFs, and support for multiple NCF types (consumo, crédito fiscal, gubernamental). It generates official DGII 606/607 CSV reports for purchases and sales and includes RNC validation utilities. Both fiscal and non-fiscal receipts can be generated. The system correctly handles various tax types (ITBIS 18% exclusive/inclusive, 16% reduced, exent) and service charges (Propina 10%) ensuring accurate tax calculations and product configurations.

**Service Charge (Propina) Calculation (Updated Oct 18, 2025):** When "Propina 10% Incluida" is selected, product prices are assumed to ALREADY include the 10% service charge. The system extracts the service charge (10% of original price) to show the subtotal without tip. The ITBIS is calculated on the ORIGINAL price (with service charge included). Formula: `Total = Subtotal (without service charge) + Service Charge + ITBIS (18% of original price)`. Example: Product priced at RD$ 317.80 with propina incluida → Propina 10%: RD$ 31.78, Subtotal (without tip): RD$ 286.02, ITBIS 18%: RD$ 57.20, Total: RD$ 375.00 (286.02 + 31.78 + 57.20).

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

### Fiscal Audit System (FASE 3 + Mejoras Adicionales)
A comprehensive internal audit system with advanced visual analytics monitors fiscal configuration:
- **Real-time Dashboard** (`/fiscal-audit/dashboard`): Visual compliance monitoring for administrators with interactive charts
- **Compliance Scoring**: 0-100 point system identifying configuration issues
- **Automatic Alerts**: Visual alerts when compliance_score < 80 (warning) or < 60 (critical) with specific action items
- **Interactive Charts** (Chart.js v4.4.0):
  - Compliance gauge meter with color-coded status
  - ITBIS distribution doughnut chart
  - Problems analysis pie chart
  - Progress bars for visual configuration status
- **Issue Detection**: Identifies products without tax, multiple ITBIS, mixed tax modes, and inactive tax types
- **JSON APIs**: `/fiscal-audit/api/summary` and `/fiscal-audit/api/products/issues` for programmatic access
- **ITBIS Distribution**: Analytics showing tax type distribution across inventory with visual graphs

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

## Additional Improvements (Completed - Oct 16, 2025)
- **Automatic Alert System**: Visual alerts trigger when compliance_score < 80 with actionable items
- **Visual Analytics Dashboard**: Added 3 interactive charts using Chart.js v4.4.0:
  - Compliance gauge meter with color-coded status (green/blue/yellow/red)
  - ITBIS distribution doughnut chart with percentage tooltips
  - Problems analysis pie chart showing configuration issues
- **Enhanced UX**: Progress bars, color-coded metrics, and responsive chart layout
- **Proactive Monitoring**: System warns administrators before generating DGII reports with low compliance

## Dashboard Enhancements (Completed - Oct 18, 2025)
- **Enhanced Statistics**: Expanded administrative dashboard with comprehensive daily analytics:
  - **Top Product**: Shows best-selling product with quantity sold and revenue generated
  - **Top Category**: Displays most profitable category with sales metrics
  - **Payment Methods**: Breakdown of daily transactions by payment type (cash, card, transfer) with totals
  - **Active Tables**: Real-time count of occupied tables
  - **Smart Stock Alerts**: Improved visualization of low-stock products with category details (max 8 displayed, link to full list)
- **Performance**: All queries optimized with proper filters and aggregations for fast dashboard loading
- **UX Design**: Color-coded cards, icons, and empty state handling for days without sales data
- Architect-reviewed for query efficiency and data model integrity

## Sales Reports System (Completed - Oct 23, 2025)
- **Period-Based Reports**: Complete sales reporting system supporting multiple time periods:
  - **Daily Reports**: Sales for current day
  - **Weekly Reports**: Last 7 days of sales activity
  - **Monthly Reports**: Current month sales data
  - **Yearly Reports**: Full year sales overview
  - **Custom Period**: Flexible date range selection
- **Comprehensive Analytics**:
  - Summary statistics (total sales, subtotal, taxes, average sale)
  - Payment methods breakdown with counts and totals
  - Top 10 products sold with quantities and revenue
  - Daily sales trends for graphical analysis
  - Complete transaction details with items
- **PDF Export**: Professional sales reports with:
  - Company information and RNC
  - Period summary and totals
  - Payment methods table
  - Detailed sales transactions list
  - Formatted for printing and archiving
- **API Endpoints**:
  - `/admin/api/sales-report`: JSON data endpoint for all periods
  - `/admin/api/sales-report/pdf`: PDF download endpoint
- **User Interface**: Interactive reports page with real-time data visualization, filterable tables, and one-click PDF downloads
- **Security**: Role-based access (administrators, managers, cashiers can access their own data)
- **Quick Access**: Added "Reportes de Ventas" button to dashboard quick actions menu for easier navigation
- Architect-reviewed for code quality, security, and performance

## Error Handling Improvements (Completed - Oct 23, 2025)

### Phase 1: Standardized Error Responses ✅
- **Standardized Error Responses**: Created centralized `error_response()` helper function in `utils.py`:
  - Consistent JSON structure with error_type, message, details, timestamp, and contextual metadata
  - Five error categories: validation, business, permission, not_found, server
  - Unique error IDs for tracking and debugging (e.g., ERR_CREATE_SALE_1729701234)
  - Optional user_message field for non-technical, actionable feedback
  - Appropriate HTTP status codes (400, 403, 404, 409, 500)
- **Enhanced API Endpoints**: Updated three critical sales endpoints with improved error handling:
  - `POST /api/sales`: Validates table existence, data types, and database constraints
  - `POST /api/sales/{id}/items`: Comprehensive validation for stock, product availability, sale status, and quantity limits
  - `POST /api/sales/{id}/finalize`: Detailed errors for permissions, empty sales, stock, cash register, NCF sequences
- **Improved Logging**: Replaced generic error messages with structured logging:
  - `logger.warning()` for business validation failures (stock, status, permissions)
  - `logger.error()` for system errors (database, NCF conflicts, missing configuration)
  - `logger.exception()` for unexpected errors with full stack traces
  - Contextual data in logs (user_id, sale_id, product_id, etc.)
- **User-Friendly Messages**: Clear, actionable error messages in Spanish for operators

### Phase 2: Validation Functions from utils.py ✅
- **RNC Validation**: Client RNC validation in sales finalization endpoint with automatic formatting
  - Uses `validate_rnc()` from utils.py
  - Validates Dominican Republic RNC format (9 or 11 digits)
  - Automatic formatting (e.g., 123-45678-9)
  - Clear error messages explaining format requirements
- **Payment Method Validation**: Validates payment method against allowed list ['cash', 'card', 'transfer']
  - Prevents invalid payment methods
  - Clear error messages with valid options
- **Numeric Range Validations**: Refactored all monetary validations using `validate_numeric_range()`:
  - Cash received: RD$ 0 - RD$ 1,000,000
  - Product cost: RD$ 0 - RD$ 1,000,000
  - Product price: RD$ 0 - RD$ 1,000,000
  - Consistent error messages and validation logic
- **Integer Range Validations**: Refactored all quantity validations using `validate_integer_range()`:
  - Sale item quantity: 1-1000 units
  - Product stock: 0-100,000 units
  - Minimum stock: 0-1000 units
  - Prevents unrealistic values and typographical errors
- **Endpoints Updated**:
  - `POST /api/sales/{id}/finalize`: RNC validation, payment method validation, cash_received validation
  - `POST /api/sales/{id}/items`: Quantity validation refactored
  - `POST /api/products`: Cost, price, stock validations refactored
  - `PUT /api/products/{id}`: Cost, price, stock validations refactored
- **Consistency**: All validations now use centralized functions from utils.py for maintainability