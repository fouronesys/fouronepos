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

# External Dependencies

- **Flask**: Web application framework.
- **PostgreSQL**: Primary relational database system.
- **bcrypt**: Password hashing library.
- **Bootstrap 5**: Frontend CSS framework for responsive design.
- **Bootstrap Icons**: Icon library for UI elements.
- **DGII Compliance**: Integration with Dominican Republic tax authority regulations for NCF management and 606/607 tax reporting.
- **RNC Validation**: Utility for validating Dominican Republic taxpayer identification numbers.
- **Thermal Printer Support**: Implements ESC/POS protocol for printing receipts on 80mm and 58mm thermal printers.