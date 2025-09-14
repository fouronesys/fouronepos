# Overview

This is a comprehensive Point of Sale (POS) system designed specifically for bars and restaurants in the Dominican Republic. The system handles multi-terminal operations with fiscal compliance according to DGII (Dominican Tax Authority) requirements, including NCF (Comprobantes de Crédito Fiscal) management and tax reporting.

The application supports three user roles:
- **Administrators**: Full system access including reports, inventory, and configuration
- **Cashiers**: POS operations, sales processing, and basic reporting
- **Waiters**: Table management, order taking, and kitchen communication

Key features include fiscal compliance with NCF sequences, inventory management with low stock alerts, purchase tracking with supplier management, DGII tax report generation (606/607 formats), and multi-device support optimized for tablets and mobile interfaces.

# Recent Changes

**September 14, 2025**: Enhanced POS Customer Selection and Fixed Template Errors
- **CUSTOMER DROPDOWN ENHANCEMENT**: Added comprehensive customer selection functionality to POS system
  - Created `/api/customers` endpoint to provide customer data with proper authentication and filtering for active customers
  - Added customer dropdown selector in POS client information section with "Seleccione un cliente o ingrese manualmente" option
  - Implemented JavaScript auto-population functionality that fills name and RNC/Cédula fields when customer is selected from dropdown
  - Integrated customer loading during POS initialization alongside tables and other system components
  - Enhanced user experience by allowing both dropdown selection and manual entry for customer information
  - Maintained all existing customer data capture and fiscal compliance functionality
- **TEMPLATE BUG FIX**: Resolved ValueError that prevented access to customer and supplier modules
  - Fixed "invalid literal for int() with base 10: 'PLACEHOLDER'" error in templates/admin/customers.html and templates/admin/suppliers.html
  - Replaced problematic url_for calls with "PLACEHOLDER" parameters with dynamic URL construction using base endpoint paths
  - Changed from `url_for("admin.edit_customer", customer_id="PLACEHOLDER").replace('PLACEHOLDER', id)` to `url_for("admin.customers") + '/' + id + '/edit'`
  - Applied same fix to both edit and delete functions in customer and supplier templates
  - Templates now render correctly without server-side errors, allowing proper access to administrative functions
  - Maintained CSRF protection and security while eliminating template rendering failures

**September 13, 2025**: Enhanced Payment System and Cash Management
- **COMPREHENSIVE PAYMENT SYSTEM**: Implemented complete payment method handling with cash, card, and transfer options
  - Added cash payment processing with automatic change calculation in POS and table billing interfaces  
  - Enhanced payment method selection with visual indicators and validation
  - Implemented cash received input fields and change amount tracking for accurate cash handling
  - Updated backend API endpoints to process and store detailed cash payment information
  - Added cash_received and change_amount columns to sales table for complete transaction tracking
- **ADVANCED CASH MANAGEMENT**: Created comprehensive cash register management system
  - Added payment method configuration modal in dashboard quick actions with enable/disable options
  - Implemented cash register opening and closing functionality with amount tracking and notes
  - Created cash management modal with opening/closing procedures and validation
  - Added cash summary dashboard with real-time totals by payment method (cash, card, transfers)
  - Enhanced role-based billing access to include managers alongside admins and cashiers for improved workflow
- **BACKEND ENHANCEMENTS**: Strengthened data handling and API capabilities
  - Created /api/sales/cash-summary endpoint for daily payment method breakdowns
  - Updated finalize_sale and table-finalize endpoints to handle cash payment details
  - Improved payment method storage with consistent "cash" terminology replacing "efectivo"
  - Enhanced error handling and validation for cash transactions and change calculations
- **UI/UX IMPROVEMENTS**: Enhanced user experience for payment processing
  - Added comprehensive payment configuration interface with individual method toggles
  - Implemented cash register status tracking with visual feedback and action buttons
  - Enhanced quick actions menu with payment configuration and cash management options
  - Added real-time cash summary display with breakdown by payment method and daily totals

**September 12, 2025**: Complete UI modernization and enhanced fiscal compliance
- **MAJOR UI OVERHAUL**: Implemented comprehensive design modernization with new enhanced-design.css system
  - Created modern design tokens system with CSS variables for colors, spacing, shadows, and animations
  - Implemented glass morphism effects with backdrop-filter and modern gradient accents
  - Added responsive design improvements with mobile-first approach and touch optimization
- **Dashboard Modernization**: Completely redesigned administrative dashboard
  - Modern statistics cards with enhanced visual hierarchy and hover effects
  - Improved header with quick action buttons and better information architecture
  - Added enhanced activity feed with timeline design and quick navigation sidebar
  - Implemented modern button styles with gradient backgrounds and micro-interactions
- **POS Interface Enhancement**: Modernized point of sale system
  - New modern cart design with glass morphism effects and improved user flow
  - Enhanced category navigation with pill-style buttons and smooth transitions
  - Improved product grid with better spacing and visual feedback
  - Added modern status indicators and quick stats display
- **Accessibility & Performance**: Added comprehensive accessibility and performance improvements
  - Implemented prefers-reduced-motion and prefers-reduced-transparency support
  - Added performance optimizations for mobile devices and low-end hardware
  - Enhanced theme system with better toggling and initialization
  - Added proper ARIA support and screen reader compatibility
- **Previous improvements maintained**: All fiscal compliance features, table assignment, and customer data capture remain fully functional
- Fixed CSS cache issues preventing dark mode display by implementing cache-busting parameters and no-cache headers
- Added customer RNC/Cédula capture fields for fiscal and governmental receipts with dynamic form validation 
- Implemented table assignment functionality allowing orders to be assigned to tables without immediate payment processing
- Added customer_name and customer_rnc columns to sales table for enhanced Dominican fiscal compliance
- Created favicon to eliminate 404 errors and improve user experience
- Enhanced error handling for cleaner operation and better debugging

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Frontend Architecture
The application uses a server-side rendered architecture with Flask templating:
- **Template Engine**: Jinja2 with Bootstrap 5 for responsive UI design
- **Mobile-First Design**: Optimized for tablets and touch interfaces with large buttons and intuitive navigation
- **Role-Based Views**: Separate template directories for admin, waiter, and auth interfaces
- **JavaScript Integration**: Vanilla JavaScript for dynamic functionality like cart management and real-time updates

## Backend Architecture
**Framework**: Flask with modular Blueprint structure for route organization
- **Route Organization**: Separate blueprints for auth, admin, waiter, API, inventory, and DGII compliance
- **Session Management**: Flask sessions with secure secret key configuration
- **Password Security**: bcrypt for password hashing and authentication
- **Business Logic**: Centralized in models with SQLAlchemy ORM

## Database Design
**Primary Database**: PostgreSQL with SQLAlchemy ORM
- **User Management**: Role-based access control with enum-defined user roles
- **Sales System**: Complete transaction tracking with NCF assignment, status management, and customer fiscal information (RNC/Cédula) for compliance
- **Inventory**: Product management with categories, stock tracking, and supplier relationships
- **Fiscal Compliance**: NCF sequences, cancelled NCF tracking, and audit trail maintenance

Key entities include Users, Sales, Products, Categories, Suppliers, Purchases, NCF Sequences, and Tables for restaurant operations.

## Authentication & Authorization
**Authentication**: Session-based login system with bcrypt password hashing
**Authorization**: Role-based access control with three distinct user types:
- Route-level protection with role verification decorators
- Session management with automatic logout functionality
- Secure password requirements and user activity tracking

## Fiscal Compliance System
**NCF Management**: Atomic NCF assignment to prevent race conditions and ensure DGII compliance
- Sequential NCF generation with range validation
- Cancelled NCF tracking for audit purposes
- Multiple NCF types (consumo, crédito fiscal, gubernamental)

**Tax Reporting**: DGII report generation in official 606/607 CSV formats
- Purchase reports (606) with supplier tax details
- Sales reports (607) with customer tax information
- RNC validation utilities for Dominican Republic tax identification

# External Dependencies

## Core Framework Dependencies
- **Flask**: Web application framework with SQLAlchemy integration
- **PostgreSQL**: Primary database system (configured via DATABASE_URL environment variable)
- **bcrypt**: Password hashing and security
- **Bootstrap 5**: Frontend CSS framework with responsive design
- **Bootstrap Icons**: Icon library for UI elements

## Development & Production Tools
- **Render Platform**: Deployment target with specific configuration files
- **Environment Variables**: SESSION_SECRET for security, DATABASE_URL for database connection
- **Migration Scripts**: Custom Python scripts for database schema updates and data migrations

## Business Integrations
- **DGII Compliance**: Dominican Republic tax authority reporting requirements
- **RNC Validation**: Dominican Republic taxpayer identification validation
- **Thermal Printer Support**: ESC/POS protocol compatibility for receipt printing (80mm and 58mm formats)

The system is designed to be lightweight and production-ready for deployment on Render platform with minimal resource requirements while maintaining full fiscal compliance for Dominican Republic business operations.