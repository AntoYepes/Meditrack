from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import pandas as pd
import sqlite3
from datetime import datetime
import os
import matplotlib
matplotlib.use('Agg')  # Usar un backend que no dependa de GUI
import matplotlib.pyplot as plt

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Predefined initial login credentials
INITIAL_USER = 'admin'
INITIAL_PASSWORD = 'admin123'

# Define where to store uploaded files temporarily
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')

# Check if the folder exists, if not, create it
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Function to initialize database if not exists
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    # Crear la tabla con las columnas correctas
    try:
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (usuario TEXT PRIMARY KEY, contraseña TEXT, rol TEXT, last_login TEXT)''')
        
        # Verificar si la tabla tiene algún usuario
        c.execute("SELECT COUNT(*) FROM users")
        if c.fetchone()[0] == 0:
            # Si no hay usuarios, insertar el usuario por defecto
            c.execute("INSERT INTO users (usuario, contraseña, rol, last_login) VALUES (?, ?, ?, ?)", 
                      (INITIAL_USER, INITIAL_PASSWORD, 'admin', None))
            print("Usuario por defecto 'admin' creado.")
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error al crear la tabla o insertar usuario: {e}")
    finally:
        conn.close()

# Function to load users from CSV to database
def load_users_from_csv(filepath):
    data = pd.read_csv(filepath, encoding='utf-8')  # Agrega el parámetro 'encoding'
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    for index, row in data.iterrows():
        c.execute("INSERT OR REPLACE INTO users (usuario, contraseña, rol) VALUES (?, ?, ?)", 
            (row['usuario'], row['contraseña'], row['rol']))
    conn.commit()
    conn.close()

# Route for login page
@app.route('/login')
def login():
    return render_template('login.html')

# Route to handle login
@app.route('/login', methods=['POST'])
def handle_login():
    usuario = request.form['username']
    contraseña = request.form['password']

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE usuario=? AND contraseña=?", (usuario, contraseña))
    user = c.fetchone()

    if (usuario == INITIAL_USER and contraseña == INITIAL_PASSWORD) or user:
        session['username'] = usuario
        if user:
            session['role'] = user[2]  # Guardar el rol del usuario
        else:
            session['role'] = 'admin'

        # Registrar la hora de inicio de sesión
        login_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("UPDATE users SET last_login=? WHERE usuario=?", (login_time, usuario))
        conn.commit()
        conn.close()
        return redirect(url_for('home'))
    else:
        conn.close()
        flash("Login Failed. Invalid credentials.")
        return redirect(url_for('login'))

# Route for home page after login
@app.route('/home')
def home():
    if 'username' in session:
        username = session['username']
        role = session.get('role', 'admin')  # Default role to 'admin' if not found
        return render_template('home.html', username=username, role=role)
    else:
        return redirect(url_for('login'))

# Página para cargar CSV
@app.route('/bd_usuarios', methods=['GET', 'POST'])
def bd_usuarios():
    if request.method == 'POST':
        if 'csv_file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['csv_file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)
            # Procesar el CSV y cargar los usuarios en la base de datos
            load_users_from_csv(filepath)
            flash('CSV cargado exitosamente. Inicia sesión con uno de los usuarios cargados.')
            return redirect(url_for('login'))
    return render_template('bd_usuarios.html')

# Ruta para el inventario
@app.route('/inventario', methods=['GET', 'POST'])
def inventario():
    success = False  # Para el manejo de la ventana modal
    data_summary = None
    graph_path_histogram = None
    graph_path_pie = None

    if request.method == 'POST':
        file = request.files.get('csv_file')
        if not file or file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'})

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)

        try:
            # Leer el CSV y cargarlo a la base de datos
            data = pd.read_csv(filepath)
            if data.empty:
                return jsonify({'success': False, 'message': 'El archivo CSV está vacío'})

            conn = sqlite3.connect('inventory.db')
            c = conn.cursor()

            # Crear la tabla 'inventory' si no existe
            c.execute('''
                CREATE TABLE IF NOT EXISTS inventory (
                    identificacion TEXT PRIMARY KEY,
                    lote TEXT,
                    nombre_dm TEXT,
                    fabricante TEXT,
                    dispositivo_medico TEXT,
                    numero_reusos INTEGER,
                    numero_esterilizacion INTEGER,
                    metodo_esterilizacion TEXT,
                    fecha_compra TEXT,
                    cantidad_piezas INTEGER,
                    esterilizador TEXT,
                    fecha_vencimiento TEXT
                )
            ''')

            # Asegúrate de que las columnas están correctas antes de continuar
            required_columns = ['identificacion', 'lote', 'nombre_dm', 'fabricante', 'dispositivo_medico', 
                                'numero_reusos', 'numero_esterilizacion', 'metodo_esterilizacion', 'fecha_compra', 
                                'cantidad_piezas', 'esterilizador', 'fecha_vencimiento']
            if not all(column in data.columns for column in required_columns):
                return jsonify({'success': False, 'message': 'El archivo CSV no tiene las columnas correctas.'})

            # Insertar cada fila en la base de datos
            for _, row in data.iterrows():
                c.execute('''
                    INSERT OR IGNORE INTO inventory 
                    (identificacion, lote, nombre_dm, fabricante, dispositivo_medico, 
                    numero_reusos, numero_esterilizacion, metodo_esterilizacion, fecha_compra,
                    cantidad_piezas, esterilizador, fecha_vencimiento)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (row['identificacion'], row['lote'], row['nombre_dm'], row['fabricante'], 
                      row['dispositivo_medico'], row['numero_reusos'], row['numero_esterilizacion'], 
                      row['metodo_esterilizacion'], row['fecha_compra'], row['cantidad_piezas'], 
                      row['esterilizador'], row['fecha_vencimiento']))

            conn.commit()
            conn.close()
            success = True
        except Exception as e:
            return jsonify({'success': False, 'message': f'Error al procesar el archivo: {str(e)}'})

    # Conectar a la base de datos y obtener los datos para el resumen
    conn = sqlite3.connect('inventory.db')
    data_summary = pd.read_sql_query("SELECT dispositivo_medico, COUNT(*) as cantidad FROM inventory GROUP BY dispositivo_medico", conn)
    conn.close()

    # Generar gráficos si hay datos
    if not data_summary.empty:
        # Crear un histograma
        plt.figure(figsize=(10, 6))
        plt.bar(data_summary['dispositivo_medico'], data_summary['cantidad'], color='skyblue')
        plt.title('Cantidad de Dispositivos por Tipo')
        plt.xlabel('Tipo de Dispositivo')
        plt.ylabel('Cantidad')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        graph_path_histogram = os.path.join('static', 'histogram.png')
        plt.savefig(graph_path_histogram)
        plt.close()

        # Crear un diagrama de torta
        plt.figure(figsize=(8, 8))
        plt.pie(data_summary['cantidad'], labels=data_summary['dispositivo_medico'], autopct='%1.1f%%', colors=plt.cm.Paired.colors)
        plt.title('Distribución de Dispositivos Médicos')
        graph_path_pie = os.path.join('static', 'pie_chart.png')
        plt.savefig(graph_path_pie)
        plt.close()

    return render_template('inventario.html', success=success, 
                           graph_path_histogram=graph_path_histogram, graph_path_pie=graph_path_pie)


# Ruta para esterilizacion
@app.route('/esterilizacion')
def esterilizacion():
    if 'username' in session:
        # Obtener la fecha y hora actuales
        fecha_actual = datetime.now().strftime('%Y-%m-%d')
        hora_actual = datetime.now().strftime('%H:%M:%S')

        # Obtener el parámetro `identificacion_dm` de la URL si está presente
        identificacion_dm = request.args.get('identificacion_dm', '')

        # Pasar `identificacion_dm` al renderizado de la plantilla
        return render_template('esterilizacion.html', fecha_actual=fecha_actual, hora_actual=hora_actual, identificacion_dm=identificacion_dm)
    else:
        return redirect(url_for('login'))

# Procesar esterilización
@app.route('/procesar_esterilizacion', methods=['POST'])
def procesar_esterilizacion():
    identificacion_dm = request.form['identificacion_dm']
    esterilizo = request.form['esterilizo']
    uso = request.form['uso']
    persona_esteriliza = request.form['persona_esteriliza']
    fecha = request.form['fecha']
    hora = request.form['hora']

    ciclos = request.form['ciclos']
    cantidad_piezas = request.form['cantidad_piezas']
    esterilizador = request.form['esterilizador']
    fecha_vencimiento = request.form['fecha_vencimiento']

    # Conectar a la base de datos de inventario
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()

    # Buscar el dispositivo médico por su identificación
    c.execute("SELECT lote, nombre_dm, numero_reusos FROM inventory WHERE identificacion=?", (identificacion_dm,))
    equipo = c.fetchone()

    if equipo:
        lote, nombre_dm, numero_reusos_permitida = equipo

        # Conectar a la base de datos de esterilización para obtener las esterilizaciones y usos previos
        conn_esterilizacion = sqlite3.connect('esterilizacion.db')
        c_esterilizacion = conn_esterilizacion.cursor()

        # Crear la tabla de esterilización si no existe
        c_esterilizacion.execute('''
            CREATE TABLE IF NOT EXISTS esterilizacion (
                identificacion_dm TEXT, 
                lote TEXT, 
                nombre_dm TEXT, 
                persona_esteriliza TEXT, 
                fecha TEXT, 
                hora TEXT, 
                esterilizo TEXT, 
                uso TEXT, 
                ciclos INTEGER, 
                cantidad_piezas INTEGER, 
                esterilizador TEXT, 
                fecha_vencimiento TEXT, 
                cantidad_esterilizaciones INTEGER, 
                cantidad_usos INTEGER
            )
        ''')

        # Verificar si ya existe un registro con los mismos identificadores clave
        c_esterilizacion.execute('''
            SELECT * FROM esterilizacion
            WHERE identificacion_dm = ? AND fecha = ? AND hora = ?
        ''', (identificacion_dm, fecha, hora))
        registro_existente = c_esterilizacion.fetchone()

        if registro_existente:
            # Cerrar la conexión antes de retornar
            conn_esterilizacion.close()
            return jsonify({'success': False, 'message': 'Registro duplicado, no se puede insertar.'})

        # Obtener la cantidad de esterilizaciones y usos más recientes
        c_esterilizacion.execute('''
            SELECT cantidad_esterilizaciones, cantidad_usos
            FROM esterilizacion
            WHERE identificacion_dm=?
            ORDER BY fecha DESC, hora DESC
            LIMIT 1
        ''', (identificacion_dm,))
        resultados = c_esterilizacion.fetchone()

        # Inicializar con valores previos o con 0 si no hay registros anteriores
        cantidad_esterilizaciones = resultados[0] if resultados else 0
        cantidad_usos = resultados[1] if resultados else 0

        # Incrementar la cantidad de esterilizaciones y usos si se marca "SI"
        if esterilizo == 'SI':
            cantidad_esterilizaciones += 1

        if uso == 'SI':
            cantidad_usos += 1

        # Insertar los datos de la esterilización
        c_esterilizacion.execute('''
            INSERT INTO esterilizacion (
                identificacion_dm, lote, nombre_dm, persona_esteriliza, 
                fecha, hora, esterilizo, uso, ciclos, cantidad_piezas, 
                esterilizador, fecha_vencimiento, 
                cantidad_esterilizaciones, cantidad_usos
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (identificacion_dm, lote, nombre_dm, persona_esteriliza, 
              fecha, hora, esterilizo, uso, ciclos, cantidad_piezas, 
              esterilizador, fecha_vencimiento, 
              cantidad_esterilizaciones, cantidad_usos))

        # Guardar cambios y cerrar la conexión
        conn_esterilizacion.commit()
        conn_esterilizacion.close()

        # Retornar redirección si no hay alerta
        return jsonify({'success': True, 'redirect_url': url_for('equipo_esterilizado', 
                                 identificacion_dm=identificacion_dm, 
                                 lote=lote, nombre_dm=nombre_dm, 
                                 persona_esteriliza=persona_esteriliza, 
                                 fecha=fecha, hora=hora, ciclos=ciclos, 
                                 cantidad_piezas=cantidad_piezas, 
                                 esterilizador=esterilizador, 
                                 fecha_vencimiento=fecha_vencimiento,
                                 cantidad_esterilizaciones=cantidad_esterilizaciones,
                                 cantidad_usos=cantidad_usos,
                                 numero_reusos_permitida=numero_reusos_permitida)})
    else:
        return jsonify({'success': False, 'message': 'Identificación de dispositivo médico no encontrada.'})



# Nueva ruta para la página equipo_esterilizado
@app.route('/equipo_esterilizado')
def equipo_esterilizado():
    identificacion_dm = request.args.get('identificacion_dm')
    persona_esteriliza = request.args.get('persona_esteriliza')
    fecha = request.args.get('fecha')
    hora = request.args.get('hora')
    ciclos = request.args.get('ciclos')
    cantidad_piezas = request.args.get('cantidad_piezas')
    esterilizador = request.args.get('esterilizador')
    fecha_vencimiento = request.args.get('fecha_vencimiento')
    lote = request.args.get('lote')
    nombre_dm = request.args.get('nombre_dm')
    cantidad_esterilizaciones = request.args.get('cantidad_esterilizaciones')
    cantidad_usos = request.args.get('cantidad_usos')
    numero_reusos_permitida = request.args.get('numero_reusos_permitida')

    return render_template('equipo_esterilizado.html', identificacion_dm=identificacion_dm, 
                           persona_esteriliza=persona_esteriliza, fecha=fecha, hora=hora, 
                           ciclos=ciclos, cantidad_piezas=cantidad_piezas, esterilizador=esterilizador,
                           fecha_vencimiento=fecha_vencimiento, lote=lote, nombre_dm=nombre_dm,
                           cantidad_esterilizaciones=cantidad_esterilizaciones,
                           cantidad_usos=cantidad_usos,
                           numero_reusos_permitida=numero_reusos_permitida)


# Ruta para la búsqueda de registros de esterilización
@app.route('/busqueda_esterilizacion', methods=['GET'])
def busqueda_esterilizacion():
    query = request.args.get('query', '')
    resultados = []

    if query:
        conn = sqlite3.connect('esterilizacion.db')
        c = conn.cursor()
        c.execute('''
            SELECT DISTINCT * FROM esterilizacion
            WHERE identificacion_dm LIKE ?
        ''', (f'%{query}%',))
        resultados = c.fetchall()
        conn.close()

    return render_template('busqueda.html', query=query, resultados=resultados)


# Buscar dispositivo médico para llenar lote, nombre DM, cantidad_piezas, esterilizador y fecha de vencimiento
@app.route('/buscar_dm')
def buscar_dm():
    identificacion_dm = request.args.get('identificacion_dm')

    # Conectar a la base de datos de inventario
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()

    # Buscar el dispositivo médico por su identificación y obtener los campos adicionales
    c.execute('''
        SELECT lote, nombre_dm, cantidad_piezas, esterilizador, fecha_vencimiento
        FROM inventory
        WHERE identificacion=?
    ''', (identificacion_dm,))
    equipo = c.fetchone()
    conn.close()

    if equipo:
        lote, nombre_dm, cantidad_piezas, esterilizador, fecha_vencimiento = equipo
        return jsonify({
            'success': True,
            'lote': lote,
            'nombre_dm': nombre_dm,
            'cantidad_piezas': cantidad_piezas,
            'esterilizador': esterilizador,
            'fecha_vencimiento': fecha_vencimiento
        })
    else:
        return jsonify({'success': False})



# Ruta para cerrar sesión
@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()  # Initialize the database on the first run
    app.run(host='0.0.0.0', port=5000, debug=True)  # Make the server accessible on the network