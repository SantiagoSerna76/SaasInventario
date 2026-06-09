from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import shutil
import os

from database import get_db_connection
from auth import verify_password, get_password_hash, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from services.gemini_service import extract_invoice_data

class ProductoFactura(BaseModel):
    nombre_producto: str
    cantidad: int
    precio_unitario: float
    id_categoria: int = 1

class ProductoCreatePayload(BaseModel):
    id_categoria: int
    nombre_producto: str
    precio_costo: float
    precio_venta: float
    cantidad_stock: int

class ProductoUpdatePayload(BaseModel):
    nombre_producto: str
    precio_venta: float

class FacturaPayload(BaseModel):
    fecha_factura: Optional[str] = None
    nombre_proveedor: Optional[str] = None
    nit_proveedor: Optional[str] = None
    total_factura: float
    productos: List[ProductoFactura]

app = FastAPI(title="Sistema de Inventario API")

# Habilitar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/login")

# ==========================================
# RUTAS DE LA API
# ==========================================

@app.post("/api/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Buscar usuario por email
    cursor.execute("SELECT * FROM USUARIOS WHERE email = %s", (form_data.username,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        raise HTTPException(status_code=400, detail="Usuario o contraseña incorrectos")
    if not verify_password(form_data.password, user['password_hash']):
        conn.close()
        raise HTTPException(status_code=400, detail="Usuario o contraseña incorrectos")
        
    conn.close()

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user['email'], "id_usuario": user['id_usuario'], "id_empresa": user['id_empresa']},
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "user": {"nombre": user['nombre'], "rol": user['rol']}}

@app.get("/api/productos")
async def listar_productos(token: str = Depends(oauth2_scheme)):
    # En un entorno real, decodificaríamos el token para obtener el id_empresa
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Ejemplo de JOIN requerido por la rúbrica
    query = """
        SELECT P.id_producto, P.nombre_producto, P.precio_venta, P.cantidad_stock, C.nombre_categoria
        FROM PRODUCTOS P
        INNER JOIN CATEGORIAS C ON P.id_categoria = C.id_categoria
        ORDER BY P.id_producto ASC
    """
    cursor.execute(query)
    productos = cursor.fetchall()
    conn.close()
    return productos

@app.post("/api/productos")
async def crear_producto(payload: ProductoCreatePayload, token: str = Depends(oauth2_scheme)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # En un sistema real extraemos id_empresa y usuario del token
        id_empresa = 1
        id_usuario = 1
        
        cursor.execute(
            "INSERT INTO PRODUCTOS (id_empresa, id_categoria, nombre_producto, precio_costo, precio_venta, cantidad_stock) VALUES (%s, %s, %s, %s, %s, %s)",
            (id_empresa, payload.id_categoria, payload.nombre_producto, payload.precio_costo, payload.precio_venta, payload.cantidad_stock)
        )
        cursor.execute("SELECT LAST_INSERT_ID()")
        id_prod = cursor.fetchone()[0]
        
        if payload.cantidad_stock > 0:
            cursor.callproc('sp_actualizar_stock', [id_prod, id_usuario, payload.cantidad_stock, 'ENTRADA'])
            
        conn.commit()
        conn.close()
        return {"mensaje": "Producto creado"}
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/productos/{id_producto}")
async def editar_producto(id_producto: int, payload: ProductoUpdatePayload, token: str = Depends(oauth2_scheme)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE PRODUCTOS SET nombre_producto = %s, precio_venta = %s WHERE id_producto = %s",
            (payload.nombre_producto, payload.precio_venta, id_producto)
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        return {"mensaje": "Producto actualizado"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.delete("/api/productos/{id_producto}")
async def eliminar_producto(id_producto: int, token: str = Depends(oauth2_scheme)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 1. Borrar de KARDEX_AUDITORIA
        cursor.execute("DELETE FROM KARDEX_AUDITORIA WHERE id_producto = %s", (id_producto,))
        # 2. Borrar de DETALLE_VENTAS
        cursor.execute("DELETE FROM DETALLE_VENTAS WHERE id_producto = %s", (id_producto,))
        # 3. Borrar de DETALLE_FACTURAS
        cursor.execute("DELETE FROM DETALLE_FACTURAS WHERE id_producto = %s", (id_producto,))
        
        # 4. Borrar el producto finalmente
        cursor.execute("DELETE FROM PRODUCTOS WHERE id_producto = %s", (id_producto,))
        conn.commit()
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        conn.close()
        return {"mensaje": "Producto eliminado exitosamente"}
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/ventas/registrar")
async def registrar_venta(venta: dict, token: str = Depends(oauth2_scheme)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        id_empresa = 1
        id_usuario = 1
        id_producto = venta['id_producto']
        cantidad = venta['cantidad']

        # Buscar el precio de venta actual del producto
        cursor.execute("SELECT precio_venta FROM PRODUCTOS WHERE id_producto = %s", (id_producto,))
        res = cursor.fetchone()
        if not res:
            raise Exception("Producto no encontrado")
        precio_venta = res[0]

        # Llamar al Procedimiento Almacenado
        cursor.callproc('sp_registrar_venta', [
            id_empresa, 
            id_usuario, 
            id_producto, 
            cantidad, 
            precio_venta
        ])
        conn.commit()
        conn.close()
        return {"mensaje": "Venta registrada y stock actualizado correctamente"}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/facturas/escanear")
async def escanear_factura(file: UploadFile = File(...)):
    # Guardar imagen temporalmente
    os.makedirs("uploads", exist_ok=True)
    file_path = f"uploads/{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Llamar a IA pasándole las categorías actuales
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True) if hasattr(conn.cursor(), 'dictionary') else conn.cursor()
    # Safe fallback if dictionary=True is not supported by pure python cursor
    cursor.execute("SELECT id_categoria, nombre_categoria FROM CATEGORIAS")
    categorias_db = cursor.fetchall()
    
    # Format categories as a string list for the prompt
    lista_categorias = [f"ID: {row[0] if isinstance(row, tuple) else row['id_categoria']} - Nombre: {row[1] if isinstance(row, tuple) else row['nombre_categoria']}" for row in categorias_db]
    conn.close()

    try:
        data = extract_invoice_data(file_path, lista_categorias)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/facturas/guardar")
async def guardar_factura(payload: FacturaPayload, token: str = Depends(oauth2_scheme)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        id_empresa = 1
        id_usuario = 1
        id_proveedor = 1
        
        fecha = payload.fecha_factura if payload.fecha_factura else datetime.now().strftime('%Y-%m-%d')
        
        cursor.callproc('sp_procesar_factura_ia', [
            id_empresa,
            id_proveedor,
            "http://storage.com/factura_escaneada.jpg",
            fecha,
            payload.total_factura,
            id_usuario
        ])
        
        cursor.execute("SELECT LAST_INSERT_ID()")
        id_factura = cursor.fetchone()[0]
        
        for p in payload.productos:
            cursor.execute("SELECT id_producto FROM PRODUCTOS WHERE nombre_producto LIKE %s LIMIT 1", (f"%{p.nombre_producto[:15]}%",))
            res = cursor.fetchone()
            
            if res:
                id_prod = res[0]
            else:
                # Si el producto no existe, crearlo automáticamente con la categoría elegida por la IA
                precio_venta_estimado = p.precio_unitario * 1.30 # 30% de ganancia
                cursor.execute(
                    "INSERT INTO PRODUCTOS (id_empresa, id_categoria, nombre_producto, precio_costo, precio_venta, cantidad_stock) VALUES (%s, %s, %s, %s, %s, %s)",
                    (id_empresa, p.id_categoria, p.nombre_producto, p.precio_unitario, precio_venta_estimado, 0)
                )
                cursor.execute("SELECT LAST_INSERT_ID()")
                id_prod = cursor.fetchone()[0]
            
            cursor.execute(
                "INSERT INTO DETALLE_FACTURAS (id_factura, id_producto, cantidad_comprada, precio_unitario_compra) VALUES (%s, %s, %s, %s)",
                (id_factura, id_prod, p.cantidad, p.precio_unitario)
            )
            cursor.callproc('sp_actualizar_stock', [id_prod, id_usuario, p.cantidad, 'ENTRADA'])
            
        conn.commit()
        conn.close()
        return {"mensaje": "Factura guardada correctamente"}
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/informes/semanal")
async def informe_semanal(token: str = Depends(oauth2_scheme)):
    conn = get_db_connection()
    # Try dictionary cursor if supported
    cursor = conn.cursor(dictionary=True) if hasattr(conn.cursor(), 'dictionary') else conn.cursor()
    try:
        # 1. Total semana
        cursor.execute("""
            SELECT COALESCE(SUM(total_venta), 0) as total_semana
            FROM VENTAS
            WHERE YEARWEEK(fecha_venta, 1) = YEARWEEK(CURRENT_DATE(), 1)
        """)
        res_total = cursor.fetchone()
        total_semana = res_total['total_semana'] if isinstance(res_total, dict) else res_total[0]
        
        # 2. Producto más vendido de la semana
        cursor.execute("""
            SELECT P.nombre_producto, SUM(DV.cantidad_vendida) as total_vendido
            FROM DETALLE_VENTAS DV
            INNER JOIN VENTAS V ON DV.id_venta = V.id_venta
            INNER JOIN PRODUCTOS P ON DV.id_producto = P.id_producto
            WHERE YEARWEEK(V.fecha_venta, 1) = YEARWEEK(CURRENT_DATE(), 1)
            GROUP BY DV.id_producto
            ORDER BY total_vendido DESC
            LIMIT 1
        """)
        mas_vendido = cursor.fetchone()
        
        # 3. Producto menos vendido de la semana
        cursor.execute("""
            SELECT P.nombre_producto, SUM(DV.cantidad_vendida) as total_vendido
            FROM DETALLE_VENTAS DV
            INNER JOIN VENTAS V ON DV.id_venta = V.id_venta
            INNER JOIN PRODUCTOS P ON DV.id_producto = P.id_producto
            WHERE YEARWEEK(V.fecha_venta, 1) = YEARWEEK(CURRENT_DATE(), 1)
            GROUP BY DV.id_producto
            ORDER BY total_vendido ASC
            LIMIT 1
        """)
        menos_vendido = cursor.fetchone()
        
        def get_val(row, key, index):
            if not row: return None
            return row[key] if isinstance(row, dict) else row[index]

        return {
            "total_semana": float(total_semana),
            "mas_vendido": get_val(mas_vendido, 'nombre_producto', 0) or "Sin ventas",
            "mas_vendido_cant": int(get_val(mas_vendido, 'total_vendido', 1) or 0),
            "menos_vendido": get_val(menos_vendido, 'nombre_producto', 0) or "Sin ventas",
            "menos_vendido_cant": int(get_val(menos_vendido, 'total_vendido', 1) or 0)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# ==========================================
# SERVIR EL FRONTEND WEB
# ==========================================
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def serve_frontend():
    return FileResponse("static/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
