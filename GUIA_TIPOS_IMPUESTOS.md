# Guía de Tipos de Impuestos y Cargos - Four One POS

## 📋 Descripción General

Este documento explica los diferentes tipos de impuestos y cargos disponibles en el sistema POS, cuándo usar cada uno, y cómo afectan los cálculos de precios según las normativas fiscales dominicanas.

---

## 🏛️ Impuestos Fiscales (ITBIS)

### 1. ITBIS 18% (Tasa Estándar)
**Cuándo usar:**
- ✅ Para la **mayoría de productos** que no califican para tasas reducidas o exenciones
- ✅ Productos de venta general
- ✅ Bebidas alcohólicas
- ✅ Comidas preparadas
- ✅ Servicios generales

**Cálculo:**
- El impuesto se **agrega al precio base**
- Precio final = Precio base + (Precio base × 0.18)

**Ejemplo:**
```
Producto: Cerveza
Precio base: RD$ 100.00
ITBIS 18%: RD$ 18.00
Precio final: RD$ 118.00
```

---

### 2. ITBIS 16% (Tasa Reducida)
**Cuándo usar:**
- ✅ **Lácteos** (leche, queso, yogurt)
- ✅ **Café** y derivados
- ✅ **Azúcar** y edulcorantes
- ✅ **Cacao** y chocolate

**Base legal:** Ley 253-12, Art. 343 - Productos de la canasta básica

**Cálculo:**
- El impuesto se **agrega al precio base**
- Precio final = Precio base + (Precio base × 0.16)

**Ejemplo:**
```
Producto: Café Latte
Precio base: RD$ 100.00
ITBIS 16%: RD$ 16.00
Precio final: RD$ 116.00
```

---

### 3. ITBIS 18% Incluido
**Cuándo usar:**
- ✅ Cuando el **precio ya incluye el impuesto**
- ✅ Cuando trabajas con precios finales (ej: menú con precios establecidos)
- ✅ Cuando importas productos con ITBIS incluido en el costo

**Cálculo (Regresivo):**
- Se calcula el precio base desde el precio final
- Precio base = Precio final / 1.18
- ITBIS = Precio final - Precio base

**Ejemplo:**
```
Producto: Combo Especial
Precio final: RD$ 118.00
Precio base: RD$ 100.00 (118 / 1.18)
ITBIS 18%: RD$ 18.00
```

**⚠️ Importante:** 
- El sistema automáticamente calcula el desglose para reportes fiscales
- Los recibos muestran el precio base y el ITBIS por separado

---

### 4. ITBIS Exento (0%)
**Cuándo usar:**
- ✅ Productos **exentos** por ley
- ✅ Medicamentos (con receta)
- ✅ Productos agrícolas básicos sin procesar
- ✅ Libros y material educativo
- ✅ Servicios de salud y educación

**Base legal:** Ley 253-12, Art. 344 - Exenciones

**Cálculo:**
- **No se aplica impuesto** (0%)
- Precio final = Precio base

**Ejemplo:**
```
Producto: Medicina (con receta)
Precio base: RD$ 100.00
ITBIS: RD$ 0.00
Precio final: RD$ 100.00
```

---

### 5. Sin Impuesto
**Cuándo usar:**
- ✅ Productos o servicios **fuera del alcance del ITBIS**
- ✅ Exportaciones
- ✅ Servicios financieros
- ✅ Transacciones específicas no gravadas

**Diferencia con ITBIS Exento:**
- **ITBIS Exento:** Producto normalmente gravado pero exento por ley (se reporta en DGII)
- **Sin Impuesto:** Producto no sujeto al ITBIS (no se reporta como exento)

**Cálculo:**
- **No se aplica impuesto** (0%)
- Precio final = Precio base

---

## 💰 Cargos por Servicio

### 6. Propina 10% (Ley 10%)
**Cuándo usar:**
- ✅ **Obligatorio** para restaurantes, bares y establecimientos de comida
- ✅ Servicio de mesa (meseros)
- ✅ Servicios de bar

**Base legal:** Ley 116-17 (Ley de Propina Legal)

**Cálculo Correcto (Normativa Dominicana):**
- La propina se calcula sobre **(subtotal + impuestos)**
- **NO** sobre el subtotal solamente

**Ejemplo Correcto:**
```
Subtotal productos: RD$ 300.00
ITBIS 18%: RD$ 54.00
Base para propina: RD$ 354.00 (subtotal + impuestos)
Propina 10%: RD$ 35.40
Total final: RD$ 389.40
```

**❌ Error Común (NO HACER):**
```
Subtotal: RD$ 300.00
Propina 10%: RD$ 30.00 (INCORRECTO - calcula solo sobre subtotal)
ITBIS: RD$ 54.00
Total: RD$ 384.00 (INCORRECTO)
```

**📌 Nota Importante:**
- La propina es un **cargo por servicio**, NO un impuesto
- Se distribuye entre el personal de servicio
- Debe aparecer separada en el recibo

---

## 🔄 Comparación Rápida

| Tipo | Tasa | Se Agrega al Precio | Incluido en Precio | Uso Principal |
|------|------|---------------------|-------------------|---------------|
| **ITBIS 18%** | 18% | ✅ Sí | ❌ No | Productos generales |
| **ITBIS 16%** | 16% | ✅ Sí | ❌ No | Lácteos, café, azúcar, cacao |
| **ITBIS 18% Incluido** | 18% | ❌ No | ✅ Sí | Precio final con impuesto incluido |
| **ITBIS Exento** | 0% | ❌ No | ❌ No | Productos exentos por ley |
| **Sin Impuesto** | 0% | ❌ No | ❌ No | Fuera del alcance ITBIS |
| **Propina 10%** | 10% | ✅ Sí | ❌ No | Cargo por servicio (sobre subtotal + impuestos) |

---

## 🧮 Ejemplos de Cálculos

### Ejemplo 1: Venta Simple (ITBIS 18%)
```
1x Cerveza Presidente - RD$ 100.00

Subtotal: RD$ 100.00
ITBIS 18%: RD$ 18.00
Propina 10%: RD$ 11.80 (calculada sobre 118.00)
Total: RD$ 129.80
```

### Ejemplo 2: Venta con Tasa Reducida
```
1x Café Latte - RD$ 80.00 (ITBIS 16%)

Subtotal: RD$ 80.00
ITBIS 16%: RD$ 12.80
Propina 10%: RD$ 9.28 (calculada sobre 92.80)
Total: RD$ 102.08
```

### Ejemplo 3: Venta con Precio Incluido
```
1x Combo Especial - RD$ 236.00 (ITBIS 18% Incluido)

Precio con impuesto: RD$ 236.00
Precio base: RD$ 200.00 (236 / 1.18)
ITBIS 18%: RD$ 36.00
Propina 10%: RD$ 23.60 (calculada sobre 236.00)
Total: RD$ 259.60
```

### Ejemplo 4: Venta Mixta (Múltiples Tasas)
```
1x Cerveza - RD$ 100.00 (ITBIS 18%)
1x Café Latte - RD$ 80.00 (ITBIS 16%)
1x Pan - RD$ 30.00 (ITBIS Exento)

Subtotal: RD$ 210.00
ITBIS Cerveza: RD$ 18.00
ITBIS Café: RD$ 12.80
ITBIS Pan: RD$ 0.00
Total Impuestos: RD$ 30.80

Base para propina: RD$ 240.80 (210 + 30.80)
Propina 10%: RD$ 24.08
Total final: RD$ 264.88
```

---

## ✅ Mejores Prácticas

### Configuración de Productos

1. **Productos Generales:**
   - Usar **ITBIS 18%** como predeterminado
   - Verificar que no califiquen para tasa reducida

2. **Productos de Canasta Básica:**
   - Verificar si califican para **ITBIS 16%**
   - Solo para lácteos, café, azúcar, cacao

3. **Productos con Precio Final:**
   - Usar **ITBIS 18% Incluido**
   - El sistema calculará automáticamente el desglose

4. **Productos Exentos:**
   - Usar **ITBIS Exento** solo si está respaldado por ley
   - Mantener documentación legal

5. **Propina:**
   - Activar por defecto en POS para restaurantes/bares
   - Se calcula automáticamente sobre (subtotal + impuestos)

### Reportes DGII

El sistema genera automáticamente:
- **Reporte 606:** Compras con desglose de ITBIS
- **Reporte 607:** Ventas con desglose de ITBIS
- **Recibos fiscales:** Con NCF y desglose de impuestos

---

## 📞 Soporte y Referencias

### Contactos para Consultas Fiscales
- **DGII (Dirección General de Impuestos Internos):** 809-689-3444
- **Contador/Auditor:** Consultar para casos específicos
- **Asesor Legal Fiscal:** Para exenciones y casos especiales

### Leyes y Normativas
- **Ley 253-12:** Código Tributario de la República Dominicana
- **Ley 116-17:** Ley de Propina Legal
- **Decreto 583-08:** Reglamento del ITBIS

### Recursos en Línea
- Portal DGII: https://www.dgii.gov.do
- Consultas de Exenciones: https://www.dgii.gov.do/legislacion
- Capacitación DGII: Talleres y seminarios disponibles

---

## 🔧 Configuración en el Sistema

### Acceso a Configuración de Impuestos
1. Ir a **Panel Administrativo**
2. Seleccionar **Configuración → Tipos de Impuestos**
3. Crear o editar tipos de impuestos
4. Asignar a productos según corresponda

### Asignación a Productos
1. Al crear/editar un producto
2. En la sección **"Configuración de Impuestos"**
3. Seleccionar el tipo de impuesto correcto
4. El sistema validará que al menos un impuesto esté seleccionado

### Validaciones del Sistema
- ✅ Todos los productos **deben** tener al menos un tipo de impuesto
- ✅ La propina se calcula automáticamente sobre (subtotal + impuestos)
- ✅ Los impuestos se separan de los cargos por servicio en reportes

---

**Última actualización:** 16 de Octubre, 2025  
**Versión del Sistema:** Four One POS v2.0  
**Fase Implementada:** Fase 2 - Mejoras de Sistema
