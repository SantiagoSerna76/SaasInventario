const API_URL = '/api';
let token = localStorage.getItem('token');
let currentUser = null;

// Referencias a DOM
const loginScreen = document.getElementById('login-screen');
const dashboardScreen = document.getElementById('dashboard-screen');
const loginForm = document.getElementById('login-form');
const loginError = document.getElementById('login-error');
const sectionTitle = document.getElementById('section-title');

// Comprobar sesión al inicio
if (token) {
    // Idealmente verificar si el token sigue siendo válido. Aquí simularemos que sí.
    showDashboard();
    cargarProductos();
}

// LOGIN LOGIC
loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    
    loginError.innerText = '';
    
    const formData = new FormData();
    formData.append('username', email);
    formData.append('password', password);

    try {
        const response = await fetch(`${API_URL}/login`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            token = data.access_token;
            localStorage.setItem('token', token);
            currentUser = data.user;
            document.getElementById('user-name').innerText = currentUser.nombre;
            showDashboard();
            cargarProductos();
        } else {
            loginError.innerText = data.detail || 'Error al iniciar sesión';
        }
    } catch (error) {
        loginError.innerText = 'Error de red. Asegúrate de que el backend esté corriendo.';
    }
});

function logout() {
    localStorage.removeItem('token');
    token = null;
    dashboardScreen.classList.remove('active');
    dashboardScreen.classList.add('hidden');
    loginScreen.classList.remove('hidden');
    loginScreen.classList.add('active');
}

function showDashboard() {
    loginScreen.classList.remove('active');
    loginScreen.classList.add('hidden');
    dashboardScreen.classList.remove('hidden');
    dashboardScreen.classList.add('active');
}

// NAVEGACIÓN
function showSection(sectionId) {
    // Ocultar todas
    document.querySelectorAll('.dashboard-section').forEach(sec => {
        sec.classList.remove('active');
        sec.classList.add('hidden');
    });
    // Mostrar la seleccionada
    document.getElementById(`sec-${sectionId}`).classList.remove('hidden');
    document.getElementById(`sec-${sectionId}`).classList.add('active');
    
    // Actualizar nav active state
    document.querySelectorAll('.sidebar nav a').forEach(a => a.classList.remove('active'));
    if (window.event && window.event.currentTarget) {
        window.event.currentTarget.classList.add('active');
    }
    
    // Cambiar título
    const titles = { 'productos': 'Inventario', 'ventas': 'Gestión de Ventas', 'escaner': 'Escaneo por IA' };
    sectionTitle.innerText = titles[sectionId];
}

// CARGAR PRODUCTOS (GET /api/productos)
async function cargarProductos() {
    try {
        const response = await fetch(`${API_URL}/productos`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (response.ok) {
            const productos = await response.json();
            const tbody = document.querySelector('#table-productos tbody');
            const selectVenta = document.getElementById('venta-producto');
            tbody.innerHTML = '';
            selectVenta.innerHTML = '<option value="">-- Selecciona un producto --</option>';
            productos.forEach(p => {
                tbody.innerHTML += `
                    <tr>
                        <td>#${p.id_producto}</td>
                        <td><strong>${p.nombre_producto}</strong></td>
                        <td><span style="background:var(--primary);padding:4px 8px;border-radius:4px;font-size:0.75rem;color:white">${p.nombre_categoria}</span></td>
                        <td>${p.cantidad_stock} unds</td>
                        <td>$${p.precio_venta}</td>
                        <td>
                            <button class="btn btn-sm btn-secondary" onclick="openEditModal(${p.id_producto}, '${p.nombre_producto.replace(/'/g, "\\'")}', ${p.precio_venta})"><i class="ph ph-pencil"></i></button>
                            <button class="btn btn-sm btn-icon" onclick="eliminarProducto(${p.id_producto})" style="color:var(--danger)"><i class="ph ph-trash"></i></button>
                        </td>
                    </tr>
                `;
                selectVenta.innerHTML += `<option value="${p.id_producto}">${p.nombre_producto} - $${p.precio_venta} (${p.cantidad_stock} disp)</option>`;
            });
        }
    } catch (e) {
        console.error("Error cargando productos", e);
    }
}

// EDITAR PRODUCTO
const editModal = document.getElementById('edit-modal');
const editForm = document.getElementById('edit-form');

function openEditModal(id, nombre, precio) {
    document.getElementById('edit-id').value = id;
    document.getElementById('edit-nombre').value = nombre;
    document.getElementById('edit-precio').value = precio;
    editModal.classList.remove('hidden');
}

function closeEditModal() {
    editModal.classList.add('hidden');
}

editForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const id = document.getElementById('edit-id').value;
    const nombre = document.getElementById('edit-nombre').value;
    const precio = document.getElementById('edit-precio').value;

    try {
        const response = await fetch(`${API_URL}/productos/${id}`, {
            method: 'PUT',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}` 
            },
            body: JSON.stringify({ nombre_producto: nombre, precio_venta: parseFloat(precio) })
        });
        if (response.ok) {
            closeEditModal();
            cargarProductos();
        } else {
            alert("Error al actualizar producto");
        }
    } catch(err) {
        alert("Error de red");
    }
});

// ELIMINAR PRODUCTO
async function eliminarProducto(id) {
    if(!confirm("¿Estás seguro de que deseas eliminar este producto?")) return;
    
    try {
        const response = await fetch(`${API_URL}/productos/${id}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (response.ok) {
            cargarProductos();
        } else {
            const err = await response.json();
            alert("Error al eliminar producto: " + (err.detail || "Error desconocido"));
        }
    } catch(err) {
        alert("Error de red: " + err.message);
    }
}

// CREAR PRODUCTO
const addModal = document.getElementById('add-modal');
const addForm = document.getElementById('add-form');

function openAddModal() {
    addForm.reset();
    addModal.classList.remove('hidden');
}

function closeAddModal() {
    addModal.classList.add('hidden');
}

addForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const payload = {
        id_categoria: parseInt(document.getElementById('add-categoria').value),
        nombre_producto: document.getElementById('add-nombre').value,
        precio_costo: parseFloat(document.getElementById('add-costo').value),
        precio_venta: parseFloat(document.getElementById('add-venta').value),
        cantidad_stock: parseInt(document.getElementById('add-stock').value)
    };

    try {
        const response = await fetch(`${API_URL}/productos`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}` 
            },
            body: JSON.stringify(payload)
        });
        if (response.ok) {
            closeAddModal();
            cargarProductos();
            alert("Producto creado exitosamente");
        } else {
            const err = await response.json();
            alert("Error al crear: " + JSON.stringify(err.detail));
        }
    } catch(err) {
        alert("Error de red");
    }
}
);

// VENTAS
const ventaForm = document.getElementById('venta-form');
ventaForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const idProducto = document.getElementById('venta-producto').value;
    const cantidad = document.getElementById('venta-cantidad').value;
    
    if(!idProducto) return alert("Selecciona un producto");

    try {
        const response = await fetch(`${API_URL}/ventas/registrar`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}` 
            },
            body: JSON.stringify({ id_producto: parseInt(idProducto), cantidad: parseInt(cantidad) })
        });
        
        if (response.ok) {
            alert("Venta registrada exitosamente. El stock ha sido descontado.");
            ventaForm.reset();
            cargarProductos(); // actualiza stock en dropdown
        } else {
            const err = await response.json();
            alert("Error al registrar venta: " + JSON.stringify(err.detail));
        }
    } catch(err) {
        alert("Error de red al vender");
    }
});

// ESCÁNER IA (POST /api/facturas/escanear)
const fileInput = document.getElementById('file-input');
const scanLoading = document.getElementById('scan-loading');
const scanResult = document.getElementById('scan-result');
const jsonResult = document.getElementById('json-result');

fileInput.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    scanLoading.classList.remove('hidden');
    scanResult.classList.add('hidden');
    
    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(`${API_URL}/facturas/escanear`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }, // Token opcional si la api lo requiere
            body: formData
        });
        
        if (response.ok) {
            const data = await response.json();
            document.getElementById('json-result').innerText = JSON.stringify(data, null, 2);
            document.getElementById('scan-result').classList.remove('hidden');
        } else {
            const err = await response.json();
            alert("Error al analizar la factura: " + (err.detail || "Error desconocido"));
        }
    } catch (e) {
        alert("Error de red al subir archivo: " + e.message);
    } finally {
        scanLoading.classList.add('hidden');
    }
});

async function guardarFactura() {
    try {
        let payload = JSON.parse(jsonResult.innerText);
        
        // Normalizar claves generadas por la IA (ej. "nombre producto" -> "nombre_producto")
        if (payload.productos && Array.isArray(payload.productos)) {
            payload.productos = payload.productos.map(p => {
                const pNorm = {};
                for (let k in p) {
                    pNorm[k.replace(/ /g, '_')] = p[k];
                }
                return pNorm;
            });
        }

        const response = await fetch(`${API_URL}/facturas/guardar`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(payload)
        });
        
        if (response.ok) {
            alert("¡Factura guardada correctamente en la Base de Datos y stock actualizado!");
            scanResult.classList.add('hidden');
            fileInput.value = ''; // clear
            cargarProductos(); // update stock
            showSection('productos'); // redirect
        } else {
            const err = await response.json();
            alert("Error al guardar: " + JSON.stringify(err.detail || "Desconocido"));
        }
    } catch(e) {
        alert("Error inesperado: " + (e.message || e));
        console.error(e);
    }
}

// NAVEGACIÓN MANUAL (Reemplazando onclick en linea)
document.getElementById('nav-productos').addEventListener('click', (e) => { e.preventDefault(); showSection('productos'); });
document.getElementById('nav-ventas').addEventListener('click', (e) => { e.preventDefault(); showSection('ventas'); });
document.getElementById('nav-escaner').addEventListener('click', (e) => { e.preventDefault(); showSection('escaner'); });
document.getElementById('nav-informes').addEventListener('click', (e) => { 
    e.preventDefault(); 
    showSection('informes'); 
    cargarInforme();
});

// CARGAR INFORMES (SEMANAL + MENSUAL)
async function cargarInforme() {
    try {
        const response = await fetch(`${API_URL}/informes/semanal`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (response.ok) {
            const data = await response.json();
            document.getElementById('informe-total').innerText = `$${data.total_semana.toLocaleString()}`;
            document.getElementById('informe-mas').innerText = data.mas_vendido;
            document.getElementById('informe-mas-cant').innerText = `${data.mas_vendido_cant} unidades`;
            document.getElementById('informe-menos').innerText = data.menos_vendido;
            document.getElementById('informe-menos-cant').innerText = `${data.menos_vendido_cant} unidades`;
        }
    } catch (e) {
        console.error('Error cargando informe semanal', e);
    }

    // Informe mensual - usa la función SQL fn_total_ventas_mes()
    try {
        const res = await fetch(`${API_URL}/informes/mensual`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok) {
            const data = await res.json();
            document.getElementById('informe-total-mes').innerText = `$${data.total_mes.toLocaleString()}`;
        }
    } catch (e) {
        console.error('Error cargando informe mensual', e);
    }
}
