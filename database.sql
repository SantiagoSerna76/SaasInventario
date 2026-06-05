-- ==========================================
-- SCRIPT DE BASE DE DATOS: SISTEMA INVENTARIO
-- Motor: MySQL
-- ==========================================

DROP DATABASE IF EXISTS sistema_inventario_db;
CREATE DATABASE sistema_inventario_db;
USE sistema_inventario_db;

-- 1. TABLA EMPRESAS
CREATE TABLE EMPRESAS (
    id_empresa INT AUTO_INCREMENT PRIMARY KEY,
    nombre_negocio VARCHAR(100) NOT NULL,
    nit_documento VARCHAR(50) NOT NULL UNIQUE,
    fecha_suscripcion DATE NOT NULL
);

-- 2. TABLA USUARIOS (Incluye campos para validación de login y bloqueos)
CREATE TABLE USUARIOS (
    id_usuario INT AUTO_INCREMENT PRIMARY KEY,
    id_empresa INT NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    rol VARCHAR(50) NOT NULL DEFAULT 'vendedor',
    FOREIGN KEY (id_empresa) REFERENCES EMPRESAS(id_empresa) ON DELETE CASCADE
);

-- 3. TABLA PROVEEDORES
CREATE TABLE PROVEEDORES (
    id_proveedor INT AUTO_INCREMENT PRIMARY KEY,
    id_empresa INT NOT NULL,
    nombre_proveedor VARCHAR(100) NOT NULL,
    telefono_contacto VARCHAR(20),
    FOREIGN KEY (id_empresa) REFERENCES EMPRESAS(id_empresa) ON DELETE CASCADE
);

-- 4. TABLA CATEGORIAS
CREATE TABLE CATEGORIAS (
    id_categoria INT AUTO_INCREMENT PRIMARY KEY,
    id_empresa INT NOT NULL,
    nombre_categoria VARCHAR(50) NOT NULL,
    FOREIGN KEY (id_empresa) REFERENCES EMPRESAS(id_empresa) ON DELETE CASCADE
);

-- 5. TABLA PRODUCTOS
CREATE TABLE PRODUCTOS (
    id_producto INT AUTO_INCREMENT PRIMARY KEY,
    id_empresa INT NOT NULL,
    id_categoria INT NOT NULL,
    nombre_producto VARCHAR(100) NOT NULL,
    precio_costo DECIMAL(10, 2) NOT NULL,
    precio_venta DECIMAL(10, 2) NOT NULL,
    cantidad_stock INT NOT NULL DEFAULT 0,
    FOREIGN KEY (id_empresa) REFERENCES EMPRESAS(id_empresa) ON DELETE CASCADE,
    FOREIGN KEY (id_categoria) REFERENCES CATEGORIAS(id_categoria) ON DELETE RESTRICT
);

-- 6. TABLA FACTURAS_COMPRA_IA (Módulo de escaneo)
CREATE TABLE FACTURAS_COMPRA_IA (
    id_factura INT AUTO_INCREMENT PRIMARY KEY,
    id_empresa INT NOT NULL,
    id_proveedor INT NOT NULL,
    url_imagen_escaneada TEXT,
    fecha_factura DATE NOT NULL,
    total_factura DECIMAL(12, 2) NOT NULL,
    FOREIGN KEY (id_empresa) REFERENCES EMPRESAS(id_empresa) ON DELETE CASCADE,
    FOREIGN KEY (id_proveedor) REFERENCES PROVEEDORES(id_proveedor) ON DELETE RESTRICT
);

-- 7. TABLA DETALLE_FACTURAS
CREATE TABLE DETALLE_FACTURAS (
    id_detalle_factura INT AUTO_INCREMENT PRIMARY KEY,
    id_factura INT NOT NULL,
    id_producto INT NOT NULL,
    cantidad_comprada INT NOT NULL,
    precio_unitario_compra DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (id_factura) REFERENCES FACTURAS_COMPRA_IA(id_factura) ON DELETE CASCADE,
    FOREIGN KEY (id_producto) REFERENCES PRODUCTOS(id_producto) ON DELETE RESTRICT
);

-- 8. TABLA VENTAS
CREATE TABLE VENTAS (
    id_venta INT AUTO_INCREMENT PRIMARY KEY,
    id_empresa INT NOT NULL,
    id_usuario INT NOT NULL,
    fecha_venta DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    total_venta DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    FOREIGN KEY (id_empresa) REFERENCES EMPRESAS(id_empresa) ON DELETE CASCADE,
    FOREIGN KEY (id_usuario) REFERENCES USUARIOS(id_usuario) ON DELETE RESTRICT
);

-- 9. TABLA DETALLE_VENTAS
CREATE TABLE DETALLE_VENTAS (
    id_detalle_venta INT AUTO_INCREMENT PRIMARY KEY,
    id_venta INT NOT NULL,
    id_producto INT NOT NULL,
    cantidad_vendida INT NOT NULL,
    subtotal DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (id_venta) REFERENCES VENTAS(id_venta) ON DELETE CASCADE,
    FOREIGN KEY (id_producto) REFERENCES PRODUCTOS(id_producto) ON DELETE RESTRICT
);

-- 10. TABLA KARDEX_AUDITORIA
CREATE TABLE KARDEX_AUDITORIA (
    id_movimiento INT AUTO_INCREMENT PRIMARY KEY,
    id_producto INT NOT NULL,
    id_usuario INT NOT NULL,
    tipo_movimiento ENUM('ENTRADA', 'SALIDA', 'AJUSTE') NOT NULL,
    cantidad_movida INT NOT NULL,
    fecha_movimiento DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_producto) REFERENCES PRODUCTOS(id_producto) ON DELETE CASCADE,
    FOREIGN KEY (id_usuario) REFERENCES USUARIOS(id_usuario) ON DELETE RESTRICT
);

-- ==========================================
-- FUNCIONES SQL
-- ==========================================
DELIMITER //

-- 1. Calcular el subtotal de un producto (cantidad * precio)
CREATE FUNCTION fn_calcular_subtotal(p_cantidad INT, p_precio DECIMAL(10, 2)) 
RETURNS DECIMAL(10,2) DETERMINISTIC
BEGIN
    RETURN p_cantidad * p_precio;
END //

-- 2. Validar si hay stock suficiente para una venta
CREATE FUNCTION fn_validar_stock(p_id_producto INT, p_cantidad_requerida INT) 
RETURNS BOOLEAN DETERMINISTIC
BEGIN
    DECLARE v_stock_actual INT;
    SELECT cantidad_stock INTO v_stock_actual FROM PRODUCTOS WHERE id_producto = p_id_producto;
    IF v_stock_actual >= p_cantidad_requerida THEN
        RETURN TRUE;
    ELSE
        RETURN FALSE;
    END IF;
END //

-- 3. Calcular impuesto (IVA 19%)
CREATE FUNCTION fn_calcular_impuesto(p_subtotal DECIMAL(12,2)) 
RETURNS DECIMAL(12,2) DETERMINISTIC
BEGIN
    RETURN p_subtotal * 0.19;
END //

-- 4. Obtener total de ventas del mes por empresa
CREATE FUNCTION fn_total_ventas_mes(p_id_empresa INT) 
RETURNS DECIMAL(12,2) DETERMINISTIC
BEGIN
    DECLARE v_total DECIMAL(12,2);
    SELECT COALESCE(SUM(total_venta), 0) INTO v_total 
    FROM VENTAS 
    WHERE id_empresa = p_id_empresa 
    AND MONTH(fecha_venta) = MONTH(CURRENT_DATE())
    AND YEAR(fecha_venta) = YEAR(CURRENT_DATE());
    RETURN v_total;
END //

DELIMITER ;

-- ==========================================
-- PROCEDIMIENTOS ALMACENADOS
-- ==========================================
DELIMITER //

-- 1. Registrar un nuevo usuario de forma segura
CREATE PROCEDURE sp_registrar_usuario(
    IN p_id_empresa INT,
    IN p_nombre VARCHAR(100),
    IN p_email VARCHAR(100),
    IN p_hash VARCHAR(255),
    IN p_rol VARCHAR(50)
)
BEGIN
    INSERT INTO USUARIOS (id_empresa, nombre, email, password_hash, rol)
    VALUES (p_id_empresa, p_nombre, p_email, p_hash, p_rol);
END //

-- 2. Actualizar inventario (Entrada/Salida/Ajuste)
CREATE PROCEDURE sp_actualizar_stock(
    IN p_id_producto INT,
    IN p_id_usuario INT,
    IN p_cantidad INT,
    IN p_tipo_movimiento VARCHAR(20)
)
BEGIN
    -- Registrar en Kardex
    INSERT INTO KARDEX_AUDITORIA (id_producto, id_usuario, tipo_movimiento, cantidad_movida)
    VALUES (p_id_producto, p_id_usuario, p_tipo_movimiento, p_cantidad);
    
    -- Actualizar Stock en Producto
    IF p_tipo_movimiento = 'ENTRADA' THEN
        UPDATE PRODUCTOS SET cantidad_stock = cantidad_stock + p_cantidad WHERE id_producto = p_id_producto;
    ELSEIF p_tipo_movimiento = 'SALIDA' THEN
        UPDATE PRODUCTOS SET cantidad_stock = cantidad_stock - p_cantidad WHERE id_producto = p_id_producto;
    ELSEIF p_tipo_movimiento = 'AJUSTE' THEN
        -- El ajuste setea la cantidad exacta
        UPDATE PRODUCTOS SET cantidad_stock = p_cantidad WHERE id_producto = p_id_producto;
    END IF;
END //

-- 3. Registrar Venta y Descontar Stock
CREATE PROCEDURE sp_registrar_venta(
    IN p_id_empresa INT,
    IN p_id_usuario INT,
    IN p_id_producto INT,
    IN p_cantidad INT,
    IN p_precio_venta DECIMAL(10,2)
)
BEGIN
    DECLARE v_id_venta INT;
    DECLARE v_subtotal DECIMAL(10,2);
    
    -- Validar Stock
    IF fn_validar_stock(p_id_producto, p_cantidad) = TRUE THEN
        -- Calcular subtotal
        SET v_subtotal = fn_calcular_subtotal(p_cantidad, p_precio_venta);
        
        -- Crear Venta
        INSERT INTO VENTAS (id_empresa, id_usuario, fecha_venta, total_venta)
        VALUES (p_id_empresa, p_id_usuario, NOW(), v_subtotal);
        
        SET v_id_venta = LAST_INSERT_ID();
        
        -- Detalle Venta
        INSERT INTO DETALLE_VENTAS (id_venta, id_producto, cantidad_vendida, subtotal)
        VALUES (v_id_venta, p_id_producto, p_cantidad, v_subtotal);
        
        -- Actualizar Stock y Kardex
        CALL sp_actualizar_stock(p_id_producto, p_id_usuario, p_cantidad, 'SALIDA');
    ELSE
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Stock insuficiente para la venta';
    END IF;
END //

-- 4. Registrar Factura desde IA
CREATE PROCEDURE sp_procesar_factura_ia(
    IN p_id_empresa INT,
    IN p_id_proveedor INT,
    IN p_url_imagen TEXT,
    IN p_fecha DATE,
    IN p_total DECIMAL(12,2),
    IN p_id_usuario INT -- Para el kardex
)
BEGIN
    INSERT INTO FACTURAS_COMPRA_IA (id_empresa, id_proveedor, url_imagen_escaneada, fecha_factura, total_factura)
    VALUES (p_id_empresa, p_id_proveedor, p_url_imagen, p_fecha, p_total);
    -- Los detalles se insertarían secuencialmente después de llamar este SP en la app
END //

DELIMITER ;

-- ==========================================
-- DATOS DE PRUEBA (Min. 30 registros en total)
-- ==========================================

-- Insertar 2 Empresas
INSERT INTO EMPRESAS (nombre_negocio, nit_documento, fecha_suscripcion) VALUES 
('Supermercado La 14', '900123456-1', '2023-01-15'),
('Tecnología Global SAS', '800987654-2', '2023-03-20');

-- Insertar 3 Usuarios (password es '123456' hasheado, aquí usamos un string demo para la inserción inicial. La API usará bcrypt real)
INSERT INTO USUARIOS (id_empresa, nombre, email, password_hash, rol) VALUES 
(1, 'Admin Supermercado', 'admin@la14.com', '$2b$12$KkQc...demo', 'admin'),
(1, 'Vendedor 1', 'vendedor1@la14.com', '$2b$12$KkQc...demo', 'vendedor'),
(2, 'Admin Tech', 'admin@techglobal.com', '$2b$12$KkQc...demo', 'admin');

-- Insertar 4 Proveedores
INSERT INTO PROVEEDORES (id_empresa, nombre_proveedor, telefono_contacto) VALUES 
(1, 'Distribuidora Alimentos S.A.', '3101234567'),
(1, 'Lacteos del Valle', '3209876543'),
(2, 'Importaciones Electrónicas', '3005556666'),
(2, 'CompuMayoristas', '3157778888');

-- Insertar-- 4. CATEGORÍAS (Básicas y Nuevas)
INSERT INTO CATEGORIAS (id_empresa, nombre_categoria) VALUES 
(1, 'Lácteos'), (1, 'Cereales'), (1, 'Bebidas'), 
(2, 'Computadores'), (2, 'Periféricos'), (2, 'Celulares'),
(1, 'Panadería y Pastelería'), (1, 'Licores y Cervezas'), 
(1, 'Ropa y Accesorios'), (1, 'Carnes y Embutidos'), 
(1, 'Aseo y Limpieza del Hogar'), (1, 'Cuidado Personal'), 
(1, 'Frutas y Verduras'), (1, 'Snacks y Dulces'), 
(1, 'Medicamentos y Farmacia'), (1, 'Herramientas y Ferretería'), 
(1, 'Juguetes y Juegos'), (1, 'Papelería y Oficina'), (1, 'Mascotas');

-- Insertar 10 Productos
INSERT INTO PRODUCTOS (id_empresa, id_categoria, nombre_producto, precio_costo, precio_venta, cantidad_stock) VALUES 
(1, 1, 'Leche Entera 1L', 2500, 3500, 100),
(1, 1, 'Queso Campesino 500g', 6000, 8500, 50),
(1, 2, 'Arroz Diana 1Kg', 3000, 4200, 200),
(1, 2, 'Lentejas 500g', 2000, 3000, 80),
(1, 3, 'Gaseosa Coca-Cola 2L', 4500, 6000, 120),
(2, 4, 'Portátil Asus Vivobook', 1500000, 2100000, 15),
(2, 4, 'MacBook Air M1', 3500000, 4500000, 5),
(2, 5, 'Mouse Inalámbrico Logitech', 45000, 80000, 40),
(2, 5, 'Teclado Mecánico Redragon', 120000, 190000, 25),
(2, 6, 'iPhone 13 128GB', 2800000, 3500000, 10);

-- Insertar 2 Facturas (Cabecera)
INSERT INTO FACTURAS_COMPRA_IA (id_empresa, id_proveedor, url_imagen_escaneada, fecha_factura, total_factura) VALUES 
(1, 1, 'http://storage.com/factura1.jpg', '2023-10-01', 500000),
(2, 3, 'http://storage.com/factura2.jpg', '2023-10-05', 4500000);

-- Insertar 4 Detalles de Factura
INSERT INTO DETALLE_FACTURAS (id_factura, id_producto, cantidad_comprada, precio_unitario_compra) VALUES 
(1, 1, 100, 2500), (1, 3, 200, 3000),
(2, 6, 2, 1500000), (2, 8, 20, 45000);

-- Simular algunas ventas llamando al procedimiento almacenado
CALL sp_registrar_venta(1, 2, 1, 5, 3500);  -- Vender 5 Leches
CALL sp_registrar_venta(1, 2, 3, 10, 4200); -- Vender 10 Arroz
CALL sp_registrar_venta(2, 3, 8, 2, 80000); -- Vender 2 Mouse
CALL sp_registrar_venta(2, 3, 10, 1, 3500000); -- Vender 1 iPhone

-- Total de registros insertados explícitamente y mediante SP supera los 30.
