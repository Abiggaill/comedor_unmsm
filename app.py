import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
# Clave secreta necesaria para gestionar las sesiones de usuario
app.secret_key = 'clave_secreta_comedor_unmsm'

DATABASE = 'comedor.db'

# Función para conectar a la base de datos SQLite
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# Inicialización de la Base de Datos: Crea la tabla 'usuarios' si no existe
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dni TEXT UNIQUE NOT NULL,
            nombres TEXT NOT NULL,
            correo TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            rol TEXT DEFAULT 'Estudiante'
        )
    ''')
    conn.commit()
    conn.close()

# Ejecutamos la creación de la tabla al arrancar la app
init_db()

# --- RUTA 1: LOGIN (Página de Inicio) ---
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form['correo']
        password = request.form['password']

        conn = get_db_connection()
        # Buscamos la fila del usuario por su correo
        usuario = conn.execute('SELECT * FROM usuarios WHERE correo = ?', (correo,)).fetchone()
        conn.close()

        # Verificamos si el usuario existe y si la contraseña cifrada coincide
        if usuario and check_password_hash(usuario['password'], password):
            # Guardamos los datos del usuario en la sesión del navegador
            session['user_id'] = usuario['id']
            session['nombres'] = usuario['nombres']
            session['rol'] = usuario['rol']
            return redirect(url_for('dashboard'))
        else:
            flash('Correo o contraseña incorrectos. Inténtalo de nuevo.')

    return render_template('login.html')

# --- RUTA 2: REGISTRO DE CUENTA ---
@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        dni = request.form['dni']
        nombres = request.form['nombres']
        correo = request.form['correo']
        password = request.form['password']
        
        # Ciframos la contraseña antes de guardarla en la BD
        password_hashed = generate_password_hash(password)

        conn = get_db_connection()
        try:
            # Insertamos una NUEVA FILA en la tabla 'usuarios'
            conn.execute('''
                INSERT INTO usuarios (dni, nombres, correo, password)
                VALUES (?, ?, ?, ?)
            ''', (dni, nombres, correo, password_hashed))
            conn.commit()
            conn.close()
            
            flash('¡Cuenta creada con éxito! Ahora puedes iniciar sesión.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            conn.close()
            flash('El DNI o Correo ya se encuentra registrado.')

    return render_template('registro.html')

# --- RUTA 3: PANEL PRINCIPAL (DASHBOARD) ---
@app.route('/dashboard')
def dashboard():
    # Verificamos que el usuario esté autenticado
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    return render_template('dashboard.html', nombres=session['nombres'], rol=session['rol'])

# --- RUTA 4: CERRAR SESIÓN ---
@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión correctamente.')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
    