#!/usr/bin/env python3
import bcrypt

# Generar hashes para las contraseñas
admin_password = "PSzorro99**"
gerente_password = "PSvestibulo99**"

admin_hash = bcrypt.hashpw(admin_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
gerente_hash = bcrypt.hashpw(gerente_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

print(f"Hash para admin: {admin_hash}")
print(f"Hash para gerente: {gerente_hash}")