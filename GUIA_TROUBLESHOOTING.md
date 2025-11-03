# Guía de Troubleshooting - Sistema POS

**Versión:** 1.0  
**Última actualización:** 3 de noviembre de 2025  
**Audiencia:** Usuarios del sistema (cajeros, meseros, administradores)

---

## Índice

1. [Problemas Comunes en Ventas](#problemas-comunes-en-ventas)
2. [Problemas de Stock e Inventario](#problemas-de-stock-e-inventario)
3. [Problemas Fiscales (NCF y RNC)](#problemas-fiscales-ncf-y-rnc)
4. [Problemas de Permisos y Acceso](#problemas-de-permisos-y-acceso)
5. [Problemas de Pago](#problemas-de-pago)
6. [Mensajes de Error del Sistema](#mensajes-de-error-del-sistema)
7. [Preguntas Frecuentes](#preguntas-frecuentes)

---

## Problemas Comunes en Ventas

### ❌ "No se puede agregar más de 100 productos al carrito"

**Causa:** El sistema limita el carrito a 100 productos diferentes para mantener el rendimiento.

**Soluciones:**
1. **Finalizar la venta actual** y crear una nueva venta para los productos adicionales
2. **Aumentar la cantidad** de productos existentes en lugar de agregar el mismo producto varias veces
3. **Dividir en múltiples ventas** si realmente necesita más de 100 productos diferentes

---

### ❌ "La cantidad debe estar entre 1 y 1000 unidades"

**Causa:** El sistema limita la cantidad máxima por producto a 1000 unidades para prevenir errores de digitación.

**Soluciones:**
1. **Verificar la cantidad:** Asegúrese de no haber agregado ceros adicionales por error
2. **Dividir en múltiples ventas:** Si realmente necesita más de 1000 unidades del mismo producto, crear múltiples ventas
3. **Contactar al administrador:** Para ventas especiales de más de 1000 unidades

**Ejemplo:**
```
✗ Incorrecto: Cantidad = 10000 (diez mil)
✓ Correcto: Cantidad = 100 (cien)
```

---

### ❌ "No se puede modificar una venta finalizada"

**Causa:** Una vez finalizada una venta y asignado un NCF, no se puede modificar por razones fiscales.

**Soluciones:**
1. **Cancelar la venta:** Use la función "Cancelar Venta" para anularla (esto genera un NCF de nota de crédito)
2. **Crear una nueva venta:** Para la venta correcta
3. **Verificar antes de finalizar:** Revise cuidadosamente los productos y cantidades antes de completar la venta

---

### ❌ "El carrito está vacío. Agregue productos antes de finalizar"

**Causa:** Intento de finalizar una venta sin productos.

**Solución:**
1. **Agregar productos al carrito** antes de intentar finalizar la venta
2. Si los productos desaparecieron, **refrescar la página** y volver a agregarlos

---

## Problemas de Stock e Inventario

### ❌ "Stock insuficiente para [Nombre del Producto]"

**Causa:** El producto no tiene suficientes unidades en inventario para completar la venta.

**Mensaje completo:**
```
Stock insuficiente para Coca Cola 2L
Disponible: 5 unidades
Solicitado: 10 unidades
```

**Soluciones:**
1. **Reducir la cantidad** solicitada al stock disponible (en el ejemplo, máximo 5 unidades)
2. **Verificar stock en tiempo real:** El sistema muestra el stock disponible en cada producto
3. **Reabastecer el producto:** Contactar al encargado de inventario
4. **Sugerir producto alternativo:** Ofrecer al cliente un producto similar con stock disponible

---

### ❌ "Producto no disponible (stock: 0)"

**Causa:** El producto está agotado.

**Soluciones:**
1. **No agregar el producto** al carrito
2. **Verificar próximo reabastecimiento** con el encargado de inventario
3. **Ofrecer producto alternativo** al cliente
4. **Notificar al administrador:** Para activar alerta de stock bajo

---

## Problemas Fiscales (NCF y RNC)

### ❌ "El NCF de Crédito Fiscal requiere nombre del cliente"

**Causa:** Según normas DGII, el NCF de Crédito Fiscal debe incluir datos del cliente.

**Soluciones:**
1. **Ingresar nombre del cliente:** Campo obligatorio para NCF de crédito fiscal
2. **Ingresar RNC del cliente:** También obligatorio para crédito fiscal
3. **Usar NCF de Consumo:** Si el cliente no requiere crédito fiscal

**Cuándo usar cada tipo de NCF:**
- **Consumo:** Ventas a consumidores finales sin RNC
- **Crédito Fiscal:** Ventas a empresas que requieren deducción fiscal (requiere nombre y RNC)
- **Sin Comprobante:** Ventas exentas de NCF

---

### ❌ "RNC debe tener 9 u 11 dígitos"

**Causa:** RNC con formato incorrecto.

**Formatos válidos:**
- **9 dígitos:** Empresas (ejemplo: `123-45678-9`)
- **11 dígitos:** Personas físicas (ejemplo: `012-3456789-0`)

**Soluciones:**
1. **Verificar el RNC:** Solicitar al cliente su RNC correcto
2. **Formateo automático:** El sistema formatea automáticamente con guiones
3. **Ejemplos comunes:**
   ```
   ✓ 123456789 → Se formatea a: 123-45678-9 (empresa)
   ✓ 01234567890 → Se formatea a: 012-3456789-0 (persona física)
   ✗ 12345 → Error: muy corto
   ```

---

### ❌ "RNC de 9 dígitos debe empezar con 1, 3, 4 o 5"

**Causa:** RNC de empresa con primer dígito inválido.

**Soluciones:**
1. **Verificar el RNC** con el cliente
2. **Primer dígito válido para empresas:**
   - `1`: Persona Jurídica Nacional
   - `3`: Persona Jurídica Extranjera
   - `4`: Entidad Gubernamental
   - `5`: Contribuyente Especial

**Ejemplo:**
```
✓ 123456789 (empieza con 1 - válido)
✓ 301234567 (empieza con 3 - válido)
✗ 223456789 (empieza con 2 - inválido)
```

---

## Problemas de Permisos y Acceso

### ❌ "Debe iniciar sesión para acceder a este recurso"

**Causa:** Sesión expirada o no iniciada.

**Soluciones:**
1. **Iniciar sesión** con su usuario y contraseña
2. **Verificar credenciales:** Asegúrese de usar las credenciales correctas
3. **Contactar al administrador:** Si olvidó su contraseña

---

### ❌ "Solo cajeros y administradores pueden finalizar ventas"

**Causa:** Meseros no tienen permiso para finalizar ventas (solo crearlas).

**Soluciones:**
1. **Solicitar a un cajero** que finalice la venta
2. **Flujo correcto para meseros:**
   - Mesero: Crea la venta y agrega productos
   - Cajero: Finaliza la venta y procesa el pago

**Roles y permisos:**
| Rol | Crear Venta | Agregar Productos | Finalizar Venta |
|-----|-------------|-------------------|-----------------|
| Administrador | ✓ | ✓ | ✓ |
| Cajero | ✓ | ✓ | ✓ |
| Mesero | ✓ | ✓ | ✗ |

---

## Problemas de Pago

### ❌ "Método de pago inválido"

**Causa:** Método de pago no soportado por el sistema.

**Métodos de pago válidos:**
- `Efectivo` (cash)
- `Tarjeta` (card)
- `Transferencia` (transfer)

**Solución:**
1. **Seleccionar un método válido** de la lista desplegable
2. **No escribir manualmente:** Usar los botones o selector del sistema

---

### ❌ "Efectivo recibido debe ser mayor o igual al total"

**Causa:** El efectivo recibido es menor que el total de la venta.

**Solución:**
1. **Verificar el monto ingresado:** Asegúrese de haber digitado correctamente
2. **Solicitar pago completo al cliente**
3. **Ejemplo:**
   ```
   Total de venta: RD$ 500.00
   ✗ Efectivo recibido: RD$ 400.00 (insuficiente)
   ✓ Efectivo recibido: RD$ 500.00 o más
   ```

---

### ❌ "El efectivo recibido debe estar entre RD$ 0 y RD$ 1,000,000"

**Causa:** Prevención de errores de digitación en montos muy altos.

**Soluciones:**
1. **Verificar el monto:** Probablemente agregó ceros de más
2. **Ejemplo común de error:**
   ```
   ✗ RD$ 5,000,000 (cinco millones - probablemente un error)
   ✓ RD$ 500 (quinientos pesos - correcto)
   ```
3. **Para ventas >RD$ 1,000,000:** Contactar al administrador para autorización especial

---

## Mensajes de Error del Sistema

### ❌ "Error interno del servidor. Código: A1B2C3D4"

**Causa:** Error inesperado en el sistema.

**Soluciones:**
1. **Anotar el código de error:** En este ejemplo `A1B2C3D4`
2. **Reintentar la operación:** A veces errores temporales se resuelven solos
3. **Reportar al administrador:** Con el código de error para rastreo en logs
4. **Refrescar la página:** Si el error persiste

**Información importante a reportar:**
- Código de error (ej: `A1B2C3D4`)
- Hora aproximada del error
- Operación que estaba realizando
- Usuario que experimentó el error

---

### ⚠️ "Error de conexión. Verifique su conexión a internet"

**Causa:** Pérdida de conexión con el servidor.

**Soluciones:**
1. **Verificar conexión WiFi/Ethernet**
2. **Verificar que el servidor esté en línea**
3. **Reintentar la operación** una vez restablecida la conexión
4. **No finalizar ventas sin conexión:** Los datos podrían perderse

---

## Preguntas Frecuentes

### 💡 ¿Cómo sé si un producto tiene stock suficiente?

El sistema muestra el stock disponible en tiempo real al agregar productos. Si el botón "Agregar" está deshabilitado o el producto tiene un indicador rojo, significa que no hay stock.

---

### 💡 ¿Qué hago si me equivoqué al finalizar una venta?

Debe **cancelar la venta** usando la función correspondiente. Esto genera un NCF de nota de crédito y registra la cancelación. Luego puede crear una nueva venta con los datos correctos.

---

### 💡 ¿Puedo modificar la cantidad de un producto después de agregarlo?

**Sí**, siempre que la venta no esté finalizada. Use los botones `+` y `-` en el carrito o haga clic en la cantidad para editarla directamente.

---

### 💡 ¿Qué tipo de NCF debo usar para cada venta?

| Situación | Tipo de NCF |
|-----------|-------------|
| Cliente sin RNC, consumidor final | **Consumo** |
| Empresa que requiere crédito fiscal | **Crédito Fiscal** (requiere nombre y RNC) |
| Venta a entidad gubernamental | **Gubernamental** |
| Cliente no requiere comprobante | **Sin Comprobante** |

---

### 💡 ¿Por qué el sistema me pide confirmación para vaciar el carrito?

Para **prevenir borrado accidental**. El sistema muestra cuántos productos y unidades se perderían. Esta es una medida de protección.

---

### 💡 ¿Por qué el sistema me pide confirmación para ventas mayores a RD$ 100,000?

Para **prevenir errores de digitación** en ventas de monto elevado. Revise que el total sea correcto antes de confirmar.

---

### 💡 ¿Cómo reporto un error del sistema?

1. **Anotar el código de error** (si se muestra)
2. **Tomar captura de pantalla** si es posible
3. **Anotar:**
   - Hora del error
   - Operación que realizaba
   - Pasos para reproducir el error
4. **Reportar al administrador** con toda la información

---

## Soporte Técnico

### Niveles de Soporte

**Nivel 1: Autoresolución**
- Consultar esta guía de troubleshooting
- Revisar mensajes de error
- Verificar validaciones del sistema

**Nivel 2: Cajero/Encargado**
- Problemas de permisos
- Problemas de stock
- Preguntas sobre NCF

**Nivel 3: Administrador**
- Errores del sistema
- Problemas de configuración
- Acceso y usuarios

**Nivel 4: Soporte Técnico**
- Errores con código de error
- Problemas de base de datos
- Errores críticos del servidor

---

## Consejos para Prevenir Errores

### ✅ Antes de Finalizar una Venta

- [ ] Verificar todos los productos y cantidades
- [ ] Revisar el total de la venta
- [ ] Confirmar método de pago con el cliente
- [ ] Para NCF Crédito Fiscal: verificar nombre y RNC del cliente
- [ ] Asegurarse de que hay stock suficiente

### ✅ Al Ingresar Datos

- [ ] RNC: 9 u 11 dígitos
- [ ] Cantidades: entre 1 y 1000 unidades
- [ ] Efectivo recibido: mayor o igual al total
- [ ] Verificar dos veces montos grandes (>RD$ 10,000)

### ✅ Gestión de Inventario

- [ ] Revisar alertas de stock bajo diariamente
- [ ] Notificar productos agotados al encargado
- [ ] Verificar stock antes de tomar pedidos grandes

---

## Mejores Prácticas

### 📌 Para Cajeros

1. **Verificar identidad en crédito fiscal:** Solicitar cédula o RNC al cliente
2. **Contar efectivo dos veces:** Antes de registrar en el sistema
3. **Revisar el cambio calculado:** Por el sistema antes de entregarlo
4. **No acumular ventas:** Finalizar cada venta antes de iniciar la siguiente

### 📌 Para Meseros

1. **Anotar número de mesa:** En cada pedido
2. **Verificar disponibilidad:** Antes de tomar el pedido
3. **Actualizar pedidos:** Si el cliente agrega o quita productos
4. **Coordinar con cajero:** Para finalización de ventas

### 📌 Para Administradores

1. **Revisar logs de error:** Diariamente (archivo `logs/pos_errors.log`)
2. **Monitorear stock bajo:** Dashboard de administración
3. **Capacitar usuarios:** En validaciones y mensajes de error
4. **Backup de datos:** Regular y automático

---

## Glosario de Términos

| Término | Significado |
|---------|-------------|
| **NCF** | Número de Comprobante Fiscal (requerido por DGII) |
| **RNC** | Registro Nacional del Contribuyente (cédula fiscal de empresas) |
| **DGII** | Dirección General de Impuestos Internos |
| **Stock** | Cantidad de unidades disponibles de un producto |
| **Crédito Fiscal** | NCF que permite a empresas deducir impuestos |
| **Error ID** | Código único de 8 caracteres para rastrear errores |

---

## Anexos

### Formato de RNC Válidos

**Empresas (9 dígitos):**
```
123-45678-9  → Persona Jurídica Nacional
301-23456-7  → Persona Jurídica Extranjera
401-23456-7  → Entidad Gubernamental
501-23456-7  → Contribuyente Especial
```

**Personas Físicas (11 dígitos):**
```
012-3456789-0  → Persona física con cédula
112-3456789-0  → Persona física con cédula
412-3456789-0  → Persona física con cédula
```

### Códigos de Área Telefónicos Válidos (RD)

- **809:** Original
- **829:** Segundo código de área
- **849:** Tercer código de área

**Formato:** `(809) 555-1234` o `+1 (809) 555-1234`

---

**Última actualización:** 3 de noviembre de 2025  
**Versión del sistema:** Compatible con todas las mejoras de manejo de errores (Fases 1-6)

Para asistencia adicional, contacte al administrador del sistema con el código de error si está disponible.
