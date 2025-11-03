# Documentación de Códigos de Error - Sistema POS

**Versión:** 1.0  
**Última actualización:** 3 de noviembre de 2025  
**Implementado en:** Fases 1-6 del Plan de Mejoras de Manejo de Errores

---

## Índice

1. [Estructura de Respuestas de Error](#estructura-de-respuestas-de-error)
2. [Tipos de Error](#tipos-de-error)
3. [Códigos de Estado HTTP](#códigos-de-estado-http)
4. [Catálogo de Errores Comunes](#catálogo-de-errores-comunes)
5. [Guía de Soluciones](#guía-de-soluciones)
6. [IDs de Error y Rastreo](#ids-de-error-y-rastreo)

---

## Estructura de Respuestas de Error

Todas las respuestas de error del sistema siguen una estructura JSON estandarizada:

```json
{
  "error": "Mensaje principal del error (breve y claro)",
  "type": "Tipo de error (validation, business, permission, not_found, server)",
  "error_id": "A1B2C3D4",
  "timestamp": "2025-11-03T14:30:45.123456",
  "details": "Detalles adicionales del error (opcional)",
  "field": "nombre_del_campo (para errores de validación)",
  "value_received": "valor_recibido (opcional)",
  "min_allowed": 0,
  "max_allowed": 1000,
  "valid_options": ["opcion1", "opcion2"],
  "user_message": "Mensaje amigable para el usuario (opcional)"
}
```

### Campos Obligatorios

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `error` | string | Mensaje principal del error, breve y descriptivo |
| `type` | string | Tipo de error (ver sección "Tipos de Error") |
| `error_id` | string | ID único de 8 caracteres para rastreo del error |
| `timestamp` | string | Timestamp ISO 8601 del momento del error |

### Campos Opcionales

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `details` | string | Información adicional sobre el error |
| `field` | string | Campo que causó el error (validaciones) |
| `value_received` | any | Valor recibido que causó el error |
| `min_allowed` | number | Valor mínimo permitido (validaciones numéricas) |
| `max_allowed` | number | Valor máximo permitido (validaciones numéricas) |
| `valid_options` | array | Lista de valores válidos (para enums) |
| `user_message` | string | Mensaje alternativo amigable para usuarios |
| `product_name` | string | Nombre del producto (errores de stock) |
| `available_stock` | number | Stock disponible (errores de stock) |
| `required_stock` | number | Stock requerido (errores de stock) |

---

## Tipos de Error

El sistema clasifica todos los errores en 5 tipos principales:

### 1. `validation` - Errores de Validación

**Descripción:** Datos enviados no cumplen con los requisitos de formato o rango.

**Código HTTP:** `400 Bad Request`

**Ejemplos:**
- RNC inválido (formato incorrecto)
- Cantidad fuera de rango (1-1000)
- Email con formato incorrecto
- Campos requeridos faltantes
- Método de pago inválido

**Nivel de Log:** `WARNING`

**Mensaje típico:**
```json
{
  "error": "Cantidad debe ser mayor o igual a 1",
  "type": "validation",
  "error_id": "A1B2C3D4",
  "field": "quantity",
  "value_received": 0,
  "min_allowed": 1,
  "max_allowed": 1000
}
```

---

### 2. `business` - Errores de Lógica de Negocio

**Descripción:** Operación no permitida por las reglas del negocio.

**Código HTTP:** `400 Bad Request` (mayoría) o `409 Conflict`

**Ejemplos:**
- Stock insuficiente para completar venta
- Venta ya finalizada (intento de modificación)
- Producto duplicado en venta
- Efectivo recibido menor al total

**Nivel de Log:** `WARNING`

**Mensaje típico:**
```json
{
  "error": "Stock insuficiente para Coca Cola 2L",
  "type": "business",
  "error_id": "B5C6D7E8",
  "product_name": "Coca Cola 2L",
  "available_stock": 5,
  "required_stock": 10,
  "details": "El producto Coca Cola 2L solo tiene 5 unidades disponibles. Se requieren 10 unidades."
}
```

---

### 3. `permission` - Errores de Permisos

**Descripción:** Usuario no tiene permisos para realizar la operación.

**Código HTTP:** `403 Forbidden` (con sesión válida) o `401 Unauthorized` (sin sesión)

**Ejemplos:**
- No autenticado (sin sesión)
- Mesero intentando finalizar venta (solo cajeros)
- Usuario no tiene rol apropiado

**Nivel de Log:** `WARNING`

**Mensaje típico:**
```json
{
  "error": "Permisos insuficientes",
  "type": "permission",
  "error_id": "C9D0E1F2",
  "details": "Solo cajeros y administradores pueden finalizar ventas. Su rol actual es: MESERO",
  "user_role": "MESERO",
  "required_roles": ["ADMINISTRADOR", "CAJERO"]
}
```

---

### 4. `not_found` - Recurso No Encontrado

**Descripción:** Recurso solicitado no existe en el sistema.

**Código HTTP:** `404 Not Found`

**Ejemplos:**
- Venta no encontrada
- Producto no encontrado
- Mesa no encontrada
- Usuario no existe

**Nivel de Log:** `WARNING`

**Mensaje típico:**
```json
{
  "error": "Producto no encontrado",
  "type": "not_found",
  "error_id": "D3E4F5G6",
  "details": "No existe un producto con ID 99999",
  "product_id": 99999
}
```

---

### 5. `server` - Errores Internos del Servidor

**Descripción:** Error inesperado en el servidor.

**Código HTTP:** `500 Internal Server Error`

**Ejemplos:**
- Error de base de datos
- Error de integridad referencial
- Excepción no manejada
- Error de conexión a servicios externos

**Nivel de Log:** `ERROR`

**Mensaje típico:**
```json
{
  "error": "Error interno del servidor",
  "type": "server",
  "error_id": "E7F8G9H0",
  "details": "Error inesperado al procesar la venta. Contacte al administrador del sistema.",
  "timestamp": "2025-11-03T14:30:45.123456"
}
```

---

## Códigos de Estado HTTP

| Código | Significado | Cuándo se usa |
|--------|-------------|---------------|
| `200` | OK | Operación exitosa (GET, PUT, DELETE) |
| `201` | Created | Recurso creado exitosamente (POST) |
| `400` | Bad Request | Error de validación o lógica de negocio |
| `401` | Unauthorized | No autenticado (sin sesión válida) |
| `403` | Forbidden | Autenticado pero sin permisos |
| `404` | Not Found | Recurso no encontrado |
| `409` | Conflict | Conflicto de estado (ej: venta ya finalizada) |
| `500` | Internal Server Error | Error inesperado del servidor |

---

## Catálogo de Errores Comunes

### Errores de Validación de Ventas

#### Error: Cantidad Inválida
```json
{
  "error": "Cantidad debe ser mayor o igual a 1",
  "type": "validation",
  "field": "quantity",
  "value_received": 0,
  "min_allowed": 1,
  "max_allowed": 1000
}
```
**Solución:** Enviar una cantidad entre 1 y 1000 unidades.

---

#### Error: Método de Pago Inválido
```json
{
  "error": "Método de pago inválido",
  "type": "validation",
  "field": "payment_method",
  "value_received": "bitcoin",
  "valid_options": ["cash", "card", "transfer"]
}
```
**Solución:** Usar uno de los métodos de pago válidos: `cash`, `card`, o `transfer`.

---

#### Error: Efectivo Recibido Inválido
```json
{
  "error": "Efectivo recibido debe ser mayor o igual a 0",
  "type": "validation",
  "field": "cash_received",
  "value_received": -100,
  "min_allowed": 0,
  "max_allowed": 1000000
}
```
**Solución:** Enviar un monto de efectivo entre RD$ 0 y RD$ 1,000,000.

---

### Errores de Validación Fiscal

#### Error: NCF Crédito Fiscal sin Nombre de Cliente
```json
{
  "error": "El NCF de Crédito Fiscal requiere nombre del cliente",
  "type": "validation",
  "details": "Según normas DGII, el NCF de Crédito Fiscal debe incluir nombre y RNC del cliente",
  "ncf_type": "credito_fiscal"
}
```
**Solución:** Proporcionar `customer_name` y `customer_rnc` cuando `ncf_type` sea `credito_fiscal`.

---

#### Error: RNC Inválido
```json
{
  "error": "RNC debe tener 9 u 11 dígitos, recibido 5",
  "type": "validation",
  "field": "customer_rnc",
  "value_received": "12345"
}
```
**Solución:** Enviar un RNC válido de 9 dígitos (empresa) u 11 dígitos (persona física).

---

### Errores de Lógica de Negocio

#### Error: Stock Insuficiente
```json
{
  "error": "Stock insuficiente para Coca Cola 2L",
  "type": "business",
  "product_name": "Coca Cola 2L",
  "product_id": 15,
  "available_stock": 5,
  "required_stock": 10,
  "details": "El producto Coca Cola 2L solo tiene 5 unidades disponibles. Se requieren 10 unidades."
}
```
**Solución:** Reducir la cantidad solicitada a 5 unidades o menos, o reabastecer el producto.

---

#### Error: Venta Ya Finalizada
```json
{
  "error": "No se puede modificar una venta finalizada",
  "type": "business",
  "sale_id": 123,
  "sale_status": "completed",
  "details": "Esta venta ya fue finalizada y no puede ser modificada. Use la función de cancelación si necesita anular la venta."
}
```
**Solución:** No se pueden agregar/eliminar ítems de ventas finalizadas. Crear una nueva venta o cancelar la existente.

---

### Errores de Permisos

#### Error: No Autenticado
```json
{
  "error": "No autorizado",
  "type": "permission",
  "details": "Debe iniciar sesión para acceder a este recurso"
}
```
**Solución:** Iniciar sesión con credenciales válidas antes de acceder al endpoint.

---

#### Error: Rol Insuficiente
```json
{
  "error": "Permisos insuficientes",
  "type": "permission",
  "user_role": "MESERO",
  "required_roles": ["ADMINISTRADOR", "CAJERO"],
  "details": "Solo cajeros y administradores pueden finalizar ventas. Su rol actual es: MESERO"
}
```
**Solución:** Solicitar que un cajero o administrador complete la operación.

---

### Errores de Recursos No Encontrados

#### Error: Venta No Encontrada
```json
{
  "error": "Venta no encontrada",
  "type": "not_found",
  "sale_id": 99999,
  "details": "No existe una venta con ID 99999"
}
```
**Solución:** Verificar que el ID de venta sea correcto. La venta puede haber sido eliminada o nunca existió.

---

#### Error: Producto No Encontrado
```json
{
  "error": "Producto no encontrado",
  "type": "not_found",
  "product_id": 99999,
  "details": "No existe un producto con ID 99999"
}
```
**Solución:** Verificar que el producto exista y esté activo en el sistema.

---

### Errores del Servidor

#### Error: Error de Base de Datos
```json
{
  "error": "Error interno del servidor",
  "type": "server",
  "error_id": "E7F8G9H0",
  "details": "Error inesperado al procesar la venta. Contacte al administrador del sistema.",
  "timestamp": "2025-11-03T14:30:45.123456"
}
```
**Solución:** Contactar al administrador del sistema con el `error_id` para rastrear el problema en los logs.

---

## Guía de Soluciones

### Validación de Campos

#### Cantidad de Productos
- **Rango permitido:** 1-1000 unidades
- **Tipo:** Entero
- **Campo:** `quantity`
- **Validación:** `validate_integer_range(quantity, min_val=1, max_val=1000)`

#### Efectivo Recibido
- **Rango permitido:** RD$ 0 - RD$ 1,000,000
- **Tipo:** Decimal
- **Campo:** `cash_received`
- **Validación:** `validate_numeric_range(cash_received, min_val=0, max_val=1000000)`

#### Método de Pago
- **Opciones válidas:** `cash`, `card`, `transfer`
- **Tipo:** String (enum)
- **Campo:** `payment_method`
- **Validación:** Debe estar en lista de opciones válidas

#### RNC (Registro Nacional del Contribuyente)
- **Formato:** 9 u 11 dígitos
- **9 dígitos:** Empresa (empieza con 1, 3, 4, o 5)
- **11 dígitos:** Persona física (empieza con 0, 1, o 4)
- **Campo:** `customer_rnc`
- **Validación:** `validate_rnc(rnc)`
- **Formateo automático:** `123456789` → `123-45678-9`

#### Teléfono (República Dominicana)
- **Formato:** 10 dígitos (809/829/849 + 7 dígitos)
- **Ejemplo:** `(809) 555-1234` o `+1 (809) 555-1234`
- **Campo:** `phone`
- **Validación:** `validate_phone_rd(phone)`

#### Email
- **Formato:** estándar RFC 5322
- **Ejemplo:** `usuario@dominio.com`
- **Campo:** `email`
- **Validación:** `validate_email(email)`

---

### Reglas de Negocio

#### Stock de Productos
1. **Productos inventariables:** Deben tener stock > 0 para ser vendidos
2. **Productos de servicio:** No requieren validación de stock
3. **Validación:** Se verifica stock antes de agregar ítem a venta
4. **Stock insuficiente:** Error tipo `business` con detalles del producto

#### NCF de Crédito Fiscal
1. **Requiere:** `customer_name` (no vacío) y `customer_rnc` (válido)
2. **Norma:** DGII Norma 06-2018
3. **Validación:** Backend y frontend
4. **Mensajes:** Claros y educativos

#### Límites del Sistema
| Concepto | Límite | Validación |
|----------|--------|------------|
| Cantidad por ítem | 1-1000 unidades | validate_integer_range |
| Ítems en carrito | Máximo 100 productos | MAX_CART_ITEMS |
| Efectivo recibido | RD$ 0-1,000,000 | validate_numeric_range |
| Precio de producto | RD$ 0-1,000,000 | validate_numeric_range |
| Stock de producto | 0-100,000 unidades | validate_integer_range |

---

### Confirmaciones de Alto Riesgo

El sistema solicita confirmación explícita para:

1. **Vaciar carrito:** Cuando hay ítems en el carrito
2. **Ventas elevadas:** Cuando el total > RD$ 100,000

Estas confirmaciones previenen operaciones accidentales sin interrumpir el flujo normal.

---

## IDs de Error y Rastreo

### Formato de Error ID
- **Longitud:** 8 caracteres
- **Formato:** Alfanumérico en mayúsculas
- **Ejemplo:** `A1B2C3D4`
- **Generación:** UUID aleatorio (primeros 8 caracteres)

### Uso del Error ID

1. **Usuario:** Reportar error con el ID para rastreo rápido
2. **Desarrollador:** Buscar en logs por el ID único
3. **Logs:** Incluyen error_id en cada entrada de error

### Buscar Error en Logs

```bash
# Buscar error específico en logs
grep "A1B2C3D4" logs/pos_app.log

# Ver contexto completo del error
grep -A 10 -B 10 "A1B2C3D4" logs/pos_app.log
```

### Información en Logs

Cada error registra:
- **error_id:** ID único del error
- **error_type:** Tipo de error
- **message:** Mensaje descriptivo
- **user_id:** ID del usuario que provocó el error
- **username:** Nombre de usuario
- **role:** Rol del usuario
- **Contexto adicional:** sale_id, product_id, etc.

**Ejemplo de log:**
```
[2025-11-03 14:30:45] WARNING [utils:81] - [A1B2C3D4] Stock insuficiente para producto Coca Cola 2L
```

---

## Mejores Prácticas

### Para Desarrolladores

1. **Usar funciones centralizadas:**
   - `error_response()` para todas las respuestas de error
   - `validate_*()` para todas las validaciones
   - `log_error()` para logging de errores

2. **Proporcionar contexto:**
   - Incluir detalles relevantes (IDs, valores, límites)
   - Usar mensajes descriptivos en español
   - Añadir sugerencias de solución cuando sea posible

3. **Niveles de log apropiados:**
   - `WARNING` para validation, business, permission
   - `ERROR` para server errors
   - `INFO` para operaciones exitosas

### Para Frontend

1. **Manejo de tipos de error:**
   - `validation` → Mostrar en campo específico
   - `business` → Mostrar alerta contextual
   - `permission` → Redirigir a login o mostrar mensaje
   - `not_found` → Actualizar vista o mostrar alternativa
   - `server` → Mostrar opción de reintentar con error_id

2. **Mostrar detalles:**
   - Usar `error` como mensaje principal
   - Mostrar `details` como información adicional
   - Incluir `error_id` para reportes
   - Proporcionar sugerencias de solución

3. **Validación preventiva:**
   - Validar en frontend antes de enviar al backend
   - Usar mismas reglas que backend
   - Proporcionar feedback inmediato

---

## Ejemplos de Código

### Backend: Generar Error Estandarizado

```python
from utils import error_response, validate_integer_range

# Validar cantidad
quantity_validation = validate_integer_range(
    quantity, 
    min_val=1, 
    max_val=1000, 
    field_name='Cantidad'
)

if not quantity_validation['valid']:
    return error_response(
        error_type='validation',
        message=quantity_validation['message'],
        details='La cantidad debe ser un número entero entre 1 y 1000 unidades',
        field='quantity',
        value_received=quantity,
        min_allowed=1,
        max_allowed=1000,
        log_context={'sale_id': sale_id, 'product_id': product_id}
    )
```

### Frontend: Manejar Error

```javascript
try {
  const response = await fetch('/api/sales/123/items', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ product_id: 1, quantity: 5 })
  });
  
  if (!response.ok) {
    const errorData = await response.json();
    
    switch (errorData.type) {
      case 'validation':
        // Mostrar error en campo específico
        showFieldError(errorData.field, errorData.error);
        break;
      
      case 'business':
        // Mostrar alerta con detalles
        showAlert(errorData.error, errorData.details);
        break;
      
      case 'permission':
        // Redirigir a login
        window.location.href = '/auth/login';
        break;
      
      case 'not_found':
        // Actualizar vista
        refreshProductList();
        showAlert(errorData.error);
        break;
      
      case 'server':
        // Mostrar opción de reintentar con error_id
        showRetryDialog(errorData.error, errorData.error_id);
        break;
    }
  }
} catch (error) {
  // Error de red
  showAlert('Error de conexión. Verifique su conexión a internet.');
}
```

---

## Soporte y Contacto

Para reportar errores o solicitar asistencia:

1. **Incluir error_id** si está disponible
2. **Describir pasos** para reproducir el error
3. **Adjuntar logs** si tiene acceso al servidor
4. **Indicar contexto:** usuario, rol, operación intentada

El `error_id` permite rastrear el error exacto en los logs del sistema para un diagnóstico rápido.

---

**Fin de la documentación**
