from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import pandas as pd
import sqlite3
from datetime import datetime
import os
import matplotlib
matplotlib.use('Agg')  # Usar un backend que no dependa de GUI
import matplotlib.pyplot as plt
import seaborn as sns

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
    success = False  # For handling modal display
    data_summary = None
    graph_path_histogram = None
    graph_path_pie = None
    graph_path_pinzas = None

    # Handle CSV upload for inventory
    if request.method == 'POST':
        file = request.files.get('csv_file')
        if not file or file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'})

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)

        try:
            # Read and load CSV into inventory database
            data = pd.read_csv(filepath)
            if data.empty:
                return jsonify({'success': False, 'message': 'El archivo CSV está vacío'})

            conn = sqlite3.connect('inventory.db')
            c = conn.cursor()

            # Create 'inventory' table if it doesn't exist
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

            # Ensure columns match the required structure
            required_columns = ['identificacion', 'lote', 'nombre_dm', 'fabricante', 'dispositivo_medico', 
                                'numero_reusos', 'numero_esterilizacion', 'metodo_esterilizacion', 'fecha_compra', 
                                'cantidad_piezas', 'esterilizador', 'fecha_vencimiento']
            if not all(column in data.columns for column in required_columns):
                return jsonify({'success': False, 'message': 'El archivo CSV no tiene las columnas correctas.'})

            # Insert rows into inventory database
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

    # Load inventory data summary
    conn = sqlite3.connect('inventory.db')
    data_summary = pd.read_sql_query("SELECT dispositivo_medico, COUNT(*) as cantidad FROM inventory GROUP BY dispositivo_medico", conn)
    conn.close()

    # Generate histograms and pie charts if data is available
    if not data_summary.empty:
        # Create a histogram
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

        # Create a pie chart
        plt.figure(figsize=(8, 8))
        plt.pie(data_summary['cantidad'], labels=data_summary['dispositivo_medico'], autopct='%1.1f%%', colors=plt.cm.Paired.colors)
        plt.title('Distribución de Dispositivos Médicos')
        graph_path_pie = os.path.join('static', 'pie_chart.png')
        plt.savefig(graph_path_pie)
        plt.close()
        
    # Retrieve and merge data for the "pinzas" usage chart
    # Query inventory.db for allowed uses (numero_reusos)
    conn_inventory = sqlite3.connect('inventory.db')
    pinzas_inventory_data = pd.read_sql_query('''
        SELECT identificacion, nombre_dm, numero_reusos
        FROM inventory
        WHERE dispositivo_medico LIKE '%Pinza%'
    ''', conn_inventory)
    conn_inventory.close()

    # Query esterilizacion.db for current uses (cantidad_usos)
    conn_esterilizacion = sqlite3.connect('esterilizacion.db')
    pinzas_esterilizacion_data = pd.read_sql_query('''
        SELECT identificacion_dm AS identificacion, nombre_dm, cantidad_usos
        FROM esterilizacion
        WHERE nombre_dm LIKE '%Pinza%'
    ''', conn_esterilizacion)
    conn_esterilizacion.close()

    # Query inventory.db for allowed uses (numero_reusos)
    conn_inventory = sqlite3.connect('inventory.db')
    retractores_inventory_data = pd.read_sql_query('''
        SELECT identificacion, nombre_dm, numero_reusos
        FROM inventory
        WHERE dispositivo_medico LIKE '%Retractor%'
    ''', conn_inventory)
    conn_inventory.close()

    # Query esterilizacion.db for current uses (cantidad_usos)
    conn_esterilizacion = sqlite3.connect('esterilizacion.db')
    retractores_esterilizacion_data = pd.read_sql_query('''
        SELECT identificacion_dm AS identificacion, nombre_dm, cantidad_usos
        FROM esterilizacion
        WHERE nombre_dm LIKE '%Retractor%'
    ''', conn_esterilizacion)
    conn_esterilizacion.close()

    # Query inventory.db for allowed uses (numero_reusos)
    conn_inventory = sqlite3.connect('inventory.db')
    filtros_inventory_data = pd.read_sql_query('''
        SELECT identificacion, nombre_dm, numero_reusos
        FROM inventory
        WHERE dispositivo_medico LIKE '%Filtro%'
    ''', conn_inventory)
    conn_inventory.close()

    # Query esterilizacion.db for current uses (cantidad_usos)
    conn_esterilizacion = sqlite3.connect('esterilizacion.db')
    filtros_esterilizacion_data = pd.read_sql_query('''
        SELECT identificacion_dm AS identificacion, nombre_dm, cantidad_usos
        FROM esterilizacion
        WHERE nombre_dm LIKE '%Filtro%'
    ''', conn_esterilizacion)
    conn_esterilizacion.close()

    # Obtener la fecha de compra de cada dispositivo
    # Cargar los datos de las bases de datos
    conn_inventory = sqlite3.connect('inventory.db')
    inventory_data = pd.read_sql_query('''
        SELECT identificacion, fecha_compra, numero_reusos, nombre_dm
        FROM inventory
    ''', conn_inventory)
    conn_inventory.close()

    conn_esterilizacion = sqlite3.connect('esterilizacion.db')
    esterilizacion_data = pd.read_sql_query('''
        SELECT identificacion_dm, fecha, cantidad_usos
        FROM esterilizacion
    ''', conn_esterilizacion)
    conn_esterilizacion.close()

    # Merge the two datasets on 'identificacion' to combine allowed and current uses
    pinzas_data = pd.merge(pinzas_inventory_data, pinzas_esterilizacion_data, on='identificacion', how='inner', suffixes=('_inventory', '_esterilizacion'))

    # Merge the two datasets on 'identificacion' to combine allowed and current uses
    retractores_data = pd.merge(retractores_inventory_data, retractores_esterilizacion_data, on='identificacion', how='inner', suffixes=('_inventory', '_esterilizacion'))

    # Merge the two datasets on 'identificacion' to combine allowed and current uses
    filtros_data = pd.merge(filtros_inventory_data, filtros_esterilizacion_data, on='identificacion', how='inner', suffixes=('_inventory', '_esterilizacion'))

    # Combinar datos basados en identificacion_dm e identificacion
    merged_data = pd.merge(
        esterilizacion_data,
        inventory_data,
        left_on='identificacion_dm',
        right_on='identificacion',
        how='inner'
    )

    # Nota: Este filtro requiere que ya sepas o tengas una columna `numero_reusos`
    merged_data['fecha'] = pd.to_datetime(merged_data['fecha'], errors='coerce')
    merged_data['fecha_compra'] = pd.to_datetime(merged_data['fecha_compra'], errors='coerce')

    # Calcular la diferencia en días
    merged_data['dias_transcurridos'] = (merged_data['fecha'] - merged_data['fecha_compra']).dt.days

    # Debug: Print columns of merged DataFrame to check names
    print("Columns in pinzas_data after merge:", pinzas_data.columns)

    # Use the correct column names from the merged DataFrame
    # Crear un gráfico acumulativo para Usos Actuales vs Permitidos
    if not pinzas_data.empty:
        # Establecer colores y dimensiones
        plt.figure(figsize=(10, 6))
        
        # Crear barras base para usos permitidos con menor altura
        plt.barh(pinzas_data['nombre_dm_inventory'], pinzas_data['numero_reusos'], 
                color='#e0e0e0', label='Usos Permitidos', height=0.5)
        
        # Crear barras superpuestas para usos actuales con menor altura
        plt.barh(pinzas_data['nombre_dm_inventory'], pinzas_data['cantidad_usos'], 
                color='#0077bc', label='Usos Actuales', height=0.5)

        # Personalizar etiquetas y leyenda
        plt.title('Usos Actuales vs Usos Permitidos para Pinzas', fontsize=16, fontweight='bold')
        plt.xlabel('Número de Usos', fontsize=14)
        plt.ylabel('Pinzas', fontsize=14)
        plt.xticks(fontsize=12)
        plt.yticks(fontsize=10)
        plt.legend(fontsize=12)

        # Ajustar espaciado y guardar gráfico
        plt.tight_layout()
        graph_path_pinzas = os.path.join('static', 'pinzas_uso_chart.png')
        plt.savefig(graph_path_pinzas)
        plt.close()

    # Use the correct column names from the merged DataFrame
    if not retractores_data.empty:
        # Plot "retractores" current vs allowed uses
        plt.figure(figsize=(10, 6))

        # Create base bars for allowed uses
        plt.barh(retractores_data['nombre_dm_inventory'], retractores_data['numero_reusos'], 
                color='#e0e0e0', label='Usos Permitidos', height=0.5)
        
        # Overlay bars for current uses
        plt.barh(retractores_data['nombre_dm_inventory'], retractores_data['cantidad_usos'], 
                color='#0077bc', label='Usos Actuales', height=0.5)

        # Customize labels and legend
        plt.title('Usos Actuales vs Usos Permitidos para Retractores', fontsize=16, fontweight='bold')
        plt.xlabel('Número de Usos', fontsize=14)
        plt.ylabel('Retractores', fontsize=14)
        plt.xticks(fontsize=12)
        plt.yticks(fontsize=10)
        plt.legend(fontsize=12)

        # Adjust spacing and save the graph
        plt.tight_layout()
        graph_path_retractores = os.path.join('static', 'retractores_uso_chart.png')
        plt.savefig(graph_path_retractores)
        plt.close()
    else:
        graph_path_retractores = None

    # Use the correct column names from the merged DataFrame
    if not filtros_data.empty:
        # Plot "filtros" current vs allowed uses
        plt.figure(figsize=(10, 6))

        # Create base bars for allowed uses
        plt.barh(filtros_data['nombre_dm_inventory'], filtros_data['numero_reusos'], 
                color='#e0e0e0', label='Usos Permitidos', height=0.5)
        
        # Overlay bars for current uses
        plt.barh(filtros_data['nombre_dm_inventory'], filtros_data['cantidad_usos'], 
                color='#0077bc', label='Usos Actuales', height=0.5)

        # Customize labels and legend
        plt.title('Usos Actuales vs Usos Permitidos para Filtros', fontsize=16, fontweight='bold')
        plt.xlabel('Número de Usos', fontsize=14)
        plt.ylabel('Filtros', fontsize=14)
        plt.xticks(fontsize=12)
        plt.yticks(fontsize=10)
        plt.legend(fontsize=12)

        # Adjust spacing and save the graph
        plt.tight_layout()
        graph_path_filtros = os.path.join('static', 'filtros_uso_chart.png')
        plt.savefig(graph_path_filtros)
        plt.close()
    else:
        graph_path_filtros = None

    # Calcular la diferencia en días entre fecha_compra y fecha
    # Asegurarse de que 'numero_reusos' está disponible y correcto
    if 'numero_reusos' in merged_data.columns:
        # Filtrar datos donde cantidad_usos es igual al número máximo de usos permitidos
        merged_data = merged_data[merged_data['cantidad_usos'] == merged_data['numero_reusos']]
    elif 'numero_reusos_inventory' in merged_data.columns:
        # Ajustar si la columna tiene un prefijo
        merged_data = merged_data[merged_data['cantidad_usos'] == merged_data['numero_reusos_inventory']]
    else:
        raise ValueError("La columna 'numero_reusos' no está disponible en los datos combinados.")


    # Asegúrate de que 'nombre_dm' contenga los nombres de los dispositivos médicos
    if 'nombre_dm' in merged_data.columns:
        # Crear el gráfico de barras horizontales con nombres en el eje Y
        plt.figure(figsize=(10, 6))
        plt.barh(merged_data['nombre_dm'], merged_data['dias_transcurridos'], color='skyblue')
        plt.title('Tiempo Transcurrido desde la Compra hasta el Límite de Usos Permitidos', fontsize=16)
        plt.xlabel('Días Transcurridos', fontsize=14)
        plt.ylabel('Dispositivo Médico', fontsize=14)
        plt.tight_layout()

        # Guardar el gráfico
        graph_path_tiempo = os.path.join('static', 'tiempo_transcurrido_chart.png')
        plt.savefig(graph_path_tiempo)
        plt.close()
    else:
        print("La columna 'nombre_dm' no está disponible en el DataFrame.")


    return render_template('inventario.html', success=success, 
                           graph_path_histogram=graph_path_histogram, 
                           graph_path_pie=graph_path_pie,
                           graph_path_pinzas=graph_path_pinzas,
                           graph_path_retractores=graph_path_retractores,
                           graph_path_filtros=graph_path_filtros,
                           graph_path_tiempo=graph_path_tiempo)


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

        # Verificar si el dispositivo ha superado el número máximo de usos permitidos
        if cantidad_usos > numero_reusos_permitida:
            # No guardar el registro y mostrar el mensaje de advertencia
            conn_esterilizacion.close()
            return jsonify({'success': False, 'mensaje': "Ya superó el número de usos permitido, no puede continuar."})

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

        # Lógica para determinar el mensaje de respuesta según los casos
        if cantidad_usos == numero_reusos_permitida:
            mensaje = "El dispositivo ha cumplido el número máximo de usos permitidos y debe desecharse."
        elif cantidad_usos == numero_reusos_permitida - 1:
            mensaje = "El dispositivo le falta un solo uso permitido."
        else:
            mensaje = "¡Esterilización de equipo guardada con éxito!"

        # Retornar redirección si no hay alerta
        return jsonify({'success': True, 'mensaje': mensaje, 'redirect_url': url_for('equipo_esterilizado', 
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

    # Listar imágenes disponibles en la carpeta
    image_folder = os.path.join(app.static_folder, 'device_images')
    available_images = [f for f in os.listdir(image_folder) if f.endswith('.png')]

    return render_template('equipo_esterilizado.html', identificacion_dm=identificacion_dm, available_images=available_images,
                           persona_esteriliza=persona_esteriliza, fecha=fecha, hora=hora, 
                           ciclos=ciclos, cantidad_piezas=cantidad_piezas, esterilizador=esterilizador,
                           fecha_vencimiento=fecha_vencimiento, lote=lote, nombre_dm=nombre_dm,
                           cantidad_esterilizaciones=cantidad_esterilizaciones,
                           cantidad_usos=cantidad_usos,
                           numero_reusos_permitida=numero_reusos_permitida)


@app.route('/busqueda_esterilizacion', methods=['GET'])
def busqueda_esterilizacion():
    query = request.args.get('query', '')
    resultados = []

    if query:
        conn = sqlite3.connect('esterilizacion.db')
        c = conn.cursor()
        # Consulta original para obtener los registros de esterilización
        c.execute('''
            SELECT DISTINCT * FROM esterilizacion
            WHERE identificacion_dm LIKE ?
        ''', (f'%{query}%',))
        resultados = c.fetchall()
        conn.close()

        # Abrimos otra conexión para obtener el número de usos permitidos desde `inventory`
        conn_inventory = sqlite3.connect('inventory.db')
        c_inventory = conn_inventory.cursor()

        # Agregar el número de usos permitidos a cada registro en `resultados`
        resultados_con_usos_permitidos = []
        for registro in resultados:
            identificacion_dm = registro[0]
            # Obtener el número de usos permitidos de `inventory`
            c_inventory.execute('''
                SELECT numero_reusos FROM inventory WHERE identificacion = ?
            ''', (identificacion_dm,))
            usos_permitidos = c_inventory.fetchone()
            numero_usos_permitidos = usos_permitidos[0] if usos_permitidos else 'N/A'
            
            # Agregar `numero_usos_permitidos` al registro
            registro_con_usos_permitidos = registro + (numero_usos_permitidos,)
            resultados_con_usos_permitidos.append(registro_con_usos_permitidos)

        conn_inventory.close()
    else:
        resultados_con_usos_permitidos = []

    return render_template('busqueda.html', query=query, resultados=resultados_con_usos_permitidos)



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