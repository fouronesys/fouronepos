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

### ✅ FASE 2 COMPLETADA (16 Oct 2025) - Mejoras de Sistema

#### 1. Auditoría y Corrección de Productos sin Tax Types
**Query de Auditoría Ejecutada:**
```sql
SELECT p.id, p.name, p.price, p.category_id, p.product_type
FROM products p
LEFT JOIN product_taxes pt ON p.id = pt.product_id
WHERE pt.id IS NULL;
```

**Resultados:**
- **Productos sin tax types encontrados:** 1 producto ("Ron de prueba", id=11)
- **Acción tomada:** Asignado ITBIS 18% (tax_type_id=8)
- **Estado final:** ✅ 0 productos sin tax types en el sistema

**Impacto:**
- Todos los productos ahora tienen configuración fiscal correcta
- Cumplimiento fiscal garantizado para todo el inventario
- Prevención de errores en cálculos de venta

#### 2. Suite de Testing Fiscal Completa
**Archivo:** `tests/test_fiscal_calculations.py`

**Tests Implementados:** 12 tests unitarios, todos pasando (100%)

**Cobertura de Tests:**
1. **TestFiscalCalculations (9 tests):**
   - ✅ ITBIS 18% exclusivo (se agrega al precio)
   - ✅ ITBIS 18% incluido (cálculo regresivo)
   - ✅ ITBIS 16% reducido (lácteos, café, etc.)
   - ✅ Propina 10% sobre (subtotal + impuestos) - Normativa RD
   - ✅ Separación correcta tax vs service_charge
   - ✅ Suma correcta de múltiples tax_types (solo categoría 'tax')
   - ✅ Productos con diferentes tasas de ITBIS
   - ✅ Productos exentos de ITBIS (0%)
   - ✅ Redondeo correcto a centavos (2 decimales)

2. **TestTaxCategoryValidation (2 tests):**
   - ✅ Validación de valores enum TaxCategory
   - ✅ Fallback defensivo cuando tax_category es NULL

3. **TestProductTaxValidation (1 test):**
   - ✅ Producto debe tener al menos un tax_type

**Resultado de Ejecución:**
```
============================= test session starts ==============================
collected 12 items

tests/test_fiscal_calculations.py::TestFiscalCalculations::test_itbis_16_reducido PASSED [  8%]
tests/test_fiscal_calculations.py::TestFiscalCalculations::test_itbis_exclusivo_calculo PASSED [ 16%]
tests/test_fiscal_calculations.py::TestFiscalCalculations::test_itbis_inclusivo_calculo PASSED [ 25%]
tests/test_fiscal_calculations.py::TestFiscalCalculations::test_multiples_productos_con_diferentes_itbis PASSED [ 33%]
tests/test_fiscal_calculations.py::TestFiscalCalculations::test_producto_exento_itbis PASSED [ 41%]
tests/test_fiscal_calculations.py::TestFiscalCalculations::test_propina_sobre_subtotal_mas_impuestos PASSED [ 50%]
tests/test_fiscal_calculations.py::TestFiscalCalculations::test_redondeo_centavos PASSED [ 58%]
tests/test_fiscal_calculations.py::TestFiscalCalculations::test_separacion_tax_vs_service_charge PASSED [ 66%]
tests/test_fiscal_calculations.py::TestFiscalCalculations::test_suma_correcta_multiples_tax_types PASSED [ 75%]
tests/test_fiscal_calculations.py::TestTaxCategoryValidation::test_fallback_defensivo_tax_category PASSED [ 83%]
tests/test_fiscal_calculations.py::TestTaxCategoryValidation::test_tax_category_enum_values PASSED [ 91%]
tests/test_fiscal_calculations.py::TestProductTaxValidation::test_producto_debe_tener_tax_type PASSED [100%]

============================== 12 passed in 0.07s ==============================
```

#### 3. Mejoras de UX en Formulario de Productos
**Archivo:** `templates/inventory/products.html`

**Mejoras Implementadas:**

**A. Categorización Visual de Tax Types:**
- 📊 **Impuestos Fiscales (ITBIS)** - Icono: bi-receipt-cutoff (azul)
  - ITBIS 18%, ITBIS 16%, ITBIS 18% Incluído, ITBIS Exento, Sin Impuesto
- 💰 **Cargos por Servicio** - Icono: bi-percent (verde)
  - Propina 10%
- 🏷️ **Otros Impuestos/Cargos** - Icono: bi-tag (amarillo)
  - Para tax types de categoría 'other'

**B. Información Visual Mejorada:**
- **Badges con porcentajes:** Muestra la tasa de cada impuesto (ej: "18%")
- **Badges inclusivo/exclusivo:** 
  - 🔵 "Incluido" para impuestos incluidos en el precio
  - ⚪ "Exclusivo" para impuestos que se agregan al precio
- **Iconos diferenciados:**
  - bi-calculator: ITBIS 18%
  - bi-calculator-fill: ITBIS 16%
  - bi-check-circle: ITBIS Incluído
  - bi-slash-circle: ITBIS Exento
  - bi-wallet2: Propina

**C. Tooltips Explicativos:**
- "ITBIS 18%": Tasa estándar para la mayoría de productos. Se agrega al precio base.
- "ITBIS 16%": Tasa reducida para lácteos, café, azúcar y cacao.
- "ITBIS 18% Incluido": Usar cuando el precio ya incluye el impuesto (precio final).
- "ITBIS Exento": Para productos exentos de impuestos (0%).
- "Propina 10%": Cargo por servicio según normativa dominicana.

**D. Guía de Uso Integrada:**
- Recomendaciones directas en el formulario
- Ejemplos de cuándo usar cada tipo
- ITBIS 18% pre-seleccionado por defecto para nuevos productos

**Resultado:** Interfaz más intuitiva y reduce errores de configuración

#### 4. Documentación Completa de Tipos de ITBIS
**Archivo:** `GUIA_TIPOS_IMPUESTOS.md`

**Contenido del Documento (300+ líneas):**

**A. Descripción de Cada Tipo de Impuesto:**
1. ITBIS 18% (Tasa Estándar) - Cuándo usar, cálculo, ejemplos
2. ITBIS 16% (Tasa Reducida) - Productos de canasta básica, base legal
3. ITBIS 18% Incluido - Cálculo regresivo, casos de uso
4. ITBIS Exento (0%) - Productos exentos por ley, exenciones
5. Sin Impuesto - Diferencia con ITBIS Exento
6. Propina 10% (Ley) - Normativa dominicana, cálculo correcto

**B. Ejemplos Detallados de Cálculos:**
- Venta simple con ITBIS 18%
- Venta con tasa reducida (ITBIS 16%)
- Venta con precio incluido (cálculo regresivo)
- Venta mixta con múltiples tasas de ITBIS

**C. Tabla Comparativa Rápida:**
| Tipo | Tasa | Se Agrega | Incluido | Uso Principal |
|------|------|-----------|----------|---------------|
| ITBIS 18% | 18% | ✅ Sí | ❌ No | Productos generales |
| ITBIS 16% | 16% | ✅ Sí | ❌ No | Lácteos, café, azúcar, cacao |
| ... | ... | ... | ... | ... |

**D. Mejores Prácticas y Configuración:**
- Configuración de productos según tipo
- Validaciones del sistema
- Reportes DGII (606/607)
- Referencias legales y contactos

**E. Base Legal Documentada:**
- Ley 253-12 (Código Tributario)
- Ley 116-17 (Ley de Propina Legal)
- Decreto 583-08 (Reglamento del ITBIS)
- Enlaces a portal DGII

**Resultado:** Guía de referencia completa para operadores y administradores

#### Archivos Modificados/Creados (Fase 2)
- `tests/test_fiscal_calculations.py` - Suite de tests unitarios (NUEVO)
- `GUIA_TIPOS_IMPUESTOS.md` - Documentación completa de ITBIS (NUEVO)
- `ERRORES_LOGICA_FUNCIONAL.md` - Actualizado con resumen FASE 2
- Base de datos - Producto "Ron de prueba" corregido con ITBIS 18%

#### Métricas de Éxito (Fase 2)
- ✅ **Auditoría de Productos:** 1 producto corregido, 0 pendientes
- ✅ **Cobertura de Tests:** 12/12 tests pasando (100%)
- ✅ **Documentación:** 1 guía completa creada (300+ líneas)
- ✅ **UX Mejorado:** Categorización, tooltips, guías integradas
- ✅ **Cumplimiento Fiscal:** 100% de productos con configuración válida

#### Impacto General (Fase 2)
- ✅ **Integridad de Datos:** 100% de productos con tax types configurados
- ✅ **Calidad del Software:** 12 tests unitarios implementados, cobertura completa de cálculos fiscales
- ✅ **Experiencia de Usuario:** UX mejorada con categorización visual, tooltips y guías integradas
- ✅ **Documentación:** Guía completa de tipos de impuestos con ejemplos y referencias legales
- ✅ **Cumplimiento Fiscal:** Sistema preparado para auditorías DGII con cálculos validados