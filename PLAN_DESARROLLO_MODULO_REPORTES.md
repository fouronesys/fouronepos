# Plan de Desarrollo - Módulo de Reportes
## Sistema POS Four One - Funcionalidades Pendientes

**Fecha de creación:** 3 de noviembre de 2025  
**Última actualización:** 5 de noviembre de 2025  
**Estado:** En Progreso - FASE 1 y FASE 2 Completadas ✅  
**Prioridad:** Alta

---

## 📋 Resumen Ejecutivo

Este plan detalla el desarrollo de las funcionalidades del módulo de reportes que actualmente están marcadas como "en desarrollo". El objetivo es completar el sistema de reportes administrativos para proporcionar al cliente análisis completos de su operación.

---

## 🎯 Estado Actual del Módulo

### ✅ Funcionalidades Implementadas

1. **Reportes de Ventas por Período**
   - Reporte diario
   - Reporte semanal
   - Reporte mensual
   - Reporte anual
   - Reporte personalizado (rango de fechas)
   - Exportación a PDF ✅

2. **Reportes Fiscales DGII**
   - Reporte 606 (Compras)
   - Reporte 607 (Ventas)
   - Exportación a CSV ✅
   - Exportación a Excel ✅
   - Exportación a PDF (solo 607) ✅

### ⏳ Funcionalidades Pendientes (En Desarrollo)

**Ubicación:** `templates/admin/reports.html` - Línea 445

1. **Reporte de Productos Más Vendidos** - Selector existe pero muestra placeholder
2. **Reporte de Comprobantes NCF** - Selector existe pero muestra placeholder
3. **Reporte de Ventas por Usuario** - Selector existe pero muestra placeholder

**Ubicación adicional:** `templates/admin/products.html` - Líneas 251, 257

4. **Edición de Productos** - Función marcada como "en desarrollo"
5. **Eliminación de Productos** - Función marcada como "en desarrollo"

---

## 📊 Plan de Desarrollo

### FASE 1: Reporte de Productos Más Vendidos ✅ COMPLETADA
**Duración real:** 1 día  
**Fecha de completación:** 4 de noviembre de 2025  
**Archivos modificados:**
- `routes/admin.py` (nuevos endpoints agregados)
- `templates/admin/reports.html` (JavaScript implementado)
- `receipt_generator.py` (función PDF agregada)

#### Tareas:
- [x] 1.1. Crear endpoint `/admin/api/products-report` ✅
- [x] 1.2. Implementar consulta SQL para productos más vendidos ✅
- [x] 1.3. Agregar filtros por período (día, semana, mes, año, personalizado) ✅
- [x] 1.4. Crear función JavaScript en frontend para mostrar resultados ✅
- [x] 1.5. Diseñar vista de resultados con tabla y gráfico ✅
- [x] 1.6. Implementar exportación a PDF del reporte ✅
- [ ] 1.7. Implementar exportación a Excel del reporte (Pendiente - opcional)
- [ ] 1.8. Agregar pruebas unitarias del endpoint (Pendiente - recomendado)

#### Funcionalidades Implementadas:
✅ **Endpoint API completo** (`/admin/api/products-report`):
- Consultas SQL optimizadas con agregaciones (SUM, COUNT, AVG)
- Filtros por período: día, semana, mes, año, personalizado
- Control de acceso por roles (Administrador, Gerente, Cajero)
- Limitación configurable de resultados (10, 20, 50, 100)
- Cálculo de estadísticas avanzadas:
  - Ranking por cantidad vendida
  - Ranking por ingresos generados
  - Margen de ganancia por producto
  - Porcentaje sobre ventas totales
  - Estadísticas por categoría

✅ **Visualización Frontend** (reports.html):
- Tarjetas de resumen con métricas clave
- Gráfico de barras: Top 10 por cantidad vendida
- Gráfico de barras: Top 10 por ingresos
- Gráfico doughnut: Distribución por categoría
- Tabla de categorías con estadísticas
- Tabs con dos vistas: por cantidad y por ingresos
- Tablas detalladas con información completa de productos
- Indicadores visuales de margen de ganancia (colores)

✅ **Exportación a PDF** (`/admin/api/products-report/pdf`):
- Formato profesional con encabezado de empresa
- Resumen general de estadísticas
- Tabla detallada de productos más vendidos
- Sección de resumen por categoría
- Espacio para firma autorizada

#### Notas de Implementación:
- La función PDF (`generate_products_report_pdf`) sigue el mismo patrón que los reportes de ventas existentes
- Las visualizaciones usan Chart.js v4.4.0 ya incluido en el proyecto
- El código maneja correctamente casos sin datos y límites configurables
- Integración completa con el sistema de permisos existente

#### Datos a incluir:
- Ranking de productos por cantidad vendida
- Ranking de productos por ingresos generados
- Período de análisis
- Cantidad total vendida por producto
- Ingresos totales por producto
- Porcentaje sobre ventas totales
- Margen de ganancia por producto
- Comparación con período anterior

#### Visualizaciones:
- Tabla con top 10/20/50 productos
- Gráfico de barras de cantidad vendida
- Gráfico de pastel de distribución de ingresos
- Tendencia de ventas por producto en el tiempo

---

### FASE 2: Reporte de Comprobantes NCF ✅ COMPLETADA
**Duración real:** 1 día  
**Fecha de completación:** 5 de noviembre de 2025  
**Archivos modificados:**
- `routes/admin.py` (nuevos endpoints agregados)
- `templates/admin/reports.html` (JavaScript implementado)
- `receipt_generator.py` (función PDF agregada)

#### Tareas:
- [x] 2.1. Crear endpoint `/admin/api/ncf-report` ✅
- [x] 2.2. Implementar consulta SQL para comprobantes NCF ✅
- [x] 2.3. Agregar filtros por tipo de NCF (consumo, crédito fiscal, gubernamental) ✅
- [x] 2.4. Agregar filtros por estado (usado, cancelado, disponible) ✅
- [x] 2.5. Crear función JavaScript para mostrar resultados ✅
- [x] 2.6. Diseñar vista de resultados con estadísticas ✅
- [x] 2.7. Implementar alertas de rangos por agotarse ✅
- [x] 2.8. Implementar exportación a PDF del reporte ✅
- [ ] 2.9. Agregar pruebas unitarias del endpoint (Pendiente - recomendado)

#### Funcionalidades Implementadas:
✅ **Endpoint API completo** (`/admin/api/ncf-report`):
- Consultas SQL optimizadas sobre NCFSequence, NCFLedger y CancelledNCF
- Filtros por período: día, semana, mes, año, personalizado, todas las fechas
- Filtros por tipo de NCF: todos, consumo, crédito fiscal, gubernamental
- Filtros por estado: todos, usado, cancelado
- Control de acceso por roles (Administrador, Gerente, Cajero)
- Cálculo de estadísticas detalladas por tipo de NCF:
  - Total de secuencias activas e inactivas
  - NCF en rangos, utilizados, disponibles y cancelados
  - Porcentaje de utilización global y por tipo
  - Sistema de alertas automáticas (crítico: ≤20, advertencia: ≤100)
  
✅ **Visualización Frontend** (reports.html):
- Tarjetas de resumen con métricas clave
- Sistema de alertas visual (críticas en rojo, advertencias en amarillo)
- Gráfico doughnut: Utilización por tipo de NCF
- Gráfico de barras: Disponibilidad vs Utilizados por tipo
- Tabla de estadísticas detalladas por tipo de NCF
- Tabla de comprobantes emitidos recientes (límite 100)
- Indicadores de estado con badges (usado/cancelado)

✅ **Exportación a PDF** (`/admin/api/ncf-report/pdf`):
- Formato profesional con encabezado de empresa
- Resumen general de estadísticas
- Sección de alertas de secuencias destacada
- Tabla detallada de estadísticas por tipo
- Tabla de comprobantes emitidos recientes
- Espacio para firma autorizada

#### Notas de Implementación:
- La función PDF (`generate_ncf_report_pdf`) sigue el mismo patrón que los reportes existentes
- Las visualizaciones usan Chart.js v4.4.0 ya incluido en el proyecto
- El sistema de alertas es proactivo y detecta automáticamente rangos por agotarse
- Integración completa con el sistema de permisos existente
- El reporte muestra NCFs de NCFLedger (registro inmutable de emisiones)

---

### FASE 3: Reporte de Ventas por Usuario 🟡 MEDIA PRIORIDAD
**Duración estimada:** 1-2 días  
**Archivos a modificar:**
- `routes/admin.py` (nuevo endpoint)
- `templates/admin/reports.html` (JavaScript)

#### Tareas:
- [ ] 3.1. Crear endpoint `/admin/api/users-sales-report`
- [ ] 3.2. Implementar consulta SQL para ventas por usuario
- [ ] 3.3. Agregar filtros por período
- [ ] 3.4. Agregar filtros por rol (cajero, mesero, administrador)
- [ ] 3.5. Crear función JavaScript para mostrar resultados
- [ ] 3.6. Diseñar vista de resultados con ranking
- [ ] 3.7. Implementar exportación a PDF del reporte
- [ ] 3.8. Agregar pruebas unitarias del endpoint

#### Datos a incluir:
- Por usuario:
  - Nombre del usuario
  - Rol
  - Total de ventas procesadas
  - Monto total vendido
  - Ticket promedio
  - Productos vendidos
  - Caja registradora asignada
- Comparación entre usuarios:
  - Ranking por cantidad de ventas
  - Ranking por monto vendido
  - Productividad (ventas/hora si hay turnos)
- Estadísticas generales:
  - Total de usuarios activos
  - Usuario con más ventas
  - Usuario con mayor monto vendido

#### Visualizaciones:
- Tabla de ranking de usuarios
- Gráfico de barras comparativo
- Distribución de ventas por usuario (gráfico de pastel)
- Evolución temporal por usuario

---

### FASE 4: Módulo de Gestión de Productos 🟢 BAJA PRIORIDAD
**Duración estimada:** 1-2 días  
**Archivos a modificar:**
- `routes/inventory.py` (ya existe pero necesita mejoras)
- `templates/admin/products.html` (JavaScript)

#### Tareas:
- [ ] 4.1. Revisar y mejorar endpoint de edición de productos
- [ ] 4.2. Implementar validaciones completas en edición
- [ ] 4.3. Implementar endpoint de eliminación lógica (desactivar)
- [ ] 4.4. Agregar confirmación en frontend antes de eliminar
- [ ] 4.5. Implementar edición de productos con manejo de errores robusto
- [ ] 4.6. Actualizar JavaScript para remover placeholders "en desarrollo"
- [ ] 4.7. Agregar pruebas unitarias de edición y eliminación

#### Funcionalidades a implementar:
- **Edición de productos:**
  - Modal o página de edición con todos los campos
  - Validación de datos (precio, costo, stock, etc.)
  - Actualización de categoría
  - Actualización de impuestos asociados
  - Actualización de imagen del producto
  - Manejo de errores con mensajes claros

- **Eliminación de productos:**
  - Desactivación lógica (no borrado físico)
  - Verificar que no haya ventas pendientes con el producto
  - Confirmación con detalles del impacto
  - Opción de reactivación posterior
  - Log de auditoría

---

### FASE 5: Mejoras Generales al Módulo de Reportes 🟢 BAJA PRIORIDAD
**Duración estimada:** 2-3 días  
**Archivos a modificar:**
- `templates/admin/reports.html`
- `routes/admin.py`
- Nuevos archivos de utilidades

#### Tareas:
- [ ] 5.1. Agregar opción de guardar reportes favoritos
- [ ] 5.2. Implementar programación de reportes automáticos
- [ ] 5.3. Agregar exportación a Excel para todos los reportes
- [ ] 5.4. Implementar envío de reportes por email
- [ ] 5.5. Crear dashboard de reportes con widgets personalizables
- [ ] 5.6. Agregar comparación entre períodos
- [ ] 5.7. Implementar filtros avanzados (por categoría, por mesa, etc.)
- [ ] 5.8. Agregar caché de reportes para mejorar rendimiento

#### Mejoras sugeridas:
- **Sistema de favoritos:**
  - Guardar configuración de reportes frecuentes
  - Acceso rápido a reportes favoritos
  
- **Reportes automáticos:**
  - Programar generación diaria/semanal/mensual
  - Envío automático por email a administradores
  
- **Exportación mejorada:**
  - Exportar a Excel con formato y gráficos
  - Exportar múltiples reportes en un solo archivo
  
- **Dashboard personalizable:**
  - Widgets arrastrables
  - Gráficos en tiempo real
  - Resúmenes ejecutivos

---

## 📁 Estructura de Archivos Propuesta

### Nuevos endpoints a crear:
```
/admin/api/products-report          [GET] - Reporte de productos más vendidos
/admin/api/products-report/pdf      [GET] - PDF de productos más vendidos
/admin/api/products-report/excel    [GET] - Excel de productos más vendidos
/admin/api/ncf-report               [GET] - Reporte de comprobantes NCF
/admin/api/ncf-report/pdf           [GET] - PDF de comprobantes NCF
/admin/api/users-sales-report       [GET] - Reporte de ventas por usuario
/admin/api/users-sales-report/pdf   [GET] - PDF de ventas por usuario
```

### Archivos JavaScript a modificar:
```
templates/admin/reports.html        - Agregar funciones para nuevos reportes
```

### Nuevas funciones en backend:
```python
# En routes/admin.py

def products_report_api():
    """Genera reporte de productos más vendidos"""
    pass

def products_report_pdf():
    """Genera PDF de productos más vendidos"""
    pass

def ncf_report_api():
    """Genera reporte de comprobantes NCF"""
    pass

def ncf_report_pdf():
    """Genera PDF de comprobantes NCF"""
    pass

def users_sales_report_api():
    """Genera reporte de ventas por usuario"""
    pass

def users_sales_report_pdf():
    """Genera PDF de ventas por usuario"""
    pass
```

---

## 🧪 Plan de Testing

### Tests unitarios por fase:

**FASE 1 - Productos:**
- Test de consulta de productos más vendidos
- Test de filtros por período
- Test de exportación a PDF
- Test de exportación a Excel
- Test de validación de parámetros

**FASE 2 - NCF:**
- Test de consulta de NCF por tipo
- Test de cálculo de comprobantes disponibles
- Test de alertas de rangos por agotarse
- Test de exportación a PDF

**FASE 3 - Usuarios:**
- Test de consulta de ventas por usuario
- Test de ranking de usuarios
- Test de filtros por rol
- Test de exportación a PDF

**FASE 4 - Productos (CRUD):**
- Test de edición de producto
- Test de validaciones en edición
- Test de eliminación lógica
- Test de reactivación de producto

---

## 📊 Cronograma Estimado

```
┌─────────────────────────────────────────────────────┐
│  Semana 1: FASE 1 - Productos Más Vendidos         │
│  Días 1-3: Backend + Frontend + Exportaciones      │
├─────────────────────────────────────────────────────┤
│  Semana 2: FASE 2 - Comprobantes NCF               │
│  Días 4-6: Backend + Frontend + Alertas            │
├─────────────────────────────────────────────────────┤
│  Semana 3: FASE 3 - Ventas por Usuario             │
│  Días 7-8: Backend + Frontend + Exportaciones      │
├─────────────────────────────────────────────────────┤
│  Semana 3-4: FASE 4 - Gestión de Productos         │
│  Días 9-10: Edición + Eliminación + Validaciones   │
├─────────────────────────────────────────────────────┤
│  Semana 4-5: FASE 5 - Mejoras Generales (Opcional) │
│  Días 11-13: Dashboard + Favoritos + Automáticos   │
└─────────────────────────────────────────────────────┘

Total: 10-13 días de desarrollo
```

---

## 🎯 Criterios de Éxito

### Por cada fase:

**FASE 1:**
- ✅ Reporte muestra top 10/20/50 productos correctamente
- ✅ Filtros por período funcionan correctamente
- ✅ Exportación a PDF genera archivo descargable
- ✅ Exportación a Excel genera archivo con formato
- ✅ Gráficos visualizan datos correctamente

**FASE 2:**
- ✅ Reporte muestra estadísticas de NCF por tipo
- ✅ Sistema detecta rangos por agotarse (<100 y <20)
- ✅ Exportación a PDF incluye alertas
- ✅ Tabla detallada muestra todos los comprobantes

**FASE 3:**
- ✅ Reporte muestra ventas de todos los usuarios
- ✅ Ranking ordena correctamente por criterio seleccionado
- ✅ Filtros por rol funcionan correctamente
- ✅ Comparación entre usuarios es precisa

**FASE 4:**
- ✅ Edición de productos funciona sin errores
- ✅ Validaciones previenen datos incorrectos
- ✅ Eliminación lógica mantiene integridad de datos
- ✅ No se muestran mensajes "en desarrollo"

---

## 💡 Consideraciones Técnicas

### Rendimiento:
- Implementar paginación para reportes con muchos registros
- Usar índices de base de datos en campos de fecha y usuario
- Cachear reportes frecuentes (con invalidación automática)
- Optimizar consultas SQL con JOINs eficientes

### Seguridad:
- Validar permisos por rol en cada endpoint
- Sanitizar parámetros de entrada
- Validar rangos de fechas
- Prevenir SQL injection con ORM

### Usabilidad:
- Indicadores de carga mientras se genera el reporte
- Mensajes claros si no hay datos
- Diseño responsive para tablets y móviles
- Exportaciones nombradas con fecha/hora

### Mantenibilidad:
- Código modular y reutilizable
- Funciones auxiliares para consultas comunes
- Documentación de endpoints en código
- Tests automatizados

---

## 📈 Impacto Esperado

Al completar este plan:

| Métrica | Mejora Esperada |
|---------|-----------------|
| Visibilidad de operaciones | +100% (reportes completos) |
| Tiempo de análisis | -60% (reportes automatizados) |
| Toma de decisiones | +80% (datos precisos) |
| Cumplimiento fiscal NCF | +100% (alertas proactivas) |
| Satisfacción de administradores | +70% (herramientas completas) |

---

## 🔄 Próximos Pasos

1. **Revisión con cliente** - Validar prioridades y funcionalidades
2. **Asignación de recursos** - Definir desarrollador(es) responsable(s)
3. **Inicio de FASE 1** - Reporte de Productos Más Vendidos
4. **Testing continuo** - Pruebas después de cada fase
5. **Documentación** - Actualizar guías de usuario
6. **Capacitación** - Entrenar al personal en nuevos reportes

---

## 📝 Notas Adicionales

### Priorización sugerida:

**Alta prioridad (hacer primero):**
- FASE 1: Productos Más Vendidos - Info crítica para inventario
- FASE 2: Comprobantes NCF - Cumplimiento fiscal obligatorio

**Media prioridad (hacer después):**
- FASE 3: Ventas por Usuario - Útil para evaluación de personal

**Baja prioridad (opcional):**
- FASE 4: Gestión de Productos - Ya existe en módulo de inventario
- FASE 5: Mejoras Generales - Nice to have

### Dependencias:
- Ninguna fase depende de otra, pueden desarrollarse en paralelo
- FASE 5 puede beneficiarse de completar FASE 1-3 primero
- FASE 4 es independiente del resto

---

**Documento preparado por:** Sistema de Desarrollo  
**Última actualización:** 3 de noviembre de 2025  
**Versión:** 1.0
