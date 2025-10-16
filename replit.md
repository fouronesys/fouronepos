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

### ✅ FASE 1 COMPLETADA (16 Oct 2025) - Correcciones Críticas Fiscales

#### 1. Separación de Impuestos y Cargos por Servicio
- **Nuevo campo:** `tax_category` agregado a `TaxType` (valores: `tax`, `service_charge`, `other`)
- **Categorización:** ITBIS = `tax`, Propina = `service_charge`
- **Lógica corregida:** Solo se suman tax_types de categoría `tax` en cálculos de impuestos
- **Archivos:** `models.py`, `routes/api.py` (líneas 354-384)

#### 2. Cálculo de Propina Corregido (Normativa Dominicana)
- **ANTES:** Propina calculada sobre subtotal ❌
- **AHORA:** Propina calculada sobre (subtotal + impuestos) ✅
- **Ejemplo:** Subtotal RD$300 + ITBIS RD$54 = Base RD$354 → Propina RD$35.40
- **Archivo:** `templates/admin/pos.html` (líneas 804-824)

#### 3. Validación Obligatoria de Tax Types en Productos
- **Frontend:** Validación que impide guardar productos sin tax_type
- **Backend:** Endpoints POST/PUT retornan error 400 si no hay tax_type_ids
- **Mensaje:** "Debe seleccionar al menos un tipo de impuesto. Esto es obligatorio para el cumplimiento fiscal."
- **Archivos:** `templates/inventory/products.html`, `routes/inventory.py`

#### Impacto
- ✅ Cálculos fiscales correctos (suma solo impuestos, no cargos)
- ✅ Propina cumple normativa dominicana
- ✅ Todos los productos nuevos tienen tax_type obligatorio

#### Archivos Modificados (Fase 1)
- `models.py` - Nuevo enum TaxCategory y campo tax_category en TaxType
- `templates/admin/pos.html` - Defaults optimizados y cálculo de propina corregido
- `templates/inventory/products.html` - Validación obligatoria de tax types
- `routes/api.py` - Mensajes de error mejorados y filtrado de tax_category
- `routes/inventory.py` - Validación backend de tax types
- `tax_types` tabla - Campo tax_category agregado, Propina categorizada como service_charge

---

### ✅ FASE 2 COMPLETADA (16 Oct 2025) - Testing y Mejoras de UX

#### 1. Auditoría y Corrección de Productos sin Tax Types
- **Productos corregidos:** Agua y Pechurinas (asignado ITBIS 18%)
- **Fix técnico:** Corrección del enum TaxCategory a mayúsculas (TAX, SERVICE_CHARGE, OTHER)
- **Resultado:** 100% de productos con tax_types asignados correctamente

#### 2. Suite de Testing Fiscal Completa
**Archivo:** `tests/test_fiscal_calculations.py` (12 tests unitarios)
- Cálculos ITBIS 18% y 16% (exclusivos)
- Cálculo ITBIS 18% Incluido (regresivo)
- Separación tax vs service_charge
- Cálculo de propina sobre (subtotal + impuestos)
- Validación de productos sin tax_types

**Archivo:** `tests/test_fiscal_integration.py` (9 tests de integración)
- Tests con base de datos real
- Creación de productos y tax_types
- Venta con múltiples tasas de ITBIS
- Cálculo correcto en ventas mixtas
- Validación de propina en transacciones completas

**Resultado:** 21/21 tests pasando ✅

#### 3. Mejora de UX en Formulario de Productos
**Archivo:** `templates/inventory/products.html`

**Mejoras implementadas:**
- **Agrupación visual por categoría:**
  - "Impuestos Fiscales (ITBIS)" - con icono bi-calculator
  - "Cargos por Servicio (Propina)" - con icono bi-wallet2
  - "Otros Impuestos/Cargos" - con icono bi-tag
- **Badges informativos:** Indican tasa y si es inclusivo/exclusivo
- **Tooltips explicativos:** Descripciones claras de cuándo usar cada tipo
- **Guía de uso integrada:** Recomendaciones directas en el formulario
- **Selección por defecto:** "ITBIS 18%" pre-seleccionado para nuevos productos

**Resultado:** Interfaz más intuitiva y reduce errores de configuración

#### 4. Documentación Completa de Tipos de ITBIS
**Archivo:** `GUIA_TIPOS_IMPUESTOS.md`

**Contenido:**
- Explicación detallada de cada tipo de ITBIS (18%, 16%, Incluido, Exento)
- Base legal y normativas dominicanas aplicables
- Cuándo usar cada tipo con ejemplos específicos
- Diferencia entre impuestos fiscales y cargos por servicio
- Cálculos paso a paso con ejemplos prácticos
- Ventas mixtas con múltiples tasas
- Tabla comparativa rápida
- Mejores prácticas y configuración del sistema
- Referencias a DGII y leyes (Ley 253-12, Ley 116-17)

**Resultado:** Guía de referencia completa para operadores y administradores

#### Archivos Modificados/Creados (Fase 2)
- `templates/inventory/products.html` - UX mejorada con agrupación visual
- `tests/test_fiscal_calculations.py` - Suite de tests unitarios (NUEVO)
- `tests/test_fiscal_integration.py` - Suite de tests de integración (NUEVO)
- `GUIA_TIPOS_IMPUESTOS.md` - Documentación completa de ITBIS (NUEVO)
- Base de datos - Productos Agua y Pechurinas corregidos

#### Impacto General (Fase 2)
- ✅ 100% cobertura de testing para cálculos fiscales
- ✅ UX optimizada reduce errores de configuración
- ✅ Documentación completa para capacitación de personal
- ✅ Todos los productos con configuración fiscal correcta
- ✅ Sistema robusto y confiable para cumplimiento DGII