from fastapi import FastAPI
from fastapi import File
from fastapi import UploadFile
import psycopg2
import re
import io
import os
import PyPDF2
from dotenv import dotenv_values
import urllib.request
import numpy as np
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()
config = dotenv_values()
DATABASE_URL = os.environ['DATABASE_URL']
#DATABASE_URL = 'postgres://uc8bn09h26evl1:pe6176f6730f4f560c5e06802fdc986b10a15bc9a1b612e6fcf5bd4c708c5b8df@c952v5ogavqpah.cluster-czrs8kj4isg7.us-east-1.rds.amazonaws.com:5432/dc9u2dqs3uerk8'

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class LoginReq(BaseModel):
    numemp: str
    password: str

#CREDENCIALES DEL PROFESOR
sesion = []



@app.post('/')
def registro():
    return 0

@app.post('/registro')
def registrarProfesor(numemp, nombreProfesor, correo, contraseña):
    try:
        conexion = psycopg2.connect(DATABASE_URL, sslmode='require')
        print("Conectado a la BD")
        #EN ESTA PARTE RECIBE LOS DATOS PARA REGISTRARSE COMO PROFESOR
        cursor = conexion.cursor()
        cursor.execute("CALL InsertProfesores(%s, %s, %s, %s)", (numemp, nombreProfesor, correo, contraseña))
        conexion.commit()
    except:
        print("No se puede acceder a la BD")
    finally:
        if conexion:
            conexion.close()

@app.post('/login')
def logIn(request:LoginReq):
    sesion.clear()
    try:
        #INICIAR LA CONEXIÓN PARA IDENTIFICAR QUE EL PROFESOR SI EXISTE
        conexion = psycopg2.connect(DATABASE_URL, sslmode='require')
        cursor = conexion.cursor()
        cursor.execute("SELECT * FROM Profesores WHERE Numeroempleado = %s AND Contrasena = %s", (request.numemp, request.password))
        if cursor.rowcount > 0:
            #ACCEDE A LA SIG PANTALLA
            print("Bienvenido")
            sesion.append(request.numemp)
            sesion.append(request.password)
        else:
            #MANDA ERROR
            print("No existe")
        conexion.commit()
    except:
        print(f"No se pudo conectar con la BD")
    finally:
        if conexion:
            conexion.close()

@app.delete('/destroythisworld')
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


@app.post('/grupo/')
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

@app.post('/grupo/{idGrupo}')
def asistir(secuencia, periodo, idMateria, codigoQR):
    #EXPRESIÓN REGULAR DE LA BOLETA
    boletaER = r'\d{10}|PE\d{8}'
    #LEER LA BOLETA DE LA URL
    response = urllib.request.urlopen(codigoQR)
    contenido = response.read().decode('utf-8')
    boleta = re.findall(boletaER, contenido)
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

@app.put('/grupo/{idGrupo}')
def modAsistencia(secuencia, periodo, idMateria, boleta, status):
    try:
        conexion = psycopg2.connect(DATABASE_URL, sslmode='require')
        cursor = conexion.cursor()
        cursor.execute("CALL ModAsistencia(%s, %s, %s, %s, %s);", (secuencia, periodo, idMateria, boleta, status))
        conexion.commit()
    except:
        print("No se puede acceder a la BD noob")
    finally:
        if conexion:
            conexion.close()
            
@app.get('/grupo/{idGrupo}')
def mostrarAsistencia(id_clase):
    try:
        conexion = psycopg2.connect(DATABASE_URL, sslmode='require')
        cursor = conexion.cursor()
        cursor.execute('SELECT DISTINCT CAST(Fecha AS VARCHAR) FROM Asistencia INNER JOIN Listas ON Asistencia.ID_Lista = Listas.ID_Lista WHERE ID_Clase = %s', (id_clase,))
        fechas = np.ravel(cursor.fetchall())
        cursor.execute('SELECT numerolista, a.Boleta, Nombre, CAST(Fecha AS VARCHAR), AoF FROM (SELECT * FROM Asistencia INNER JOIN Listas ON Asistencia.ID_Lista = Listas.ID_Lista WHERE ID_Clase = %s) AS a INNER JOIN Alumnos ON a.Boleta = Alumnos.boleta ORDER BY numerolista', (id_clase,))
        asistencias = cursor.fetchall()
        print(asistencias)
        conexion.commit()
    except:
        print("No se puede acceder a la BD noob")
    finally:
        if conexion:
            conexion.close()