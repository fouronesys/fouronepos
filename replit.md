# Overview

This is a comprehensive Point of Sale (POS) system designed specifically for bars and restaurants in the Dominican Republic. The system handles multi-terminal operations with fiscal compliance according to DGII (Dominican Tax Authority) requirements, including NCF (Comprobantes de Crédito Fiscal) management and tax reporting.

The application supports three user roles:
- **Administrators**: Full system access including reports, inventory, and configuration
- **Cashiers**: POS operations, sales processing, and basic reporting
- **Waiters**: Table management, order taking, and kitchen communication

Key features include fiscal compliance with NCF sequences, inventory management with low stock alerts, purchase tracking with supplier management, DGII tax report generation (606/607 formats), and multi-device support optimized for tablets and mobile interfaces.

# Recent Changes

**September 12, 2025**: Enhanced fiscal compliance and UI improvements
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