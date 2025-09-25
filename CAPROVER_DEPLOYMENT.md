# Configuración de Despliegue en CapRover

Este documento explica cómo configurar la aplicación Four One POS para su despliegue en CapRover.

## Archivos de Configuración

### 1. captain-definition
Archivo principal de configuración de CapRover que apunta al Dockerfile.

### 2. Dockerfile
Configuración optimizada que:
- Configura el backend Flask con todas las dependencias
- Preserva los archivos estáticos existentes (CSS, JS, PWA assets)
- Usa gunicorn como servidor web en producción

## Variables de Entorno Requeridas

### Variables Obligatorias

1. **DATABASE_URL**
   - Descripción: String de conexión a PostgreSQL
   - Formato: `postgresql://usuario:password@host:puerto/database`
   - Ejemplo: `postgresql://user:pass@db:5432/fouronepos`

2. **SESSION_SECRET**
   - Descripción: Clave secreta para sesiones Flask (mínimo 32 caracteres)
   - Ejemplo: `your-super-secret-session-key-here-32chars`

3. **ENVIRONMENT**
   - Descripción: Entorno de ejecución
   - Valor: `production`

4. **JWT_SECRET**
   - Descripción: Clave secreta para tokens JWT
   - Ejemplo: `your-jwt-secret-key-for-api-auth`

### Variables Opcionales (Impresora Térmica)

Si usas impresora térmica, configura las siguientes variables según tu tipo de impresora:

#### Tipo de Impresora
- **PRINTER_TYPE**: `usb`, `serial`, `network`, o `file`

#### Para Impresora USB
- **PRINTER_USB_VENDOR_ID**: ID del fabricante (ej: `0x04b8`)
- **PRINTER_USB_PRODUCT_ID**: ID del producto (ej: `0x0202`)

#### Para Impresora Serial
- **PRINTER_SERIAL_PORT**: Puerto serie (ej: `/dev/ttyUSB0`)
- **PRINTER_SERIAL_BAUDRATE**: Velocidad (ej: `9600`)

#### Para Impresora de Red
- **PRINTER_NETWORK_HOST**: IP de la impresora (ej: `192.168.1.100`)
- **PRINTER_NETWORK_PORT**: Puerto TCP (ej: `9100`)

#### Configuración General de Impresora
- **PRINTER_PAPER_WIDTH**: Ancho del papel (`80` o `58`)
- **PRINTER_AUTO_CUT**: Corte automático (`true` o `false`)
- **PRINTER_AUTO_OPEN_DRAWER**: Abrir cajón automático (`true` o `false`)

## Pasos de Despliegue en CapRover

1. **Crear aplicación en CapRover**
   - Nombre: `fouronepos` (o el que prefieras)
   - Tipo: Dockerfile/Captain Definition

2. **Configurar variables de entorno**
   - Ve a la sección "App Configs" 
   - Añade todas las variables requeridas mencionadas arriba

3. **Configurar base de datos**
   - Crea una app de PostgreSQL en CapRover
   - Usa la URL de conexión generada para DATABASE_URL

4. **Desplegar aplicación**
   - Conecta tu repositorio o sube los archivos
   - CapRover construirá automáticamente usando el Dockerfile

## Características de la Aplicación

- **Frontend**: React PWA con soporte offline
- **Backend**: Flask con SQLAlchemy
- **Base de datos**: PostgreSQL
- **Servidor web**: Gunicorn
- **Puerto**: 5000
- **Funcionalidades especiales**:
  - Service Worker para funcionalidad offline
  - Impresión térmica de recibos
  - Sistema POS completo
  - Gestión de inventario
  - Reportes y análisis

## Verificación del Despliegue

Después del despliegue, verifica:

1. **Health Check**: Accede a `/health` - debe retornar "OK"
2. **Frontend**: Verifica que la PWA cargue correctamente
3. **Base de datos**: Confirma que las tablas se crean automáticamente
4. **Service Worker**: Verifica que se registre para funcionalidad offline
5. **Impresora**: Si usas impresora térmica, verifica la conectividad

## Notas de Seguridad

- La aplicación incluye headers de seguridad automáticos en producción
- CSRF protection habilitado
- Rate limiting configurado
- Cookies seguras en HTTPS
- Todas las variables secretas deben ser únicas y complejas