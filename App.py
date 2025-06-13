from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
import hashlib
import pyscrypt  # 🔹 Instala pyscrypt con `pip install pyscrypt`

from flask import send_file
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

def verificar_contraseña(password_plain, password_hashed):
    return hashlib.sha256(password_plain.encode()).hexdigest() == password_hashed

app = Flask(__name__, static_folder="static")
app.secret_key = 'supersecretkey'    # Clave para sesiones

# Configuración de MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'plataforma_cursos'
app.config['MYSQL_PORT'] = 3306  # 🚀 Puerto configurado

mysql = MySQL(app)


#------------------REGISTRO --------------#
# 🔹 Ruta de registro
@app.route('/registro')
def registro():
    return render_template('registro.html')

import hashlib  # 🔹 Importamos hashlib para la encriptación

@app.route('/procesar_registro', methods=['POST'])
def procesar_registro():
    nombre = request.form.get('nombre', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()

    if not nombre or not email or not password:
        return "Error: Todos los campos son obligatorios.", 400

    # 🔐 Generar hash SHA-256
    hashed_password = hashlib.sha256(password.encode('utf-8')).hexdigest()

    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO usuarios (nombre, email, contraseña) VALUES (%s, %s, %s)", (nombre, email, hashed_password))
    mysql.connection.commit()
    cur.close()

    return redirect(url_for('login_estudiante'))  # 🔹 Redirige al login después del registro exitoso




# ----------------- LOGIN ESTUDIANTES ---------------- #

@app.route('/login_estudiante', methods=['GET', 'POST'])
def login_estudiante():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        cur = mysql.connection.cursor()
        cur.execute("SELECT id, nombre, contraseña FROM usuarios WHERE email = %s", (email,))
        usuario = cur.fetchone()
        cur.close()

        if not usuario or not usuario[2]:  
            flash("Error: Usuario no encontrado o sin contraseña registrada")
            return redirect(url_for('login_estudiante'))

        stored_password = usuario[2]
        hashed_password = hashlib.sha256(password.encode()).hexdigest()  # 🔹 Encripta la contraseña ingresada

        if hashed_password == stored_password:  
            session['usuario_id'] = usuario[0]
            session['usuario_nombre'] = usuario[1]  
            return redirect(url_for('dashboard_estudiante'))  

        flash("Error: Credenciales incorrectas")  
    return render_template('login_estudiante.html')




# ----------------- LOGIN PROFESORES ---------------- #
@app.route('/login_profesor', methods=['GET', 'POST'])
def login_profesor():
    if request.method == 'POST':
        email = request.form['email']
        contraseña = request.form['contraseña']

        cur = mysql.connection.cursor()
        cur.execute("SELECT id, nombre, email, contraseña FROM profesores WHERE email = %s", (email,))
        profesor = cur.fetchone()

        if profesor and verificar_contraseña(contraseña, profesor[3]):
            session['profesor_id'] = profesor[0]
            session['profesor_nombre'] = profesor[1]
            print(f"✅ Profesor autenticado, ID: {session['profesor_id']}")  #
            return redirect(url_for('dashboard_profesor'))
        else:
            flash('Correo o contraseña incorrectos')

    return render_template('login_profesor.html')

# ----------------- DASHBOARD ESTUDIANTES ---------------- #
@app.route('/dashboard_estudiante')
def dashboard_estudiante():
    if 'usuario_id' in session:
        cur = mysql.connection.cursor()
        cur.execute("SELECT cursos.nombre FROM matriculas INNER JOIN cursos ON matriculas.curso_id = cursos.id WHERE matriculas.usuario_id = %s", (session['usuario_id'],))
        cursos_inscritos = cur.fetchall()
        cur.close()

        return render_template('dashboard_estudiante.html', usuario=session['usuario_nombre'], cursos=cursos_inscritos)

    return redirect(url_for('login_estudiante'))  # 🔹 Si no hay sesión, redirige al login


# ----------------- DASHBOARD PROFESORES ---------------- #
@app.route('/dashboard_profesor')
def dashboard_profesor():
    if 'profesor_id' in session:
        cur = mysql.connection.cursor()

        cur.execute("SELECT COUNT(*) FROM cursos WHERE profesor_id = %s", (session['profesor_id'],))
        cursos_asignados = cur.fetchone()[0]

        cur.execute("""
            SELECT usuarios.nombre, cursos.nombre FROM matriculas 
            INNER JOIN usuarios ON matriculas.usuario_id = usuarios.id 
            INNER JOIN cursos ON matriculas.curso_id = cursos.id 
            INNER JOIN clases ON cursos.id = clases.curso_id 
            WHERE clases.profesor_id = %s
        """, (session['profesor_id'],))
        alumnos_matriculados = cur.fetchall()

        return render_template('dashboard_profesor.html', 
                               profesor_nombre=session['profesor_nombre'], 
                               alumnos=alumnos_matriculados, 
                               cursos_asignados=cursos_asignados)

    return redirect(url_for('login_profesor'))

# ----------------- EDITAR CURSOS ---------------- #
@app.route('/editar_cursos')
def editar_cursos():
    if 'profesor_id' in session:
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, nombre, cupos, estado FROM cursos WHERE profesor_id = %s", (session['profesor_id'],))
        cursos = cur.fetchall()
        cur.close()

        cursos_lista = [{'id': c[0], 'nombre': c[1], 'cupos': c[2], 'estado': c[3]} for c in cursos]

        return render_template('editar_cursos.html', profesor_nombre=session['profesor_nombre'], cursos=cursos_lista)

    flash('Acceso denegado')
    return redirect(url_for('login_profesor'))

@app.route('/editar_cupo', methods=['POST'])
def editar_cupo():
    curso_id = request.form.get('curso_id')
    cupos = request.form.get('cupos')

    if curso_id and cupos:
        cur = mysql.connection.cursor()
        cur.execute("UPDATE cursos SET cupos = %s WHERE id = %s", (cupos, curso_id))
        mysql.connection.commit()
        cur.close()

        return jsonify({"success": True, "message": "✅ Cupos actualizados correctamente"}) 
    return jsonify({"success": False, "message": "⚠️ Error al actualizar los cupos"})

#------------ CURSOS PROFESOR--------------#
@app.route('/cursos_profesor')
def cursos_profesor():
    if 'profesor_id' in session:
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, nombre, descripcion, cupos, estado, horario FROM cursos WHERE profesor_id = %s", (session['profesor_id'],))
        cursos = cur.fetchall()
        cur.close()

        cursos_lista = [{'id': c[0], 'nombre': c[1], 'descripcion': c[2], 'cupos': c[3], 'estado': c[4], 'horario': c[5]} for c in cursos]

        return render_template('cursos_profesor.html', cursos=cursos_lista)

    return redirect(url_for('login_profesor'))

#----------------ALUMNOS INSCRITOS-----------#
@app.route('/alumnos_inscritos')
def alumnos_inscritos():
    if 'profesor_id' in session:
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT cursos.id, cursos.nombre, cursos.descripcion, cursos.cupos, cursos.estado, cursos.horario,
                   (SELECT COUNT(*) FROM matriculas WHERE matriculas.curso_id = cursos.id) AS inscritos
            FROM cursos WHERE profesor_id = %s
        """, (session['profesor_id'],))
        cursos_data = cur.fetchall()

        cursos_lista = []
        for curso in cursos_data:
            cur.execute("SELECT usuarios.nombre FROM matriculas INNER JOIN usuarios ON matriculas.usuario_id = usuarios.id WHERE matriculas.curso_id = %s", (curso[0],))
            estudiantes = cur.fetchall()
            cursos_lista.append({
                'nombre': curso[1], 
                'descripcion': curso[2], 
                'cupos': curso[3], 
                'estado': curso[4], 
                'horario': curso[5],  # 🔹 Se agregó el horario aquí
                'inscritos': curso[6], 
                'estudiantes': [{'nombre': e[0]} for e in estudiantes]
            })

        cur.close()

        return render_template('alumnos_inscritos.html', cursos=cursos_lista)

    return redirect(url_for('login_profesor'))


#------------------ACTUALIZAR CURSO--------------#
@app.route('/actualizar_curso', methods=['POST'])
def actualizar_curso():
    curso_id = request.form['curso_id']
    nombre = request.form['nombre']
    descripcion = request.form['descripcion']
    cupos = request.form['cupos']
    estado = request.form['estado']
    horario = request.form['horario']

    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE cursos 
        SET nombre = %s, descripcion = %s, cupos = %s, estado = %s, horario = %s 
        WHERE id = %s
    """, (nombre, descripcion, cupos, estado, horario, curso_id))
    mysql.connection.commit()
    cur.close()

    return redirect(url_for('editar_cursos'))

#----------------INSCRIBIR CURSO-----------------#
@app.route('/inscribir_curso', methods=['POST'])
def inscribir_curso():
    if 'usuario_id' in session:
        curso_id = request.form['curso_id']
        
        cur = mysql.connection.cursor()

        # 🔍 Verificar si el estudiante ya está inscrito en el curso
        cur.execute("SELECT COUNT(*) FROM matriculas WHERE usuario_id = %s AND curso_id = %s", (session['usuario_id'], curso_id))
        ya_inscrito = cur.fetchone()[0]

        if ya_inscrito > 0:
            cur.close()
            return redirect(url_for('matricular'))  # 🔹 Redirige de nuevo a la página de inscripción

        # 📝 Registrar nueva inscripción
        cur.execute("INSERT INTO matriculas (usuario_id, curso_id) VALUES (%s, %s)", (session['usuario_id'], curso_id))
        mysql.connection.commit()

        # 📉 Reducir cupos disponibles
        cur.execute("UPDATE cursos SET cupos = cupos - 1 WHERE id = %s", (curso_id,))
        mysql.connection.commit()
        
        cur.close()

        return redirect(url_for('dashboard_estudiante'))

    return redirect(url_for('login_estudiante'))

#----------------- MIS CURSOS------------------------#
@app.route('/mis_cursos')
def mis_cursos():
    if 'usuario_id' in session:
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT c.nombre, c.horario, c.estado, p.nombre 
            FROM matriculas m
            INNER JOIN cursos c ON m.curso_id = c.id
            INNER JOIN profesores p ON c.profesor_id = p.id
            WHERE m.usuario_id = %s
        """, (session['usuario_id'],))
        cursos_inscritos = cur.fetchall()
        cur.close()

        cursos_lista = [{'nombre': c[0], 'horario': c[1], 'estado': c[2], 'docente': c[3]} for c in cursos_inscritos]

        return render_template('mis_cursos.html', cursos=cursos_lista)

    return redirect(url_for('login_estudiante'))

#----------------- PARA MATRICULAR EN MATERIA------------#
@app.route('/matriculacion')
def matricular():
    if 'usuario_id' in session:
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, nombre, horario, cupos, profesor_id FROM cursos WHERE estado = 'Activo'")
        cursos_data = cur.fetchall()

        cursos_lista = []
        for curso in cursos_data:
            cur.execute("SELECT nombre FROM profesores WHERE id = %s", (curso[4],))
            profesor = cur.fetchone()

            # 🔍 Verificar si el estudiante ya está inscrito en el curso
            cur.execute("SELECT COUNT(*) FROM matriculas WHERE usuario_id = %s AND curso_id = %s", (session['usuario_id'], curso[0]))
            ya_inscrito = cur.fetchone()[0] > 0  # 🔹 Devuelve True si ya está inscrito

            cursos_lista.append({
                'id': curso[0], 
                'nombre': curso[1], 
                'horario': curso[2], 
                'cupos': curso[3], 
                'docente': profesor[0] if profesor else "Desconocido",
                'ya_inscrito': ya_inscrito  # 🔹 Se agrega esta variable
            })

        cur.close()
        
        return render_template('matricular.html', cursos=cursos_lista)

    return redirect(url_for('login_estudiante'))

#------------------REGISTRO MATERIA----------#
@app.route('/registro_materia', methods=['GET', 'POST'])
def registro_materia():
    if request.method == 'POST':
        nombre_materia = request.form['nombre_materia']
        descripcion = request.form['descripcion']
        cupos = request.form['cupos']
        horario = request.form['horario']
        profesor_id = session.get('profesor_id')  # 🔹 Usamos `profesor_id` en sesión

        if not profesor_id:
            flash("❌ Error: No se ha encontrado el ID del profesor en sesión.")
            return redirect(url_for('dashboard_profesor'))

        cur = mysql.connection.cursor()
        try:
            cur.execute("""
                INSERT INTO cursos (nombre, descripcion, profesor_id, cupos, estado, horario) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (nombre_materia, descripcion, profesor_id, cupos, 'Activo', horario))
            mysql.connection.commit()
            print(f"✅ Materia '{nombre_materia}' guardada con `profesor_id`: {profesor_id}")
            flash("✅ Materia registrada exitosamente y vinculada al profesor.")
        except Exception as e:
            print(f"❌ Error al registrar materia: {e}")
            flash("❌ Ocurrió un problema al guardar la materia.")
        finally:
            cur.close()

        return redirect(url_for('dashboard_profesor'))

    return render_template('registro_materia.html')


#------------------ MIS HORARIOS -------------#
@app.route('/mis_horarios')
def mis_horarios():
    if 'usuario_id' in session:
        cur = mysql.connection.cursor()

        # 🔹 Obtener los horarios desde la tabla `cursos`
        cur.execute("SELECT nombre, horario FROM cursos WHERE id IN (SELECT curso_id FROM matriculas WHERE usuario_id = %s)", (session['usuario_id'],))
        horarios_estudiante = cur.fetchall()
        cur.close()

        return render_template('mis_horarios.html', usuario=session['usuario_nombre'], horarios=horarios_estudiante)

    return redirect(url_for('login_estudiante'))


#---------REPORTE ESTUDIANTE------------------#
@app.route('/reporte_estudiante')
def reporte_estudiante():
    if 'usuario_id' in session:
        cur = mysql.connection.cursor()
        cur.execute("SELECT nombre, horario FROM cursos WHERE id IN (SELECT curso_id FROM matriculas WHERE usuario_id = %s)", (session['usuario_id'],))
        cursos_inscritos = cur.fetchall()
        cur.close()

        # Crear el PDF
        filename = f"reporte_estudiante_{session['usuario_id']}.pdf"
        pdf = canvas.Canvas(filename, pagesize=letter)
        pdf.setTitle("Reporte de Materias Matriculadas")

        # Encabezado
        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawString(200, 750, "📚 Reporte de Materias Matriculadas")

        # Datos del estudiante
        pdf.setFont("Helvetica", 14)
        pdf.drawString(50, 720, f"Estudiante: {session['usuario_nombre']}")

        y = 690
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, y, "Materia")
        pdf.drawString(300, y, "Horario")
        y -= 30

        pdf.setFont("Helvetica", 12)
        for curso in cursos_inscritos:
            pdf.drawString(50, y, curso[0])
            pdf.drawString(300, y, curso[1])
            y -= 20

        pdf.save()
        return send_file(filename, as_attachment=True)

    return redirect(url_for('login'))


#----------------- REPORTE PROFESOR-------------#
@app.route('/reporte_profesor')
def reporte_profesor():
    if 'profesor_id' in session:
        cur = mysql.connection.cursor()

        # 🔹 Obtener los datos del profesor
        cur.execute("SELECT id, nombre, email FROM profesores WHERE id = %s", (session['profesor_id'],))
        profesor = cur.fetchone()

        # 🔹 Obtener materias asignadas al profesor
        cur.execute("SELECT nombre, horario FROM cursos WHERE profesor_id = %s", (session['profesor_id'],))
        materias = cur.fetchall()
        cur.close()

        # 🔹 Verificación de datos
        if not profesor:
            flash("❌ No se encontró el profesor en la base de datos.")
            return redirect(url_for('dashboard_profesor'))
        
        if not materias:
            flash("❌ No tienes materias registradas.")
            return redirect(url_for('dashboard_profesor'))

        # 🔹 Crear el PDF
        filename = f"reporte_profesor_{session['profesor_id']}.pdf"
        pdf = canvas.Canvas(filename, pagesize=letter)
        pdf.setTitle("Reporte de Materias del Profesor")

        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawString(200, 750, "📄 Reporte de Materias")
        pdf.setFont("Helvetica", 14)
        pdf.drawString(50, 720, f"Profesor: {profesor[1]} ({profesor[2]})")  

        y = 690
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, y, "Materia")
        pdf.drawString(300, y, "Horario")
        y -= 30

        pdf.setFont("Helvetica", 12)
        for materia in materias:
            pdf.drawString(50, y, materia[0])
            pdf.drawString(300, y, materia[1])
            y -= 20

        pdf.save()
        return send_file(filename, as_attachment=True, mimetype='application/pdf')

    flash("❌ Sesión no válida. Inicia sesión nuevamente.")
    return redirect(url_for('login_profesor'))
# ----------------- LOGOUT ---------------- #
@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada correctamente')
    return redirect(url_for('login_estudiante'))

if __name__ == '__main__':
    app.run(port=2199, debug=True)

