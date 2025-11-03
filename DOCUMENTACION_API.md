# Documentación API - Sistema POS

**Versión:** 1.0  
**Última actualización:** 3 de noviembre de 2025  
**Base URL:** `/api`

---

## Tabla de Contenidos

1. [Introducción](#introducción)
2. [Autenticación](#autenticación)
3. [Estructura de Respuestas](#estructura-de-respuestas)
4. [Endpoints de Ventas](#endpoints-de-ventas)
5. [Endpoints de Productos](#endpoints-de-productos)
6. [Endpoints de Categorías](#endpoints-de-categorías)
7. [Endpoints de Mesas](#endpoints-de-mesas)
8. [Manejo de Errores](#manejo-de-errores)
9. [Códigos de Estado HTTP](#códigos-de-estado-http)
10. [Ejemplos de Uso](#ejemplos-de-uso)

---

## Introducción

La API del Sistema POS proporciona endpoints para gestionar ventas, productos, inventario y operaciones fiscales conforme a las regulaciones DGII de República Dominicana.

### Características Principales

- ✅ **Validaciones robustas** en backend y frontend
- ✅ **Manejo de errores estandarizado** con mensajes en español
- ✅ **Rastreo de errores** con IDs únicos
- ✅ **Logging completo** de operaciones críticas
- ✅ **Cumplimiento fiscal** con DGII (NCF, RNC, 606/607)
- ✅ **Control de stock** en tiempo real
- ✅ **Autenticación basada en sesiones** con roles

---

## Autenticación

### Requisitos

Todos los endpoints de la API requieren autenticación mediante sesión de Flask.

**Headers requeridos:**
```http
Cookie: session=<session_token>
X-CSRFToken: <csrf_token>
```

### Obtención de Token CSRF

El token CSRF está disponible en la sesión del usuario después del login.

**Frontend (JavaScript):**
```javascript
// El token se puede obtener de una meta tag en el HTML
const csrfToken = document.querySelector('meta[name="csrf-token"]').content;

// O desde un cookie
const csrfToken = getCookie('csrf_token');
```

### Roles y Permisos

| Rol | Crear Venta | Agregar Productos | Finalizar Venta | Gestión Inventario |
|-----|-------------|-------------------|-----------------|-------------------|
| **Administrador** | ✓ | ✓ | ✓ | ✓ |
| **Cajero** | ✓ | ✓ | ✓ | ✗ |
| **Mesero** | ✓ | ✓ | ✗ | ✗ |

---

## Estructura de Respuestas

### Respuesta Exitosa

```json
{
  "success": true,
  "data": {
    // Datos específicos del endpoint
  },
  "message": "Operación completada exitosamente"
}
```

### Respuesta de Error

Ver [Documentación de Códigos de Error](DOCUMENTACION_CODIGOS_ERROR.md) para detalles completos.

```json
{
  "error": "Mensaje del error",
  "type": "validation|business|permission|not_found|server",
  "error_id": "A1B2C3D4",
  "timestamp": "2025-11-03T14:30:45.123456",
  "details": "Detalles adicionales",
  "field": "campo_con_error"
}
```

---

## Endpoints de Ventas

### 1. Crear Venta

Crea una nueva venta pendiente.

**Endpoint:** `POST /api/sales`

**Autenticación:** Requerida (todos los roles)

**Request Body:**
```json
{
  "table_id": 5,  // Opcional
  "description": "Pedido mesa 5"  // Opcional
}
```

**Response Exitosa:** `201 Created`
```json
{
  "sale_id": 123,
  "status": "pending",
  "subtotal": 0,
  "tax_amount": 0,
  "total": 0,
  "created_at": "2025-11-03T14:30:45"
}
```

**Errores Posibles:**
- `401` - No autenticado
- `404` - Mesa no encontrada (si table_id proporcionado)

---

### 2. Agregar Producto a Venta

Agrega un producto a una venta existente.

**Endpoint:** `POST /api/sales/{sale_id}/items`

**Autenticación:** Requerida (todos los roles)

**Request Body:**
```json
{
  "product_id": 15,
  "quantity": 2
}
```

**Validaciones:**
- `quantity`: 1-1000 unidades (entero)
- `product_id`: Debe existir y estar activo
- Stock suficiente para productos inventariables
- Venta debe estar en estado `pending` o `tab_open`

**Response Exitosa:** `200 OK`
```json
{
  "item_id": 456,
  "product_id": 15,
  "product_name": "Coca Cola 2L",
  "quantity": 2,
  "unit_price": 100.00,
  "total_price": 200.00,
  "sale_total": 200.00
}
```

**Errores Posibles:**
- `400` - Validación fallida
  - Cantidad inválida (< 1 o > 1000)
  - Campos requeridos faltantes
- `400` - Stock insuficiente (tipo: business)
- `404` - Venta o producto no encontrado
- `409` - Venta ya finalizada

---

### 3. Finalizar Venta

Finaliza una venta, asigna NCF, actualiza stock y genera recibo.

**Endpoint:** `POST /api/sales/{sale_id}/finalize`

**Autenticación:** Requerida (solo **Cajero** o **Administrador**)

**Request Body:**
```json
{
  "payment_method": "cash",  // cash|card|transfer
  "cash_received": 500.00,  // Opcional (solo para cash)
  "change_amount": 50.00,  // Opcional (solo para cash)
  "ncf_type": "consumo",  // consumo|credito_fiscal|sin_comprobante
  "customer_name": "Empresa ABC",  // Requerido para credito_fiscal
  "customer_rnc": "123456789"  // Requerido para credito_fiscal
}
```

**Validaciones:**

| Campo | Validación |
|-------|------------|
| `payment_method` | Debe ser: `cash`, `card`, o `transfer` |
| `cash_received` | RD$ 0 - RD$ 1,000,000 (solo para cash) |
| `ncf_type` | `consumo`, `credito_fiscal`, o `sin_comprobante` |
| `customer_name` | Requerido si `ncf_type === 'credito_fiscal'` |
| `customer_rnc` | Requerido si `ncf_type === 'credito_fiscal'` (9 u 11 dígitos) |

**Response Exitosa:** `200 OK`
```json
{
  "success": true,
  "sale_id": 123,
  "ncf": "B0100000123",
  "ncf_type": "consumo",
  "total": 450.00,
  "payment_method": "cash",
  "cash_received": 500.00,
  "change_amount": 50.00,
  "receipt_url": "/receipts/receipt_123.pdf"
}
```

**Errores Posibles:**
- `400` - Validación fallida
  - Método de pago inválido
  - Efectivo recibido inválido
  - RNC inválido
  - Faltan nombre o RNC para crédito fiscal
- `403` - Permisos insuficientes (solo cajeros/admin)
- `404` - Venta no encontrada
- `409` - Venta ya finalizada

---

### 4. Eliminar Producto de Venta

Elimina un ítem de una venta pendiente.

**Endpoint:** `DELETE /api/sales/{sale_id}/items/{item_id}`

**Autenticación:** Requerida (todos los roles)

**Response Exitosa:** `200 OK`
```json
{
  "success": true,
  "new_total": 250.00
}
```

**Errores Posibles:**
- `404` - Venta o ítem no encontrado
- `409` - Venta ya finalizada

---

### 5. Actualizar Cantidad de Producto

Actualiza la cantidad de un ítem en la venta.

**Endpoint:** `PUT /api/sales/{sale_id}/items/{item_id}/quantity`

**Autenticación:** Requerida (todos los roles)

**Request Body:**
```json
{
  "quantity": 5
}
```

**Validaciones:**
- `quantity`: 1-1000 unidades
- Stock suficiente disponible

**Response Exitosa:** `200 OK`
```json
{
  "success": true,
  "new_quantity": 5,
  "new_item_total": 500.00,
  "new_sale_total": 750.00
}
```

**Errores Posibles:**
- `400` - Cantidad inválida o stock insuficiente
- `404` - Venta o ítem no encontrado
- `409` - Venta ya finalizada

---

## Endpoints de Productos

### 1. Listar Productos

Obtiene lista de productos activos.

**Endpoint:** `GET /api/products`

**Autenticación:** Requerida

**Query Parameters:**
- `category_id` (opcional): Filtrar por categoría

**Response Exitosa:** `200 OK`
```json
[
  {
    "id": 15,
    "name": "Coca Cola 2L",
    "price": 100.00,
    "stock": 50,
    "min_stock": 10,
    "product_type": "inventariable",
    "category_id": 3,
    "tax_types": [
      {
        "id": 1,
        "name": "ITBIS 18%",
        "rate": 0.18,
        "is_inclusive": false
      }
    ]
  }
]
```

---

### 2. Consultar Stock de Producto

Verifica disponibilidad de stock en tiempo real.

**Endpoint:** `GET /api/products/{product_id}/stock`

**Autenticación:** Requerida

**Response Exitosa:** `200 OK`
```json
{
  "product_id": 15,
  "product_name": "Coca Cola 2L",
  "stock_available": 50,
  "min_stock": 10,
  "product_type": "inventariable",
  "is_available": true,
  "stock_status": "available"  // available|low_stock|out_of_stock|not_tracked
}
```

**Estados de Stock:**
- `available`: Stock > min_stock
- `low_stock`: Stock ≤ min_stock (pero > 0)
- `out_of_stock`: Stock = 0
- `not_tracked`: Producto tipo servicio

---

## Endpoints de Categorías

### Listar Categorías

Obtiene lista de categorías activas.

**Endpoint:** `GET /api/categories`

**Autenticación:** Requerida

**Response Exitosa:** `200 OK`
```json
[
  {
    "id": 3,
    "name": "Bebidas",
    "active": true
  },
  {
    "id": 5,
    "name": "Comida",
    "active": true
  }
]
```

---

## Endpoints de Mesas

### 1. Listar Mesas

Obtiene lista de mesas.

**Endpoint:** `GET /api/tables`

**Autenticación:** Requerida

**Query Parameters:**
- `status` (opcional): Filtrar por estado (available, occupied, reserved)

**Response Exitosa:** `200 OK`
```json
[
  {
    "id": 1,
    "number": 1,
    "capacity": 4,
    "status": "available",
    "active": true
  }
]
```

---

### 2. Actualizar Estado de Mesa

Cambia el estado de una mesa.

**Endpoint:** `PUT /api/tables/{table_id}/status`

**Autenticación:** Requerida

**Request Body:**
```json
{
  "status": "occupied"  // available|occupied|reserved
}
```

**Response Exitosa:** `200 OK`
```json
{
  "success": true,
  "table_id": 1,
  "new_status": "occupied"
}
```

---

## Manejo de Errores

### Tipos de Error

Ver [Documentación de Códigos de Error](DOCUMENTACION_CODIGOS_ERROR.md) para catálogo completo.

1. **validation** - Errores de validación de datos
2. **business** - Errores de lógica de negocio
3. **permission** - Errores de autorización
4. **not_found** - Recurso no encontrado
5. **server** - Errores internos del servidor

### Estructura de Error

```json
{
  "error": "Mensaje principal",
  "type": "validation",
  "error_id": "A1B2C3D4",
  "timestamp": "2025-11-03T14:30:45.123456",
  "details": "Detalles adicionales",
  "field": "campo_con_error",
  "value_received": "valor_incorrecto",
  "min_allowed": 1,
  "max_allowed": 1000
}
```

### Rastreo de Errores

Cada error incluye un `error_id` único de 8 caracteres para rastreo en logs.

**Ejemplo de búsqueda en logs:**
```bash
grep "A1B2C3D4" logs/pos_app.log
```

---

## Códigos de Estado HTTP

| Código | Significado | Uso |
|--------|-------------|-----|
| 200 | OK | Operación exitosa |
| 201 | Created | Recurso creado |
| 400 | Bad Request | Validación fallida |
| 401 | Unauthorized | No autenticado |
| 403 | Forbidden | Sin permisos |
| 404 | Not Found | Recurso no encontrado |
| 409 | Conflict | Conflicto de estado |
| 500 | Internal Server Error | Error del servidor |

---

## Ejemplos de Uso

### Ejemplo 1: Flujo Completo de Venta

```javascript
// 1. Crear venta
const createSaleResponse = await fetch('/api/sales', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRFToken': csrfToken
  },
  body: JSON.stringify({
    table_id: 5
  })
});

const sale = await createSaleResponse.json();
const saleId = sale.sale_id;

// 2. Agregar productos
await fetch(`/api/sales/${saleId}/items`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRFToken': csrfToken
  },
  body: JSON.stringify({
    product_id: 15,
    quantity: 2
  })
});

await fetch(`/api/sales/${saleId}/items`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRFToken': csrfToken
  },
  body: JSON.stringify({
    product_id: 20,
    quantity: 1
  })
});

// 3. Finalizar venta
const finalizeResponse = await fetch(`/api/sales/${saleId}/finalize`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRFToken': csrfToken
  },
  body: JSON.stringify({
    payment_method: 'cash',
    cash_received: 500.00,
    ncf_type: 'consumo'
  })
});

const result = await finalizeResponse.json();
console.log('NCF:', result.ncf);
console.log('Cambio:', result.change_amount);
```

---

### Ejemplo 2: Venta con NCF de Crédito Fiscal

```javascript
// Crear y procesar venta para empresa
const saleResponse = await fetch('/api/sales', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRFToken': csrfToken
  },
  body: JSON.stringify({})
});

const sale = await saleResponse.json();

// Agregar producto
await fetch(`/api/sales/${sale.sale_id}/items`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRFToken': csrfToken
  },
  body: JSON.stringify({
    product_id: 15,
    quantity: 10
  })
});

// Finalizar con NCF de crédito fiscal
const finalizeResponse = await fetch(`/api/sales/${sale.sale_id}/finalize`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRFToken': csrfToken
  },
  body: JSON.stringify({
    payment_method: 'transfer',
    ncf_type: 'credito_fiscal',
    customer_name: 'Empresa ABC S.R.L.',
    customer_rnc: '123456789'  // Será formateado a 123-45678-9
  })
});

const result = await finalizeResponse.json();
console.log('NCF Crédito Fiscal:', result.ncf);
```

---

### Ejemplo 3: Manejo de Errores

```javascript
async function addItemToSale(saleId, productId, quantity) {
  try {
    const response = await fetch(`/api/sales/${saleId}/items`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      body: JSON.stringify({
        product_id: productId,
        quantity: quantity
      })
    });
    
    if (!response.ok) {
      const error = await response.json();
      
      // Manejo por tipo de error
      switch (error.type) {
        case 'validation':
          console.error(`Validación fallida en ${error.field}: ${error.error}`);
          showFieldError(error.field, error.error);
          break;
          
        case 'business':
          // Stock insuficiente
          console.error(`Error de negocio: ${error.error}`);
          if (error.available_stock !== undefined) {
            alert(`Solo hay ${error.available_stock} unidades disponibles de ${error.product_name}`);
          }
          break;
          
        case 'not_found':
          console.error('Recurso no encontrado:', error.error);
          refreshProductList();
          break;
          
        case 'server':
          console.error(`Error del servidor [${error.error_id}]:`, error.error);
          alert(`Error inesperado. Código: ${error.error_id}. Contacte al administrador.`);
          break;
      }
      
      return null;
    }
    
    const result = await response.json();
    return result;
    
  } catch (networkError) {
    console.error('Error de red:', networkError);
    alert('Error de conexión. Verifique su conexión a internet.');
    return null;
  }
}
```

---

### Ejemplo 4: Verificar Stock Antes de Agregar

```javascript
async function checkStockAndAdd(saleId, productId, quantity) {
  // 1. Verificar stock disponible
  const stockResponse = await fetch(`/api/products/${productId}/stock`, {
    headers: {
      'X-CSRFToken': csrfToken
    }
  });
  
  const stockInfo = await stockResponse.json();
  
  // 2. Validar disponibilidad
  if (!stockInfo.is_available) {
    alert(`${stockInfo.product_name} está agotado`);
    return false;
  }
  
  if (stockInfo.stock_available < quantity) {
    alert(`Solo hay ${stockInfo.stock_available} unidades disponibles de ${stockInfo.product_name}`);
    return false;
  }
  
  // 3. Agregar a la venta
  const addResponse = await fetch(`/api/sales/${saleId}/items`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken
    },
    body: JSON.stringify({
      product_id: productId,
      quantity: quantity
    })
  });
  
  return addResponse.ok;
}
```

---

## Límites y Restricciones

### Límites de Validación

| Campo | Límite Mínimo | Límite Máximo |
|-------|---------------|---------------|
| Cantidad por ítem | 1 unidad | 1000 unidades |
| Ítems en carrito | 1 producto | 100 productos |
| Efectivo recibido | RD$ 0 | RD$ 1,000,000 |
| Precio de producto | RD$ 0 | RD$ 1,000,000 |
| Stock de producto | 0 unidades | 100,000 unidades |

### Confirmaciones Requeridas

El sistema solicita confirmación explícita para:

1. **Vaciar carrito:** Cuando hay ítems en el carrito
2. **Ventas elevadas:** Cuando el total > RD$ 100,000

---

## Versionado y Compatibilidad

**Versión actual:** 1.0  
**Compatibilidad:** Todas las mejoras de manejo de errores (Fases 1-6)

### Cambios Recientes (v1.0)

- ✅ Manejo de errores estandarizado con IDs únicos
- ✅ Validaciones completas con funciones centralizadas
- ✅ Logging estructurado con contexto completo
- ✅ Mensajes de error en español amigables para usuarios
- ✅ Validación fiscal completa (NCF, RNC conforme a DGII)
- ✅ Confirmaciones de alto riesgo

---

## Soporte y Recursos

### Documentación Relacionada

- [Documentación de Códigos de Error](DOCUMENTACION_CODIGOS_ERROR.md)
- [Guía de Troubleshooting](GUIA_TROUBLESHOOTING.md)
- [Plan de Mejoras de Manejo de Errores](PLAN_MEJORAS_MANEJO_ERRORES.md)

### Reportar Problemas

Para reportar errores o bugs en la API:

1. Incluir `error_id` del error
2. Endpoint afectado
3. Request body enviado
4. Response recibido
5. Pasos para reproducir

### Contacto

Para asistencia técnica o consultas sobre la API, contactar al administrador del sistema con el código de error si está disponible.

---

**Última actualización:** 3 de noviembre de 2025  
**Mantenido por:** Equipo de Desarrollo Sistema POS
