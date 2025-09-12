from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import bcrypt
import models
from models import db
import secrets
from datetime import datetime, timedelta

bp = Blueprint('auth', __name__, url_prefix='/auth')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = models.User.query.filter_by(username=username, active=True).first()
        
        if user and bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
            # Update last_login timestamp
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role.value
            
            # Check if user must change password
            if user.must_change_password:
                flash('Debes cambiar tu contraseña antes de continuar', 'warning')
                return redirect(url_for('auth.change_password'))
            
            flash('Inicio de sesión exitoso', 'success')
            
            # Redirect based on role
            if user.role.value == 'administrador':
                return redirect(url_for('admin.dashboard'))
            elif user.role.value == 'cajero':
                return redirect(url_for('admin.pos'))
            elif user.role.value == 'mesero':
                return redirect(url_for('waiter.tables'))
        else:
            flash('Usuario o contraseña incorrectos', 'error')
    
    return render_template('auth/login.html')


@bp.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión', 'info')
    return redirect(url_for('auth.login'))


@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        
        # Always show the same message to prevent user enumeration
        flash('Si el email existe en nuestro sistema, recibirás un enlace de recuperación.', 'info')
        
        # Find user by email
        user = models.User.query.filter_by(email=email, active=True).first()
        
        if user:
            try:
                # Generate reset token
                token = secrets.token_urlsafe(32)
                expires_at = datetime.utcnow() + timedelta(hours=1)  # 1 hour expiry
                
                # Save token to database
                reset_token = models.PasswordResetToken()
                reset_token.user_id = user.id
                reset_token.token = token
                reset_token.expires_at = expires_at
                reset_token.ip_address = request.remote_addr or 'unknown'
                
                db.session.add(reset_token)
                db.session.commit()
                
                # For development, print the reset link to console
                reset_url = url_for('auth.reset_password', token=token, _external=True)
                print(f"\n=== RESET PASSWORD LINK FOR {user.email} ===")
                print(f"Reset URL: {reset_url}")
                print(f"Token expires at: {expires_at}")
                print("=== END RESET LINK ===\n")
                
                # In production, you would send an email here
                # send_password_reset_email(user.email, reset_url)
                
            except Exception as e:
                db.session.rollback()
                print(f"Error creating password reset token: {e}")
        
        return redirect(url_for('auth.login'))
    
    return render_template('auth/forgot_password.html')


@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    # Find valid token
    reset_token = models.PasswordResetToken.query.filter_by(
        token=token, 
        used_at=None
    ).first()
    
    if not reset_token or reset_token.expires_at < datetime.utcnow():
        flash('El enlace de recuperación es inválido o ha expirado.', 'error')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if len(password) < 6:
            flash('La contraseña debe tener al menos 6 caracteres', 'error')
            return render_template('auth/reset_password.html', token=token)
        
        if password != confirm_password:
            flash('Las contraseñas no coinciden', 'error')
            return render_template('auth/reset_password.html', token=token)
        
        try:
            # Update user password
            user = models.User.query.get(reset_token.user_id)
            if user:
                password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                user.password_hash = password_hash
                user.must_change_password = False
                
                # Mark token as used
                reset_token.used_at = datetime.utcnow()
                
                db.session.commit()
                
                flash('Contraseña actualizada exitosamente. Puedes iniciar sesión ahora.', 'success')
                return redirect(url_for('auth.login'))
            else:
                flash('Usuario no encontrado', 'error')
                
        except Exception as e:
            db.session.rollback()
            flash('Error al actualizar la contraseña. Intenta de nuevo.', 'error')
            print(f"Error resetting password: {e}")
    
    return render_template('auth/reset_password.html', token=token)


@bp.route('/change-password', methods=['GET', 'POST'])
def change_password():
    """Force password change for users with must_change_password flag"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user = models.User.query.get(session['user_id'])
    if not user or not user.active:
        session.clear()
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        # Validate current password
        if not bcrypt.checkpw(current_password.encode('utf-8'), user.password_hash.encode('utf-8')):
            flash('La contraseña actual es incorrecta', 'error')
            return render_template('auth/change_password.html')
        
        # Validate new password
        if len(new_password) < 6:
            flash('La nueva contraseña debe tener al menos 6 caracteres', 'error')
            return render_template('auth/change_password.html')
        
        if new_password != confirm_password:
            flash('Las nuevas contraseñas no coinciden', 'error')
            return render_template('auth/change_password.html')
        
        # Don't allow same password
        if current_password == new_password:
            flash('La nueva contraseña debe ser diferente a la actual', 'error')
            return render_template('auth/change_password.html')
        
        try:
            # Update password
            password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            user.password_hash = password_hash
            user.must_change_password = False
            
            db.session.commit()
            
            flash('Contraseña cambiada exitosamente', 'success')
            
            # Redirect based on role
            if user.role.value == 'administrador':
                return redirect(url_for('admin.dashboard'))
            elif user.role.value == 'cajero':
                return redirect(url_for('admin.pos'))
            elif user.role.value == 'mesero':
                return redirect(url_for('waiter.tables'))
            else:
                return redirect(url_for('auth.login'))
                
        except Exception as e:
            db.session.rollback()
            flash('Error al cambiar la contraseña. Intenta de nuevo.', 'error')
            print(f"Error changing password: {e}")
    
    return render_template('auth/change_password.html')