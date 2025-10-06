# Plan de Mejoras - Sistema POS para Bar

## 🎯 Objetivo
Optimizar el sistema POS para operación eficiente de bar, eliminando funcionalidades de restaurante/cocina y agregando gestión de tabs y división de cuentas.

---

## 📋 Problemas Identificados

### 1. Sistema de Mesas/Órdenes Ineficiente
- **Problema**: Usa estados de cocina innecesarios (NOT_SENT, SENT_TO_KITCHEN, IN_PREPARATION, READY, SERVED)
- **Impacto**: Flujo complicado para un bar donde no hay preparación en cocina
- **Solución**: Simplificar a estados relevantes para bar

### 2. No Hay Sistema de Tabs
- **Problema**: Cada consumo crea venta nueva o requiere finalizar la anterior
- **Impacto**: No se pueden ir agregando bebidas a cuenta abierta de cliente/mesa
- **Solución**: Implementar tabs/cuentas abiertas que permitan agregar items

### 3. División de Cuenta No Funciona
- **Problema**: Función `splitBill()` solo muestra alerta, no está implementada
- **Impacto**: Grupos de amigos no pueden dividir fácilmente la cuenta
- **Solución**: Implementar división por personas, por items, o equitativa

### 4. Validación de Stock Solo al Finalizar
- **Problema**: Usuario puede agregar productos al carrito sin saber si hay stock
- **Impacto**: Error solo al intentar pagar, mala experiencia de usuario
- **Solución**: Validar y mostrar stock disponible en tiempo real

### 5. Flujo de "Enviar a Cocina" Innecesario
- **Problema**: Botón y lógica de enviar orden a cocina no aplica para bar
- **Impacto**: Pasos extra innecesarios en el flujo de trabajo
- **Solución**: Simplificar flujo mesero → cobrar directo

---

## ✅ Mejoras a Implementar

### **PRIORIDAD 1: Sistema de Tabs/Cuentas Abiertas**

#### Backend - Nuevos Endpoints
- `POST /api/tabs/open` - Abrir tab por nombre cliente o número mesa
  - Parámetros: `customer_name`, `table_id`, `user_id`
  - Retorna: `tab_id`, `created_at`
  
- `GET /api/tabs/active` - Listar todos los tabs abiertos
  - Retorna: Lista de tabs con totales parciales y tiempo abierto
  
- `GET /api/tabs/{tab_id}` - Obtener detalles de tab específico
  - Retorna: Items, subtotal, impuestos, total actual
  
- `POST /api/tabs/{tab_id}/close` - Cerrar tab y preparar para pago
  - Convierte tab a Sale pendiente
  - Retorna: `sale_id` para finalizar

**NOTA:** Los tabs NO tienen endpoints dedicados para agregar/quitar/modificar items. En su lugar, reutilizan los endpoints existentes de sales:
- Agregar item: `POST /api/sales/{id}/items` (funciona con status='pending' O 'tab_open')
- Quitar item: `DELETE /api/sales/{id}/items/{item_id}` (funciona con status='pending' O 'tab_open')
- Modificar cantidad: `PUT /api/sales/{id}/items/{item_id}/quantity` (funciona con status='pending' O 'tab_open')

#### Lógica de Negocio
1. Tab es una venta con `status='tab_open'` (nuevo estado)
2. Items se agregan sin finalizar venta
3. Al cerrar tab, cambia a `status='pending'` para finalización
4. Validar stock en cada agregado, no solo al final

#### Frontend - Meseros
- Botón "Abrir Tab" en vista de mesas
- Modal para nombre/cliente
- Vista de tab actual con items y total
- Botón "Agregar consumo" permanente
- Botón "Cerrar y Cobrar" cuando cliente lo pida

---

### **PRIORIDAD 2: División de Cuenta**

#### Backend - Endpoint de División
- `POST /api/sales/{sale_id}/split`
  - Parámetros:
    ```json
    {
      "split_type": "equal|by_items|custom",
      "num_people": 3,  // para equal
      "splits": [       // para by_items o custom
        {
          "items": [1, 3, 5],
          "customer_name": "Juan"
        },
        {
          "items": [2, 4],
          "customer_name": "María"
        }
      ]
    }
    ```
  - Proceso:
    1. Validar venta existe y está pendiente
    2. Crear N ventas nuevas según división
    3. Copiar items a cada venta según corresponda
    4. Marcar venta original como `status='split_parent'`
    5. Vincular ventas hijas con `parent_sale_id`
    6. Retornar IDs de ventas creadas

#### Tipos de División
1. **Equitativa** (`equal`):
   - Total / N personas
   - Todos pagan lo mismo
   
2. **Por Items** (`by_items`):
   - Asignar items específicos a cada persona
   - Cada quien paga sus consumos
   
3. **Personalizada** (`custom`):
   - Porcentajes específicos
   - Montos fijos por persona

#### Frontend
- Botón "Dividir Cuenta" en vista de mesa
- Modal con opciones de división:
  - Input: número de personas
  - O seleccionar items por persona
- Mostrar preview de división antes de confirmar
- Generar ventas separadas listas para cobrar

---

### **PRIORIDAD 3: Validación de Stock en Tiempo Real**

#### Backend - Endpoint de Stock
- `GET /api/products/{product_id}/stock`
  - Retorna: `stock_available`, `is_available` (bool)
  
- Modificar `POST /api/sales/{sale_id}/items`:
  - Validar stock ANTES de agregar
  - Si no hay suficiente, retornar error con stock actual
  - Respuesta: `{ "error": "Stock insuficiente. Disponible: X" }`

#### Frontend - POS
- Agregar badge de stock en tarjeta de producto:
  ```
  Stock: 15 ✅
  Stock: 3 ⚠️ (pocas unidades)
  Agotado ❌
  ```
- Deshabilitar botón si stock = 0
- Al agregar al carrito, validar contra stock actual
- Mostrar alerta si stock cambió desde que cargó la página

#### Frontend - Meseros
- Igual que POS, mostrar disponibilidad
- Al intentar agregar sin stock, sugerir alternativas
- Notificar a bartender/gerente cuando producto se agota

---

### **PRIORIDAD 4: Simplificar Flujo de Meseros**

#### Cambios en Lógica
1. **Eliminar estados de cocina innecesarios**:
   - Quitar: NOT_SENT, SENT_TO_KITCHEN, IN_PREPARATION, READY
   - Mantener solo: SERVED (opcional para tracking)
   - `order_status` puede ser NULL para bar

2. **Flujo simplificado**:
   ```
   Mesa → Abrir Tab → Agregar Consumos → Cerrar Tab → Cajero Cobra
   ```

3. **Modificar template `waiter/table_detail.html`**:
   - Quitar botón "Enviar a Cocina"
   - Cambiar "Cerrar Mesa" por "Cerrar Tab y Cobrar"
   - Eliminar badges de estado de cocina
   - Mostrar solo: tiempo de tab abierto, total actual

#### Backend - Rutas a Modificar
- `/api/sales/{sale_id}/send-to-kitchen` → Marcar como DEPRECATED
- `/api/tables/{table_id}/close` → Simplificar lógica
  - Solo cambiar status mesa a available
  - Marcar venta como pending para cajero

#### Frontend - Vista de Mesero
- Remover función `sendToKitchen()`
- Simplificar `closeTable()`:
  - Directo a pending sin estados intermedios
  - Mensaje: "Tab cerrado, enviar a caja para cobrar"

---

## 🔧 Cambios en Base de Datos

### Nuevos Campos en Sale
```sql
ALTER TABLE sales ADD COLUMN parent_sale_id INTEGER REFERENCES sales(id);
ALTER TABLE sales ADD COLUMN split_type VARCHAR(20);  -- 'equal', 'by_items', 'custom'
```

### Nuevos Valores en Enum
```python
# En models.py, agregar a SaleStatus (o crear nuevo enum):
class SaleStatus(enum.Enum):
    PENDING = "pending"
    TAB_OPEN = "tab_open"        # NUEVO: Tab abierto
    SPLIT_PARENT = "split_parent"  # NUEVO: Venta que se dividió
    COMPLETED = "completed"
    CANCELLED = "cancelled"
```

---

## 📊 Endpoints API - Resumen

### Tabs
- `POST /api/tabs/open` - Abrir tab
- `GET /api/tabs/active` - Listar tabs abiertos  
- `GET /api/tabs/{id}` - Ver tab
- `POST /api/tabs/{id}/close` - Cerrar tab
- **Item Management:** Usa endpoints existentes de sales (POST/DELETE/PUT /api/sales/{id}/items)

### División de Cuenta
- `POST /api/sales/{id}/split` - Dividir venta

### Stock
- `GET /api/products/{id}/stock` - Consultar stock
- Modificar `POST /api/sales/{id}/items` para validar stock

### Simplificación
- Deprecar `/api/sales/{id}/send-to-kitchen`
- Simplificar `/api/tables/{id}/close`

---

## 🎯 Orden de Implementación Sugerido

1. ✅ **Stock en tiempo real** (más simple, alto impacto) - **COMPLETADO**
   - ✅ Endpoint GET stock
   - ✅ Validación en add item
   - ✅ UI mostrando disponibilidad

2. ✅ **Sistema de Tabs** (crítico para bar) - **COMPLETADO**
   - ✅ Modelo actualizado (parent_sale_id, split_type, nuevos status)
   - ✅ Endpoints de tabs (open, active, get, close)
   - ✅ Validaciones actualizadas para permitir modificar items en tabs
   - ✅ UI meseros (abrir tab, agregar items, cerrar tab)
   - ✅ Tabs reutilizan endpoints de sales (sin duplicación)

3. ✅ **División de cuenta** (funcionalidad clave) - **COMPLETADO**
   - ✅ Endpoint POST /api/sales/{sale_id}/split
   - ✅ Lógica de división (equal, by_items, custom)
   - ✅ UI de división con modal interactivo
   - ✅ Validaciones y preview de divisiones

4. ✅ **Simplificar flujo meseros** (limpieza final) - **COMPLETADO**
   - ✅ Removidos estados de cocina de templates
   - ✅ Templates actualizados (meseros y admin)
   - ✅ Endpoints de cocina marcados como deprecados
   - ✅ Flujo simplificado: Mesero → Cajero directo

---

## 📝 Notas de Implementación

### Validaciones Importantes
- Tab solo puede tener un estado a la vez
- No se puede dividir venta ya dividida
- Stock debe validarse con locks para evitar race conditions
- Tabs antiguos (>4 horas) deben alertar al gerente

### Compatibilidad
- Mantener compatibilidad con ventas existentes
- Tabs son ventas con status especial
- División crea ventas normales que siguen flujo existente

### Testing
- Probar concurrencia en validación de stock
- Probar división con diferentes cantidades de items
- Probar tabs con múltiples meseros
- Validar que NCF se asigna solo en venta final, no en tabs

---

## ✅ Criterios de Éxito

1. **Tabs funcionando**:
   - Mesero puede abrir tab y agregar consumos
   - Tab mantiene total actualizado
   - Cierre de tab es fluido

2. **División implementada**:
   - Grupo puede dividir cuenta equitativamente
   - Se puede dividir por items individuales
   - Cada sub-venta genera NCF propio

3. **Stock visible**:
   - Productos muestran disponibilidad
   - No se puede agregar productos sin stock
   - Alertas cuando stock < mínimo

4. **Flujo simplificado**:
   - No hay referencias a cocina
   - Mesero → Cajero es directo
   - Sin pasos innecesarios

---

## 🚀 Beneficios Esperados

- **Servicio más rápido**: Menos clics para operaciones comunes
- **Menos errores**: Validación de stock en tiempo real
- **Mejor experiencia**: Clientes pueden dividir fácilmente
- **Mayor eficiencia**: Tabs abiertos permiten flujo natural de bar
- **Código más limpio**: Eliminar funcionalidades innecesarias
