# Overview

This is a comprehensive Point of Sale (POS) system designed for bars and restaurants in the Dominican Republic. It supports multi-terminal operations and ensures fiscal compliance with DGII (Dominican Tax Authority) requirements, including NCF (Comprobantes de Crédito Fiscal) management and tax reporting (606/607 formats). The system handles inventory, purchases, and offers multi-device support, optimized for tablets and mobile use, with role-based access for administrators, cashiers, and waiters.

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