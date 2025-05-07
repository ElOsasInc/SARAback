from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import psycopg2
import base64
import re
import io
import os
import PyPDF2
import numpy as np
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import random


upiicsara = FastAPI()
DATABASE_URL = os.environ['DATABASE_URL']
#DATABASE_URL = 'postgres://uc8bn09h26evl1:pe6176f6730f4f560c5e06802fdc986b10a15bc9a1b612e6fcf5bd4c708c5b8df@c952v5ogavqpah.cluster-czrs8kj4isg7.us-east-1.rds.amazonaws.com:5432/dc9u2dqs3uerk8'

upiicsara.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://upiicsara.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class LoginReq(BaseModel):
    numemp: str
    password: str

class SignUpReq(BaseModel):
    numemp: str
    nombreProfesor:str
    correo:str
    password: str
    
class RecoveryReq(BaseModel):
    numemp: str
    correo: str
    
class PasswordData(BaseModel):
    password: str

#CREDENCIALES DEL PROFESOR
sesion = []



@upiicsara.post('/')
def registro():
    return 0

@upiicsara.post('/registro')
def registrarProfesor(request:SignUpReq):
    try:
        conexion = psycopg2.connect(DATABASE_URL, sslmode='require')
        print("Conectado a la BD")
        #EN ESTA PARTE RECIBE LOS DATOS PARA REGISTRARSE COMO PROFESOR
        cursor = conexion.cursor()
        cursor.execute("CALL InsertProfesores(%s, %s, %s, %s)", (request.numemp, request.nombreProfesor, request.correo, request.password))
        conexion.commit()
    except:
        print("No se puede acceder a la BD")
    finally:
        if conexion:
            conexion.close()

@upiicsara.post('/login')
def logIn(request:LoginReq):
    sesion.clear()
    respuesta = False
    try:
        #INICIAR LA CONEXIÓN PARA IDENTIFICAR QUE EL PROFESOR SI EXISTE
        conexion = psycopg2.connect(DATABASE_URL, sslmode='require')
        cursor = conexion.cursor()
        cursor.execute("SELECT * FROM Profesores WHERE Numeroempleado = %s AND Contrasena = %s", (request.numemp, request.password))
        resultado = cursor.fetchone()
        cursor.execute("DELETE FROM Invitados WHERE Hora_Caducidad < (NOW() AT TIME ZONE 'America/Mexico_City');")
        if resultado:
            #ACCEDE A LA SIG PANTALLA
            sesion.append(request.numemp)
            sesion.append(request.password)
            respuesta = True
            print("Bienvenido")
        else:
            #MANDA ERROR
            respuesta = False
            print("No existe")
        conexion.commit()
        return respuesta
    except:
        print(f"No se pudo conectar con la BD")
        return False
    finally:
        if conexion:
            conexion.close()

@upiicsara.delete('/destroythisworld')
def borrartodo():
    try:
        conexion = psycopg2.connect(DATABASE_URL, sslmode='require')
        print("Conectado a la BD")
        tablas=['asistencia', 'clases', 'profesores', 'secuencias', 'alumnos']
        cursor = conexion.cursor()
        #for tabla in tablas:
        cursor.executemany("DELETE FROM %s;", tablas)
        conexion.commit()
        print("Registros eliminados")
    except:
        print("No se puede acceder a la BD")
    finally:
        if conexion:
            conexion.close()


@upiicsara.post('/grupo/')
async def subirGrupo(file: UploadFile = File(...)):
    #EXPRESIONES REGULARES
    secuenciaER = r'\d[A-Z][MV]\d{2}'
    materiaER = r'(?P<clave>[A-Z]\d{3})\ (?P<materia>(\ ?[A-ZÑÁÉÍÓÚ])+)'
    periodoER = r'\d{5}'
    alumnoER = r'(?P<boleta>\d{10}|PE\d{8})\s(?P<nl>\d{1,2})\s(?P<nombre>(\ ?[A-ZÑ])+)'
    #IDENTIFICACIÓN DEL ARCHIVO PDF
    contenido = await file.read()
    archivo = io.BytesIO(contenido)
    #CREACIÓN DEL LECTOR DEL ARCHIVO
    lector = PyPDF2.PdfReader(archivo)
    #EXTRACCIÓN DEL TEXTO
    texto = ""
    for pagina in lector.pages:
        texto = texto + pagina.extract_text()
    #EXTRACCIÓN DE LOS VALORES
    #CADA UNA DE LAS VARIABLES TENDRÁ SU INSERCIÓN A BD
    invBoletas = []
    invNL = []
    invNombres = []
    secuencia = re.search(secuenciaER, texto).group(0)
    clave = re.sub("PERIODO ESCOLAR", "", re.search(materiaER, texto).group(1))
    materia = re.sub("PERIODO ESCOLAR", "", re.search(materiaER, texto).group(2))
    periodo = re.search(periodoER, texto).group(0)
    for alumno in re.findall(alumnoER, texto):
        invBoletas.append(alumno[0])
        invNL.append(alumno[1])
        invNombres.append(alumno[2])
    #CONSULTAS A BD
    try:
        #INICIAR LA CONEXIÓN
        conexion = psycopg2.connect(DATABASE_URL, sslmode='require')
        print("Conectado a la BD")
        cursor = conexion.cursor()
        cursor.execute("SELECT * FROM Secuencias WHERE Secuencia = %s AND Periodo = %s;", (secuencia, periodo))
        if cursor.rowcount < 1:
            cursor.execute("CALL InsertSecuencias(%s, %s);", (secuencia, periodo))
        cursor.execute("SELECT * FROM Materias WHERE ID_Materia = %s AND Materia = %s;", (clave, materia))
        if cursor.rowcount < 1:
            cursor.execute("CALL InsertMaterias(%s, %s);", (clave, materia))
        id_clase = f"{secuencia}{periodo}{clave}"
        cursor.execute("SELECT * FROM Clases WHERE ID_Clase = %s AND NumeroEmpleado = %s", (id_clase, sesion[0]))
        if cursor.rowcount < 1:
            cursor.execute("CALL InsertClases(%s, %s, %s, %s)", (secuencia, periodo, clave, sesion[0]))
        for alumno in range(len(invBoletas)):
            cursor.execute("SELECT * FROM Alumnos WHERE Boleta = %s AND Nombre = %s", (invBoletas[alumno], invNombres[alumno]))
            if cursor.rowcount < 1:
                cursor.execute("CALL InsertAlumnos(%s, %s)", (invBoletas[alumno], invNombres[alumno]))
            cursor.execute("SELECT * FROM Listas WHERE ID_Clase = %s AND Boleta = %s", (id_clase, invBoletas[alumno]))
            if cursor.rowcount < 1:
                cursor.execute("CALL InsertListas(%s, %s, %s, %s, %s)", (secuencia, periodo, clave, invBoletas[alumno], invNL[alumno]))
        conexion.commit()
    #ERROR EN CASO DE QUE NO PUEDA CONECTARSE
    except psycopg2.Error as error:
        print("Error al conectar con la Base de Datos", error)
    #CERRAR LA CONEXIÓN
    finally:
        if conexion:
            conexion.close()
            
@upiicsara.post('/grupo/{idGrupo}') #La neta ya me cansé xd 4:35 29/04
def asistir(secuencia:str, periodo:str, idMateria:str, boleta:int):
    try:
        conexion = psycopg2.connect(DATABASE_URL, sslmode='require')
        cursor = conexion.cursor()
        cursor.execute("CALL InsertNuevaAsistencia(%s, %s, %s, %s);", (secuencia, periodo, idMateria, boleta))
        conexion.commit()
    except:
        print("No se puede acceder a la BD")
    finally:
        if conexion:
            conexion.close()

@upiicsara.put('/grupo/{idGrupo}') #La neta ya me cansé xd 4:35 29/04
def modAsistencia(secuencia:str, periodo:str, idMateria:str, boleta:int, fecha:str, cambio:bool):
    print(secuencia, periodo, idMateria, boleta, fecha, cambio)
    try:
        conexion = psycopg2.connect(DATABASE_URL, sslmode='require')
        cursor = conexion.cursor()
        cursor.execute("SELECT numerolista FROM Listas WHERE ID_Clase = %s AND Boleta = %s", ((secuencia+periodo+idMateria), boleta))
        numerolista = cursor.fetchone()
        print(numerolista[0])
        cursor.execute("CALL ModAsistencia(%s, %s, %s, %s, %s, %s);", (secuencia, periodo, idMateria, numerolista[0], fecha, cambio))
        conexion.commit()
        print("Asistencia actualizada")
    except:
        print("No fue posible actualizar la asistencia")
    finally:
        if conexion:
            conexion.close()

            
@upiicsara.get('/grupo/{idGrupo}')
def mostrarAsistencia(idGrupo:str):
    fechas = []
    clases = []
    asistencias = []
    alumnos = []
    profesor = []
    try:
        conexion = psycopg2.connect(DATABASE_URL, sslmode='require')
        cursor = conexion.cursor()
        cursor.execute('SELECT DISTINCT CAST(Fecha AS VARCHAR) FROM Asistencia INNER JOIN Listas ON Asistencia.ID_Lista = Listas.ID_Lista WHERE ID_Clase = %s', (idGrupo,))
        fechas = cursor.fetchall()
        fechas = [{
            "Fecha": fecha
        } for fecha in fechas]
        print(fechas)
        cursor.execute('SELECT numerolista, a.Boleta, Nombre, CAST(Fecha AS VARCHAR), AoF, Hora FROM (SELECT * FROM Asistencia INNER JOIN Listas ON Asistencia.ID_Lista = Listas.ID_Lista WHERE ID_Clase = %s) AS a INNER JOIN Alumnos ON a.Boleta = Alumnos.boleta ORDER BY numerolista', (idGrupo,))
        asistencias = cursor.fetchall()
        asistencias = [{
            "NumeroLista": asistencia[0],
            "Boleta": asistencia[1],
            "Nombre": asistencia[2],
            "Fecha": asistencia[3],
            "Asistencia": asistencia[4],
            "Hora": asistencia[5]
        } for asistencia in asistencias]
        print(asistencias)
        cursor.execute('SELECT Secuencia, Periodo, a.ID_Materia, Materia FROM (SELECT * FROM Clases INNER JOIN Secuencias ON Clases.ID_Secuencia = Secuencias.ID_Secuencia WHERE ID_Clase = %s) AS a INNER JOIN Materias ON Materias.ID_Materia = a.ID_Materia', (idGrupo,))
        clases = cursor.fetchall()
        clases = [{
            "Secuencia": clase[0],
            "Periodo": clase[1],
            "ID_Materia": clase[2],
            "Materia": clase[3]
        } for clase in clases]
        print(clases)
        cursor.execute('SELECT DISTINCT numerolista, Listas.Boleta, Nombre FROM Listas INNER JOIN Alumnos ON Listas.Boleta = Alumnos.Boleta WHERE ID_Clase = %s ORDER BY numerolista', (idGrupo,))
        alumnos = cursor.fetchall()
        alumnos = [{
            "NumeroLista": alumno[0],
            "Boleta": alumno[1],
            "Nombre": alumno[2] 
        } for alumno in alumnos]
        print(alumnos)
        cursor.execute('SELECT numeroempleado FROM Clases WHERE ID_Clase = %s AND ID_Clase = %s', (idGrupo,idGrupo))
        profesor = cursor.fetchone()
        profesor=[{
            "Profesor": profesor[0]
        }]
        print(profesor)

        conexion.commit()
    except:
        print("No se puede acceder a la BD noob")
    finally:
        if conexion:
            conexion.close()
        return JSONResponse(content={"clases":clases, "fechas":fechas, "asistencias":asistencias, "alumnos":alumnos, "profesor":profesor})
            
@upiicsara.get('/grupo/')
def getSecuencias():
    clases = []
    try:
        conexion = psycopg2.connect(DATABASE_URL, sslmode='require')
        cursor = conexion.cursor()
        cursor.execute('SELECT Secuencia, Periodo, a.ID_Materia, Materia FROM (SELECT * FROM Clases INNER JOIN Secuencias ON Clases.ID_Secuencia = Secuencias.ID_Secuencia WHERE numeroempleado = %s) AS a INNER JOIN Materias ON Materias.ID_Materia = a.ID_Materia', (sesion[0],))
        clases = cursor.fetchall()
        clases = [{
            "Secuencia": clase[0],
            "Periodo": clase[1],
            "ID_Materia": clase[2],
            "Materia": clase[3]
        } for clase in clases]
        print(clases)
        conexion.commit()
    except:
        print("No se puede acceder a la BD xd")
    finally:
        if conexion:
            conexion.close()
        return JSONResponse(content=clases)

@upiicsara.post('/recuperar-cuenta/')
def mandarCorreo(request:RecoveryReq):
    print(request.numemp, request.correo)
    try:
        conexion = psycopg2.connect(DATABASE_URL, sslmode='require')
        cursor = conexion.cursor()
        cursor.execute('SELECT * FROM Profesores WHERE NumeroEmpleado = %s AND Correo = %s', (request.numemp, request.correo))
        Profesor_Existe = cursor.fetchone()
        print(Profesor_Existe)
        if Profesor_Existe:
            smtp_server = os.environ['SMTP_SERVER']
            print(smtp_server)
            smtp_port = os.environ['SMTP_PORT']
            smtp_user = os.environ['SMTP_USER']
            smtp_password = os.environ['SMTP_PASSWORD']
            smtp_destiny = request.correo
            msg = MIMEMultipart()
            msg['From'] = smtp_user
            msg['To'] = smtp_destiny
            msg['Subject'] = 'Recuperación de contraseña'
            #CUERPO DEL MSJ NO SE Q PONER XD
            password = ""
            for i in range(10):
                i = random.randint(0, 9)
                password = f'{password}{i}'
            cursor.execute('UPDATE Profesores SET contrasena = %s WHERE NumeroEmpleado = %s', (password, request.numemp))
            conexion.commit()
            body = f'Usted solicitó un cambio de contraseña, su nueva contraseña es:\n\n{password}\n\nEn su siguiente inicio de sesión cambie su contraseña por una propia.'
            msg.attach(MIMEText(body, 'plain'))
            try:
                server = smtplib.SMTP(smtp_server, smtp_port)
                server.starttls()
                server.login(smtp_user, smtp_password)
                text = msg.as_string()
                server.sendmail(smtp_user, smtp_destiny, text)
                server.quit()
                print("Correo enviado exitosamente")
            except Exception as e:
                print(f"Error al enviar el correo: {e}")
        else:
            print("El profesor no existe")
    except Exception as error:
        print(f"No se puede acceder a la BD xd {error}")
    finally:
        if conexion:
            conexion.close()

@upiicsara.post('/nuevoinvitado/')
def nuevoInvitado(idClase:str):
    respuesta = ""
    try:
        conexion = psycopg2.connect(DATABASE_URL, sslmode='require')
        cursor = conexion.cursor()
        invitado = ""
        while True:
            for i in range(5):
                i = random.randint(0, 9)
                invitado = f'{invitado}{i}'
            cursor.execute('SELECT ID_Invitado FROM Invitados WHERE ID_Invitado = %s', (invitado,))
            Invitado_Existe = cursor.fetchone()
            if Invitado_Existe:
                print("Volviendo a generar invitado")
            else:
                break
        cursor.execute('CALL InsertInvitado(%s, %s)', (invitado, idClase))
        respuesta = invitado
    except:
        print("No se puede acceder a la BD gay")
        respuesta = False
    finally:
        if conexion:
            conexion.close()
        return respuesta
    
@upiicsara.post('/login-invitado/')
def loginInvitado(invitado:int):
    respuesta = False
    try:
        conexion = psycopg2.connect(DATABASE_URL, sslmode='require')
        cursor = conexion.cursor()
        cursor.execute('SELECT * FORM ID_Invitado = %s', (invitado,))
        Invitado_Existe = cursor.fetchone()
        if Invitado_Existe:
            respuesta = True
    except:
        print("No se puede acceder a la BD gay")
        respuesta = False
    finally:
        if conexion:
            conexion.close()
        return respuesta
    
@upiicsara.put('/cambiar-password/')
def cambiarPassword(request:PasswordData):
    try:
        conexion = psycopg2.connect(DATABASE_URL, sslmode='require')
        cursor = conexion.cursor()
        cursor.execute('UPDATE Profesores SET contrasena = %s WHERE NumeroEmpleado = %s', (request.password, sesion[0]))
        conexion.commit()
    except:
        print("No se puede acceder a la BD gay")
    finally:
        if conexion:
            conexion.close()