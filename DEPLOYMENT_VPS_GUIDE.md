# 🚀 Guía de Deployment en VPS con Impresora Térmica

## Arquitectura del Sistema

```
Usuario (Móvil/PC) → Navegador → Internet → VPS (Flask + Impresora)
                                              ↓
                                      Impresora USB/Red
```

## ✅ Ventajas de esta Arquitectura

- ✅ Impresión directa sin diálogo del navegador
- ✅ Funciona desde cualquier dispositivo (móvil, tablet, PC)
- ✅ La impresora solo necesita estar en el VPS
- ✅ Usuarios no necesitan instalar nada

---

## 📋 Requisitos del VPS

### Sistema Operativo Recomendado
- **Ubuntu 22.04 LTS** o **Debian 11+**

### Especificaciones Mínimas
- 1 CPU
- 2 GB RAM
- 20 GB SSD
- 1 Puerto USB disponible (para impresora USB) o red local

---

## 🔧 Instalación en VPS

### 1. Conectar al VPS
```bash
ssh root@tu-vps-ip
```

### 2. Actualizar Sistema
```bash
apt update && apt upgrade -y
```

### 3. Instalar Dependencias del Sistema
```bash
# Python y herramientas
apt install -y python3 python3-pip python3-venv git

# Dependencias para impresión USB
apt install -y libusb-1.0-0 libusb-1.0-0-dev

# PostgreSQL
apt install -y postgresql postgresql-contrib

# Nginx (servidor web)
apt install -y nginx

# Supervisor (mantener app corriendo)
apt install -y supervisor
```

### 4. Crear Usuario de Aplicación
```bash
adduser --system --group --home /home/posapp posapp
su - posapp
```

### 5. Clonar Repositorio
```bash
cd /home/posapp
git clone <tu-repositorio> pos
cd pos
```

### 6. Crear Entorno Virtual
```bash
python3 -m venv venv
source venv/bin/activate
```

### 7. Instalar Dependencias Python
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 🖨️ Configuración de Impresora

### Opción A: Impresora USB

#### 1. Conectar Impresora y Detectarla
```bash
# Listar dispositivos USB
lsusb

# Salida ejemplo:
# Bus 001 Device 003: ID 04b8:0202 Seiko Epson Corp. TM-T20
#                        ^^^^:^^^^
#                     Vendor:Product ID
```

#### 2. Configurar Permisos
```bash
# Agregar usuario al grupo lp
usermod -a -G lp posapp

# Crear regla udev
nano /etc/udev/rules.d/99-thermal-printer.rules
```

Contenido:
```
SUBSYSTEM=="usb", ATTR{idVendor}=="04b8", ATTR{idProduct}=="0202", MODE="0666"
```
(Reemplaza `04b8` y `0202` con tus IDs)

```bash
# Recargar reglas udev
udevadm control --reload-rules
udevadm trigger
```

#### 3. Verificar Conexión
```bash
# Desde el entorno virtual de la app
cd /home/posapp/pos
source venv/bin/activate
python3 test_usb_printer.py
```

### Opción B: Impresora de Red

#### 1. Configurar IP Estática en la Impresora
- Asigna una IP fija a la impresora (ej: 192.168.1.100)
- Asegúrate que el VPS puede alcanzarla

#### 2. Probar Conectividad
```bash
# Ping a la impresora
ping 192.168.1.100

# Probar puerto 9100
nc -zv 192.168.1.100 9100
```

---

## 🗄️ Configuración de Base de Datos

### 1. Crear Base de Datos PostgreSQL
```bash
sudo -u postgres psql

postgres=# CREATE DATABASE posdb;
postgres=# CREATE USER posuser WITH PASSWORD 'tu-password-seguro';
postgres=# GRANT ALL PRIVILEGES ON DATABASE posdb TO posuser;
postgres=# \q
```

### 2. Configurar Variables de Entorno
```bash
cd /home/posapp/pos
nano .env
```

Contenido:
```env
# Base de datos
DATABASE_URL=postgresql://posuser:tu-password-seguro@localhost/posdb

# Flask
SESSION_SECRET=genera-un-secreto-aleatorio-largo
FLASK_ENV=production

# Impresora (USB - ejemplo)
PRINTER_TYPE=usb
PRINTER_USB_VENDOR_ID=0x04b8
PRINTER_USB_PRODUCT_ID=0x0202
PRINTER_PAPER_WIDTH=80
PRINTER_AUTO_CUT=true

# O para impresora de Red
# PRINTER_TYPE=network
# PRINTER_NETWORK_HOST=192.168.1.100
# PRINTER_NETWORK_PORT=9100
```

### 3. Inicializar Base de Datos
```bash
source venv/bin/activate
python3 << EOF
from app import app, db
with app.app_context():
    db.create_all()
