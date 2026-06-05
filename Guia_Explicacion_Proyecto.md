# Guía Completa del Proyecto: SaaS Inventario con IA

Esta guía está diseñada para que puedas explicar paso a paso tu proyecto durante la presentación o el parcial. Cubre desde la arquitectura de la base de datos hasta cómo se conecta con la Inteligencia Artificial y el Backend.

---

## 1. Arquitectura General del Sistema

El proyecto sigue una arquitectura moderna dividida en tres capas:
1. **Frontend (Interfaz de Usuario):** Construido con HTML, CSS y JavaScript (Vanilla). Se encarga de mostrar la información, capturar interacciones (como subir la foto de la factura) y hacer peticiones (`fetch`) al servidor.
2. **Backend (Lógica de Servidor):** Construido en **Python** usando el framework **FastAPI**. Recibe peticiones, valida los datos con **Pydantic**, se comunica con la Inteligencia Artificial (Google Gemini) y ejecuta comandos en la base de datos.
3. **Base de Datos (Persistencia):** Construida en **MySQL**. No solo guarda tablas, sino que contiene lógica de negocio avanzada mediante **Funciones** y **Procedimientos Almacenados**.

---

## 2. Explicación de la Base de Datos (`database.sql`)

La base de datos cuenta con **10 tablas relacionadas**, diseñadas para soportar un modelo Multitenant (múltiples empresas o negocios en un solo sistema).

### Tablas Core (Catálogos)
- **`EMPRESAS`**: Es la tabla principal. Todo en el sistema le pertenece a una empresa (`id_empresa`).
- **`USUARIOS`**: Empleados de la empresa. Aquí se guarda la contraseña, pero **NUNCA en texto plano**; se guarda un `password_hash` por seguridad.
- **`PROVEEDORES`**: Quienes suministran los productos.
- **`CATEGORIAS`** y **`PRODUCTOS`**: La tabla `PRODUCTOS` tiene una llave foránea (`id_categoria`) que la une a la categoría, y otra a `id_empresa`. Guarda el `precio_costo`, `precio_venta` y `cantidad_stock`.

### Tablas Transaccionales (Movimientos)
- **`FACTURAS_COMPRA_IA`** y **`DETALLE_FACTURAS`**: Cuando la IA lee una factura, se guarda la "Cabecera" (quién es el proveedor, la fecha, el total) y el "Detalle" (cuántas unidades de cada producto se compraron).
- **`VENTAS`** y **`DETALLE_VENTAS`**: Sigue el mismo modelo Maestro-Detalle. Una venta general tiene muchos detalles (productos vendidos en ese ticket).

### Tabla de Auditoría
- **`KARDEX_AUDITORIA`**: Es el historial exacto. Si el stock de un producto cambia (por venta, compra o ajuste manual), se guarda **quién** lo hizo, **cuándo**, **qué tipo de movimiento** fue y la cantidad.

---

## 3. Lógica Avanzada SQL (Funciones y JOINs)

En lugar de hacer cálculos lentos en Python, la base de datos hace el trabajo pesado:

### Funciones (`CREATE FUNCTION`)
Son pedazos de código SQL que devuelven un valor.
- `fn_calcular_subtotal`: Multiplica cantidad por precio.
- `fn_validar_stock`: Retorna `TRUE` o `FALSE` verificando si un producto tiene suficiente `cantidad_stock` antes de permitir una venta.
- `fn_total_ventas_mes`: Hace un **SUM** de las ventas filtrando por el mes actual.

### JOINs (Unión de Tablas)
Se usan cuando el frontend necesita datos legibles. Por ejemplo, en `main.py` hacemos:
```sql
SELECT P.id_producto, P.nombre_producto, P.precio_venta, P.cantidad_stock, C.nombre_categoria
FROM PRODUCTOS P
INNER JOIN CATEGORIAS C ON P.id_categoria = C.id_categoria
ORDER BY P.id_producto ASC
```
Esto une la tabla de `PRODUCTOS` (que solo tiene números de ID) con la de `CATEGORIAS`, para devolver la palabra "Lácteos" o "Cereales" a la página web.

---

## 4. Procedimientos Almacenados (`CREATE PROCEDURE`)

Los "Stored Procedures" o SPs son rutinas completas. Su mayor ventaja es garantizar que múltiples operaciones de base de datos se ejecuten como una sola **transacción segura**.

### El mejor ejemplo: `sp_registrar_venta`
Cuando alguien hace una venta en la página web, el Backend NO hace múltiples `INSERT` y `UPDATE`. Solo llama a `CALL sp_registrar_venta()`.
**¿Qué hace este SP por dentro?**
1. Llama a la función `fn_validar_stock` para asegurarse de que no se venda algo que no existe.
2. Si hay stock, inserta la venta en `VENTAS`.
3. Inserta el producto en `DETALLE_VENTAS`.
4. Llama a otro procedimiento (`sp_actualizar_stock`) que **descuenta el stock** en `PRODUCTOS` y **registra el movimiento** en el `KARDEX_AUDITORIA`.
*¡Todo en un solo llamado desde Python!*

---

## 5. El Backend en Python (`main.py`)

### Modelos y Pydantic
Usamos clases como `ProductoCreatePayload(BaseModel)`. Esto sirve de "portero de discoteca". Si la página web intenta enviar un producto pero olvida incluir el `precio_venta` o envía texto en vez de números, **Pydantic** rechaza la petición (Error 422) antes de que el código intente guardarlo, evitando que la base de datos falle.

### Seguridad y Login (Hashes)
**¿Cómo funciona el Login?**
1. El usuario digita su correo y clave en la web.
2. La web lo manda a la ruta `@app.post("/api/login")`.
3. Python va a la DB y trae el `password_hash` de ese usuario.
4. Usa una librería de criptografía (`bcrypt`) para calcular si la clave que digitó el usuario genera el mismo hash.
5. Si es correcto, Python emite un **Token JWT (JSON Web Token)**. El navegador guarda ese token y se lo envía a Python en cada clic futuro para demostrar que es un usuario autorizado.

**¿Cómo sería un Registro?**
Simplemente haríamos un nuevo endpoint donde el usuario envía su clave nueva, Python la encripta con `bcrypt.hashpw()` y hace un `INSERT INTO USUARIOS (email, password_hash)`.

### Integración con Inteligencia Artificial
El ciclo de vida de la factura escaneada:
1. El usuario sube la foto. JS hace un `fetch` hacia `@app.post("/api/facturas/escanear")`.
2. `main.py` recibe la foto y usa el SDK de Google (`google-genai`) para llamar al modelo **Gemini 2.5 Flash**.
3. Se le envía la foto y un "Prompt" estricto diciéndole que actúe como un extractor de datos y retorne un formato **JSON**.
4. Gemini lee la imagen, reconoce el texto (OCR y NLP) y devuelve el JSON.
5. El JSON se muestra en la web. Cuando el usuario da clic en "Guardar", se envía al endpoint `/api/facturas/guardar`.
6. Python itera la lista. Si el producto ya existe, actualiza el stock llamando al SP. **Si no existe, el sistema lo inserta como nuevo producto** automáticamente y le calcula un precio de venta.

---
*Fin de la guía. ¡Mucho éxito en tu presentación, dominas toda la lógica del sistema!*
