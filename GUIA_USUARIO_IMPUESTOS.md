# Guía Rápida: Configuración de Impuestos en Four One POS

## Para Usuarios Finales y Operadores del Sistema

Esta guía te ayudará a configurar correctamente los impuestos en tus productos para cumplir con las regulaciones fiscales de República Dominicana.

---

## 📋 Conceptos Básicos

### ¿Qué son los Tipos de Impuestos?

El sistema maneja tres categorías de cargos:

1. **IMPUESTOS (TAX)** - Obligaciones fiscales con DGII (ITBIS)
2. **CARGOS DE SERVICIO (SERVICE_CHARGE)** - Propina legal del 10%
3. **OTROS (OTHER)** - Otros cargos especiales

---

## 🎯 Configuración Correcta por Tipo de Producto

### Productos Gravados (con ITBIS)

**Ejemplo: Cerveza Nacional**
- ✅ **UN SOLO** ITBIS: "ITBIS 18% (Exclusivo)"
- ✅ Propina 10% (opcional)
- ❌ **NUNCA** múltiples ITBIS al mismo producto

**Ejemplo: Comida del Menú**
- ✅ **UN SOLO** ITBIS: "ITBIS 18% (Inclusivo)"
- ✅ Propina 10%
- ❌ **NUNCA** mezclar inclusivo y exclusivo

### Productos Exentos

**Ejemplo: Arroz, Productos Básicos**
- ✅ ITBIS Exento
- ✅ Propina 10% (opcional)
- ❌ **NO** agregar ITBIS normal si es exento

### Productos con Tasa Reducida

**Ejemplo: Productos Médicos, Ciertos Alimentos**
- ✅ ITBIS 16% (Reducido)
- ✅ Propina 10% (opcional)
- ❌ **NO** combinar con ITBIS 18%

---

## ⚠️ Errores Comunes y Cómo Evitarlos

### ❌ ERROR 1: Múltiples ITBIS en un Producto
**Incorrecto:**
```
Producto: Cerveza
- ITBIS 18% (Inclusivo)
- ITBIS 18% (Exclusivo)  ← ¡ERROR!
```

**Correcto:**
```
Producto: Cerveza
- ITBIS 18% (Exclusivo)  ✓
- Propina 10%  ✓
```

### ❌ ERROR 2: Mezclar Inclusivo/Exclusivo
**Incorrecto:**
```
Producto: Comida
- ITBIS 18% (Inclusivo)
- ITBIS 16% (Exclusivo)  ← ¡ERROR!
```

**Correcto:**
```
Producto: Comida
- ITBIS 18% (Inclusivo)  ✓
- Propina 10%  ✓
```

### ❌ ERROR 3: Productos sin Configuración Fiscal
**Incorrecto:**
```
Producto: Whisky
(Sin impuestos configurados)  ← ¡ERROR!
```

**Correcto:**
```
Producto: Whisky
- ITBIS 18% (Exclusivo)  ✓
```

---

## 🔍 Cómo Usar el Panel de Auditoría Fiscal

El sistema incluye un panel de auditoría que te ayuda a identificar problemas:

### Acceder al Panel
1. Inicia sesión como Administrador
2. Ve a **Menú → Auditoría Fiscal**
3. Revisa el **Puntaje de Cumplimiento**

### Interpretar el Puntaje

- **100 puntos**: ✅ Configuración perfecta
- **80-99 puntos**: ⚠️ Revisar advertencias menores
- **60-79 puntos**: ⚠️ Problemas importantes a corregir
- **Menos de 60**: ❌ Configuración crítica incorrecta

### Problemas que Detecta el Panel

1. **Productos sin configuración fiscal**
   - Acción: Agregar ITBIS apropiado a cada producto

2. **Múltiples ITBIS por producto**
   - Acción: Eliminar impuestos duplicados, dejar solo UNO

3. **Mezcla de tipos inclusivo/exclusivo**
   - Acción: Usar solo UN tipo por producto

4. **Tax Types inactivos en productos activos**
   - Acción: Reemplazar con tax types activos

---

## 📊 Casos de Uso Prácticos

### Caso 1: Nuevo Producto - Cerveza Importada
1. Crear producto "Cerveza Importada"
2. Asignar **UN SOLO** impuesto: "ITBIS 18% (Exclusivo)"
3. Agregar "Propina 10%" si aplica
4. Verificar en el panel que no hay advertencias

### Caso 2: Corregir Producto con Error
1. Identificar producto en panel de auditoría
2. Ir a **Inventario → Productos**
3. Editar el producto problemático
4. Eliminar impuestos duplicados
5. Dejar **UN SOLO** ITBIS correcto
6. Guardar y verificar en panel de auditoría

### Caso 3: Producto Exento (Arroz)
1. Crear/editar producto "Arroz"
2. Asignar **SOLO**: "ITBIS Exento"
3. **NO** agregar otros ITBIS
4. Guardar

---

## 🛡️ Reglas de Oro del Sistema

### Regla #1: UN Solo ITBIS por Producto
- Cada producto puede tener **MÁXIMO UN** tipo de ITBIS
- El sistema **bloqueará** intentos de agregar múltiples ITBIS

### Regla #2: NO Mezclar Inclusivo/Exclusivo
- Si usas ITBIS Inclusivo, **TODOS** los impuestos fiscales deben ser inclusivos
- Si usas ITBIS Exclusivo, **TODOS** los impuestos fiscales deben ser exclusivos

### Regla #3: Propina es Opcional
- La Propina 10% NO es un impuesto fiscal
- Se puede combinar con cualquier ITBIS
- Es opcional según el tipo de negocio

### Regla #4: Productos Activos = Configuración Activa
- Si un producto está activo, sus impuestos deben estar activos
- El sistema **advertirá** si hay tax types inactivos

---

## 📞 Preguntas Frecuentes

### ¿Qué diferencia hay entre Inclusivo y Exclusivo?

**ITBIS Inclusivo (18% ya incluido en el precio):**
- Precio mostrado: RD$118.00
- ITBIS calculado: RD$18.00
- Cliente paga: RD$118.00
- Ejemplo: Menú de comida con precio final

**ITBIS Exclusivo (18% se agrega al precio):**
- Precio base: RD$100.00
- ITBIS calculado: RD$18.00
- Cliente paga: RD$118.00
- Ejemplo: Bebidas en barra

### ¿Puedo tener productos sin ITBIS?

Solo si son **productos exentos** según la ley:
- Productos de canasta básica
- Productos médicos específicos
- Otros casos especiales de exención

Para estos casos, usa "ITBIS Exento".

### ¿Qué hago si el panel muestra errores?

1. Lee el mensaje de error específico
2. Ve a **Inventario → Productos**
3. Busca el producto mencionado
4. Corrige según esta guía
5. Verifica nuevamente en el panel

### ¿Con qué frecuencia debo revisar el panel?

- **Diario**: Si se agregan productos nuevos frecuentemente
- **Semanal**: En operación normal
- **Antes de cierre fiscal**: Siempre antes de generar reportes 606/607

---

## ✅ Checklist de Verificación

Antes de poner productos en venta, verifica:

- [ ] Cada producto tiene **UN SOLO** ITBIS asignado
- [ ] NO hay mezcla de inclusivo/exclusivo en el mismo producto
- [ ] Todos los tax types usados están **activos**
- [ ] El panel de auditoría muestra **100 puntos** o explica las excepciones
- [ ] Los productos exentos usan **solo** "ITBIS Exento"
- [ ] La propina 10% está configurada donde aplica

---

## 🚨 En Caso de Emergencia

Si el panel de auditoría muestra **puntaje bajo** antes de un cierre fiscal:

1. **NO entres en pánico**
2. Lee cada advertencia específica
3. Corrige productos uno por uno
4. Prioriza productos **más vendidos**
5. Verifica después de cada corrección
6. Contacta soporte si necesitas ayuda urgente

---

## 📚 Recursos Adicionales

- **GUIA_TIPOS_IMPUESTOS.md**: Guía técnica completa (para administradores)
- **Panel de Auditoría**: Herramienta de verificación en tiempo real
- **ERRORES_LOGICA_FUNCIONAL.md**: Historial de mejoras y correcciones

---

**Última actualización**: Octubre 2025 (FASE 3 completada)
**Versión del sistema**: Four One POS v2.0

*Esta guía es parte del sistema de cumplimiento fiscal integrado de Four One POS.*
