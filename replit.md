# Overview

This project is a multi-terminal Point of Sale (POS) system designed for bars in the Dominican Republic. Its primary purpose is to manage sales, inventory, and purchasing, with a strong focus on achieving full fiscal compliance with the DGII (Dominican Tax Authority), including NCF management and 606/607 tax reporting. The system supports various user roles, is optimized for multi-device use (especially tablets and mobile devices), and aims to significantly enhance operational efficiency and fiscal transparency for businesses.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## UI/UX
The application utilizes Flask with Jinja2 for server-side rendered templates and Bootstrap 5 for a responsive, mobile-first design. It incorporates role-based views and vanilla JavaScript for dynamic features such as cart management, real-time stock validation, and interactive elements for tab and bill-splitting functionalities. The system also includes an internal audit system with advanced visual analytics for fiscal configuration, featuring an interactive dashboard with compliance scoring, automatic alerts, and various Chart.js graphs (gauge, doughnut, pie charts, progress bars) for monitoring ITBIS distribution and identifying issues. Enhanced administrative dashboards provide comprehensive daily analytics including top products, top categories, payment method breakdowns, active tables, and smart low-stock alerts. 

**Reporting Module**: The system features a comprehensive reports module with period-based analytics. Sales reports include daily, weekly, monthly, yearly, and custom date range analysis with summaries, payment breakdowns, top 10 products, daily trends, and PDF export functionality. **Products Report** (FASE 1 completed Nov 2025) provides advanced analytics for best-selling products including: rankings by quantity sold and revenue generated, profit margin calculations, category-level statistics, interactive Chart.js visualizations (bar charts for top products, doughnut chart for category distribution), tabbed interface for multiple views, and professional PDF export with detailed product performance metrics. All reports respect role-based permissions (Admin/Manager/Cashier) and support multiple time periods.

Frontend error handling is robust, with a reusable `ErrorDisplay` component supporting various error types, contextual suggestions, and progress indicators for user feedback. The POS payment modal includes a visual NCF type selector allowing users to choose between Consumo, Crédito Fiscal, and Sin Comprobante, with contextual validation requiring customer name and RNC for Crédito Fiscal. High-risk operations (clearing cart, sales >RD$100,000) require user confirmation with detailed dialogs.

## Technical Implementation
The backend is built with Flask, organized into modular Blueprints for authentication, administration, waiter operations, API, inventory, and DGII compliance. It uses Flask sessions for user state, bcrypt for secure password hashing, and SQLAlchemy ORM for database interactions. Key features include real-time stock validation, a flexible tab system for open orders, and comprehensive bill splitting options.
Fiscal compliance for the Dominican Republic is a core module, featuring atomic NCF assignment, sequential NCF generation with range validation, tracking of cancelled NCFs, and support for multiple NCF types (consumo, credito_fiscal, gubernamental, sin_comprobante). It generates official DGII 606/607 CSV reports and includes RNC validation utilities. NCF type selection is integrated into the POS payment flow with backend validation enforcing DGII Norma 06-2018: Crédito Fiscal NCFs require both customer name and RNC to be provided. The system accurately handles various tax types (ITBIS 18% exclusive/inclusive, 16% reduced, exent) and service charges (Propina 10%) with precise calculation rules. Strict validation rules enforce a single tax type of category TAX per product, disallow mixed inclusive/exclusive tax modes, and ensure active tax types for active products. Error handling is standardized with a centralized `error_response()` helper returning structured JSON with unique error IDs (8-character UUIDs), error types (validation, business, permission, not_found, server), timestamps, and contextual details. Structured logging captures all errors and critical operations with complete context (user, operation, data) in rotating log files (`logs/pos_app.log`, `logs/pos_errors.log`). Validation functions for RNC, payment methods, numeric ranges, and integer ranges are centralized in `utils.py` and applied across API endpoints. The system includes comprehensive limit validations (1-1000 units per item, max 100 cart items, RD$0-1M cash received) and high-risk operation confirmations. Comprehensive documentation includes error code catalog, troubleshooting guides for users, and complete API documentation with examples. Testing coverage includes 82 unit tests for validation functions (52% code coverage in utils.py), comprehensive endpoint error testing, and 8 end-to-end integration tests covering complete sale flows (cash/card payments, multiple products, NCF assignment, stock validation, total calculations).

## Database
PostgreSQL is used as the primary database, managed through SQLAlchemy ORM. Key entities include Users (with role-based access), Sales (tracking transactions, NCFs, customer fiscal info, split sales), Products (categories, stock, suppliers), Purchases, NCF Sequences, Tax Types, and Tables.

# External Dependencies

-   **Flask**: Web application framework.
-   **PostgreSQL**: Primary relational database system.
-   **bcrypt**: Password hashing library.
-   **Bootstrap 5**: Frontend CSS framework for responsive design.
-   **Bootstrap Icons**: Icon library for UI elements.
-   **Chart.js v4.4.0**: JavaScript charting library for data visualization in dashboards.
-   **DGII Compliance**: Integration with Dominican Republic tax authority regulations for NCF management and 606/607 tax reporting.
-   **RNC Validation**: Utility for validating Dominican Republic taxpayer identification numbers.
-   **Thermal Printer Support**: Implements ESC/POS protocol for printing receipts on 80mm and 58mm thermal printers.