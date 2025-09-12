from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import bcrypt
import models
from main import db

bp = Blueprint('auth', __name__, url_prefix='/auth')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = models.User.query.filter_by(username=username, active=True).first()
        
        if user and bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role.value
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