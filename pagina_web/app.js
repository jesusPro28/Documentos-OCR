

// CONSTANTES GLOBALES DE CONFIGURACIÓN


const API_URL        = "http://127.0.0.1:8000/predict";
const API_ASYNC_URL  = "http://127.0.0.1:8000/subir_y_analizar";


const MODO_PRODUCCION = true;

// INICIALIZACIÓN DEL DOM


document.addEventListener("DOMContentLoaded", () => {
    // Configura los listeners de drag & drop y selección de archivos
    setupUploadListeners();
    // Carga y renderiza los registros existentes en la tabla de auditoría
    renderTablaAdmin();
});


function setupUploadListeners() {
    setupDragAndDrop('curpBox', 'curpFile', 'curpLabel');
    setupDragAndDrop('actaBox', 'actaFile', 'actaLabel');
}

function setupDragAndDrop(boxId, inputId, labelId) {
    const box = document.getElementById(boxId);
    const input = document.getElementById(inputId);

    if (!box || !input) return;

    // Clic normal
    input.addEventListener('change', () => {
        updateFileLabel(inputId, labelId);
    });

    // Evitar que el navegador abra el PDF directamente
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        box.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    // Estilos visuales al arrastrar
    ['dragenter', 'dragover'].forEach(eventName => {
        box.addEventListener(eventName, () => {
            box.style.borderColor = "#3b82f6";
            box.style.backgroundColor = "#eff6ff";
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        box.addEventListener(eventName, () => {
            box.style.borderColor = "#cbd5e1";
            box.style.backgroundColor = "transparent";
        }, false);
    });

    // Manejar cuando se suelta el archivo
    box.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files && files.length > 0) {
            input.files = files; // Forzar el archivo arrastrado al input nativo
            updateFileLabel(inputId, labelId);
        }
    }, false);
}


function updateFileLabel(inputId, labelId) {
    const input = document.getElementById(inputId);
    const label = document.getElementById(labelId);
    if (input && input.files.length > 0) {
        label.innerText = input.files[0].name;
        label.style.color = "#10b981"; // Cambia el texto a verde para confirmar selección
    }
}


function switchTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));

    if (tab === 'alumno') {
        document.querySelector('[onclick="switchTab(\'alumno\')"]').classList.add('active');
        document.getElementById('tab-alumno').classList.add('active');
    } else {
        document.querySelector('[onclick="switchTab(\'admin\')"]').classList.add('active');
        document.getElementById('tab-admin').classList.add('active');
        renderTablaAdmin();
    }
}

// COMUNICACIÓN CON LA API DE INTELIGENCIA ARTIFICIAL


async function analizarDocumento(file, tipoEsperado) {
    const formData = new FormData();
    formData.append("file", file);

    // Llamada POST asíncrona a FastAPI
    const response = await fetch(API_URL, {
        method: "POST",
        body: formData
    });

    if (!response.ok) {
        throw new Error(`Error en el servidor de IA (${response.status})`);
    }

    const resultado = await response.json();

    
    if (resultado.estado_final === "ACEPTADO" && resultado.clase_pred !== tipoEsperado) {
        const tipoDetectado = resultado.clase_pred === "curp" ? "CURP" : "Acta de Nacimiento";
        const tipoRequerido = tipoEsperado === "curp" ? "CURP" : "Acta de Nacimiento";
        
        // Forzamos el rechazo sobreescribiendo la respuesta original
        resultado.estado_final = "RECHAZADO";
        resultado.b3_ok = false;
        resultado.observaciones = `B1: OK | B2: OK | B3: Documento incorrecto. Se detectó ${tipoDetectado} pero se requiere ${tipoRequerido}.`;
    }

    return resultado;
}

// LÓGICA PRINCIPAL DE REGISTRO (BACKGROUND PROCESSING)


async function registrarAlumno(event) {
    event.preventDefault();

    const nombre   = document.getElementById('nombre').value.trim();
    const edad     = document.getElementById('edad').value;
    const carrera  = document.getElementById('carrera').value;
    const curpFile = document.getElementById('curpFile').files[0];
    const actaFile = document.getElementById('actaFile').files[0];

    if (!nombre || !edad || !carrera || !curpFile || !actaFile) {
        alert("Por favor completa todos los campos del formulario.");
        return;
    }

    // Bloquear botón mientras se envían los archivos
    const btn = document.querySelector('#alumnoForm button[type="submit"]');
    btn.disabled = true;
    btn.textContent = "Enviando archivos...";

    const formData = new FormData();
    formData.append("nombre",    nombre);
    formData.append("edad",      edad);
    formData.append("carrera",   carrera);
    formData.append("curp_file", curpFile);
    formData.append("acta_file", actaFile);

    try {
        const response = await fetch(API_ASYNC_URL, {
            method: "POST",
            body: formData   // No se pone Content-Type: FormData lo configura solo
        });

        if (!response.ok) throw new Error(`Error del servidor (${response.status})`);

        // Mostrar mensaje de éxito inmediatamente, sin esperar el análisis
        const successMsg = document.getElementById('successMessage');
        successMsg.style.display = 'flex';

        // Ocultar el banner después de 12 segundos
        setTimeout(() => { successMsg.style.display = 'none'; }, 12000);

        // Limpiar formulario
        document.getElementById('alumnoForm').reset();
        resetLabels();

    } catch (error) {
        alert(`Error al enviar documentos: ${error.message}\nVerifica que el servidor Uvicorn esté encendido.`);
    } finally {
        btn.disabled = false;
        btn.textContent = "Enviar Documentación a Análisis";
    }
}


function resetLabels() {
    const curpLabel = document.getElementById('curpLabel');
    const actaLabel = document.getElementById('actaLabel');

    if (curpLabel) {
        curpLabel.innerText = "Arrastra o selecciona tu archivo PDF/Imagen";
        curpLabel.style.color = "#64748b";
    }
    if (actaLabel) {
        actaLabel.innerText = "Arrastra o selecciona tu archivo PDF/Imagen";
        actaLabel.style.color = "#64748b";
    }
}

// RENDERIZADO Y CONTROL DE LA TABLA ADMINISTRATIVA

// Identificador del intervalo de auto-refresco (para poder cancelarlo)
let autoRefreshInterval = null;

async function renderTablaAdmin() {
    const tbody = document.getElementById('tablaAlumnos');
    if (!tbody) return;

    tbody.innerHTML = "";
    let alumnos = [];

    try {
        if (MODO_PRODUCCION) {
            const response = await fetch("obtener_alumnos.php");
            alumnos = await response.json();
        } else {
            alumnos = JSON.parse(localStorage.getItem('alumnos') || '[]');
        }
    } catch (error) {
        console.error("Fallo al obtener alumnos: ", error);
    }

    if (alumnos.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" style="text-align:center; color:#94a3b8; padding:3rem;">
                    Bandeja de entrada vacía. Registra alumnos en la pestaña anterior para verlos aquí.
                </td>
            </tr>`;
        return;
    }

    // Activar auto-refresco si hay registros en proceso de análisis
    const hayAnalizando = alumnos.some(a => a.estatus_admin === 'Analizando');
    if (hayAnalizando && !autoRefreshInterval) {
        autoRefreshInterval = setInterval(() => renderTablaAdmin(), 30000);
    } else if (!hayAnalizando && autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
    }

    alumnos.forEach(alumno => {
        const tr = document.createElement('tr');
        const curpHtml = obtenerHtmlDocumento(alumno.curp);
        const actaHtml = obtenerHtmlDocumento(alumno.acta);

        let badgeClass = "badge-warning";
        if (alumno.estatus_admin === "Aprobado")   badgeClass = "badge-success";
        if (alumno.estatus_admin === "Rechazado")  badgeClass = "badge-danger";
        if (alumno.estatus_admin === "Analizando") badgeClass = "badge-warning";

        // Deshabilitar botones Aprobar/Rechazar mientras el análisis esté en curso
        const btnDisabled = alumno.estatus_admin === 'Analizando' ? 'disabled style="opacity:0.4;cursor:not-allowed;"' : '';

        tr.innerHTML = `
            <td><strong>${alumno.nombre}</strong></td>
            <td>
                <span style="font-weight:600; color:#334155;">${alumno.carrera}</span><br>
                <span style="color:#64748b; font-size:0.85rem;">Edad: ${alumno.edad} años</span>
            </td>
            <td>${curpHtml}</td>
            <td>${actaHtml}</td>
            <td><span class="badge ${badgeClass}">${alumno.estatus_admin}</span></td>
            <td>
                <button class="btn-action btn-approve" onclick="cambiarEstatusAdmin(${alumno.id}, 'Aprobado')" ${btnDisabled}>Aprobar</button>
                <button class="btn-action btn-reject"  onclick="cambiarEstatusAdmin(${alumno.id}, 'Rechazado')" ${btnDisabled}>Rechazar</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

// UTILIDADES DE PRESENTACIÓN Y CÁLCULOS


function calcularConfianzaCompuesta(doc) {
    const obs = doc.obs || "";

    // Extraemos la confianza REAL de B1 si fue guardada (registros nuevos)
    // Para registros viejos, usamos binario: 100% si pasó, 0% si no.
    const b1ConfMatch = obs.match(/\[B1_CONF:([\d.]+)\]/);
    const b1Score = b1ConfMatch
        ? parseFloat(b1ConfMatch[1])
        : (doc.b1 == true ? 100 : 0);

    const b2Score = doc.b2 == true && doc.b2 !== null ? 100 : 0;
    const b3Raw   = (doc.conf_ocr && doc.conf_ocr !== "N/D") ? parseFloat(doc.conf_ocr) : 0;

    const total = (b1Score * 0.30) + (b2Score * 0.20) + (b3Raw * 0.50);
    return {
        total:  total.toFixed(1),
        b1Pts:  (b1Score * 0.30).toFixed(1),
        b2Pts:  (b2Score * 0.20).toFixed(1),
        b3Pts:  (b3Raw   * 0.50).toFixed(1),
        b1Raw:  b1Score.toFixed(1),
        b3Raw:  b3Raw.toFixed(1)
    };
}


function obtenerHtmlDocumento(doc) {
    // Estado PROCESANDO: la IA aún no ha terminado el análisis
    if (doc.estado === 'PROCESANDO') {
        return `
            <div style="display:flex; align-items:center; gap:0.7rem; padding:0.8rem; background:#fefce8; border:1px solid #fde68a; border-radius:8px;">
                <div style="width:18px; height:18px; border:3px solid #fbbf24; border-top-color:transparent; border-radius:50%; animation:spin 1s linear infinite; flex-shrink:0;"></div>
                <div>
                    <div style="font-weight:600; color:#92400e; font-size:0.85rem;">Analizando con IA...</div>
                    <div style="color:#b45309; font-size:0.78rem;">Disponible en ~1-3 min</div>
                </div>
            </div>`;
    }

    const isAprobado = doc.estado === "ACEPTADO";
    const badge = isAprobado 
        ? `<span class="badge badge-success">✓ Aprobado</span>` 
        : `<span class="badge badge-danger">✗ Rechazado</span>`;

    const obs = doc.obs || "";
    const b1Val  = doc.b1 == true && doc.b1 !== "N/A";
    const b2Val  = doc.b2 == true && doc.b2 !== "N/A";
    const b3Val  = doc.b3 == true && doc.b3 !== "N/A";
    const b1Ejec = doc.b1 !== undefined && doc.b1 !== null && doc.b1 !== "N/A";
    const b2Ejec = doc.b2 !== undefined && doc.b2 !== null && doc.b2 !== "N/A";
    const b3Ejec = doc.b3 !== undefined && doc.b3 !== null && doc.b3 !== "N/A";
    const b1Icon = !b1Ejec ? "⚪" : b1Val ? "🟢" : "🔴";
    const b2Icon = !b2Ejec ? "⚪" : b2Val ? "🟢" : "🔴";
    const b3Icon = !b3Ejec ? "⚪" : b3Val ? "🟢" : "🔴";

    let mensajeB3 = "";
    const matchB3 = obs.match(/B3:\s*(.+)/);
    if (matchB3) mensajeB3 = matchB3[1];

    const conf       = calcularConfianzaCompuesta(doc);
    const confFinal  = isAprobado ? conf.total : "0.0";
    const confColor  = !isAprobado ? "#dc2626" : confFinal >= 75 ? "#16a34a" : confFinal >= 50 ? "#d97706" : "#dc2626";
    const confBg     = !isAprobado ? "#fef2f2" : "#f0fdf4";
    const confBorder = !isAprobado ? "#fecaca" : "#bbf7d0";
    const confTooltip = isAprobado
        ? `B1 IA ${conf.b1Raw}% (×30%): ${conf.b1Pts}pts | B2 Calidad (×20%): ${conf.b2Pts}pts | B3 OCR ${conf.b3Raw}% (×50%): ${conf.b3Pts}pts`
        : "Documento rechazado — confianza inválida";
    const confHtml = `
        <div title="${confTooltip}" style="cursor:help; margin-top:0.5rem; background:${confBg}; border:1px solid ${confBorder}; border-radius:6px; padding:0.35rem 0.7rem; display:flex; align-items:center; gap:0.4rem;">
            <span style="font-weight:700; color:${confColor}; font-size:0.85rem;">Confianza: ${confFinal}%</span>
        </div>`;

    // Botón para ver el documento sin descargarlo (lee el BLOB directo de MySQL via PHP)
    const verUrl = `ver_documento.php?id=${doc.id || ''}&tipo=${doc.tipo || 'curp'}`;
    const verBtn = `<a href="${verUrl}" target="_blank" rel="noopener"
        style="display:inline-flex; align-items:center; gap:0.3rem; margin-top:0.4rem;
               font-size:0.75rem; color:#3b82f6; text-decoration:none;
               border:1px solid #bfdbfe; border-radius:5px; padding:0.2rem 0.5rem;
               background:#eff6ff; transition:background 0.2s;"
        onmouseover="this.style.background='#dbeafe'" onmouseout="this.style.background='#eff6ff'">
        👁 Ver documento
    </a>`;

    return `
        ${badge}
        <div style="font-size:0.78rem; color:#475569; margin-top:0.5rem; line-height:1.6; background:#f8fafc; border-radius:6px; padding:0.5rem 0.7rem;">
            <div style="font-weight:600; color:#334155; margin-bottom:0.3rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:220px;" title="${doc.nombre_archivo}">
                📄 ${doc.nombre_archivo}
            </div>
            <div>${b1Icon} <strong>B1 Clasificación:</strong> ${b1Val ? "Documento válido" : b1Ejec ? "Tipo incorrecto" : "No ejecutado"}</div>
            <div>${b2Icon} <strong>B2 Calidad:</strong> ${b2Val ? "Imagen aceptable" : b2Ejec ? "Imagen deficiente" : "No ejecutado"}</div>
            <div>${b3Icon} <strong>B3 OCR:</strong> ${mensajeB3 || (b3Val ? "Metadata encontrada" : "Sin metadata")}</div>
            ${confHtml}
            ${verBtn}
        </div>
    `;
}


async function cambiarEstatusAdmin(id, nuevoEstatus) {
    try {
        if (MODO_PRODUCCION) {
            // Actualización real en la base de datos MySQL en Hostinger
            const response = await fetch("actualizar_estatus.php", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ id: id, estatus_admin: nuevoEstatus })
            });
            const res = await response.json();
            if (!res.success) {
                alert(res.message);
                return;
            }
        } else {
            // Actualización de pruebas localmente
            let alumnos = JSON.parse(localStorage.getItem('alumnos') || '[]');
            alumnos = alumnos.map(al => {
                if (al.id === id) {
                    al.estatus_admin = nuevoEstatus;
                }
                return al;
            });
            localStorage.setItem('alumnos', JSON.stringify(alumnos));
        }
        renderTablaAdmin();
    } catch (error) {
        alert("Fallo al actualizar estatus: " + error.message);
    }
}


function limpiarRegistros() {
    if (MODO_PRODUCCION) {
        alert("La limpieza completa de la base de datos está deshabilitada en producción por seguridad.");
        return;
    }
    if (confirm("¿Estás seguro de que deseas vaciar la bandeja de entrada? Esta acción no se puede deshacer.")) {
        localStorage.removeItem('alumnos');
        renderTablaAdmin();
    }
}
