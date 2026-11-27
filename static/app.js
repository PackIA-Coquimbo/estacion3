// ============================================================
// App de la Estación 3: pestañas, botones y actualización del estado
// ============================================================

let estado = null;          // último estado recibido de /api/estado
let pestanaActiva = "cinta";
let verMascara = false;     // pestaña Clasificador: ver la máscara en vez de la cámara
let modoZona = false;       // pestaña Clasificador: dibujando la zona
let inicioZona = null;      // punto donde empezó el arrastre (en px de la página)

const $ = (id) => document.getElementById(id);

// ---------- Avisos y llamadas a la API ----------
let temporizadorAviso = null;
function aviso(texto, ok = true) {
  const caja = $("aviso");
  caja.textContent = texto;
  caja.classList.toggle("error", !ok);
  caja.classList.add("visible");
  clearTimeout(temporizadorAviso);
  temporizadorAviso = setTimeout(() => caja.classList.remove("visible"), 3500);
}

async function api(ruta, datos = {}) {
  try {
    const r = await fetch(ruta, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(datos),
    });
    const respuesta = await r.json();
    aviso(respuesta.mensaje, respuesta.ok);
    actualizar();
    return respuesta;
  } catch (e) {
    aviso("No hay conexión con la app", false);
    return { ok: false };
  }
}

// ---------- Pestañas ----------
// Solo la pestaña visible pide video, para no cargar la Raspberry.
function activarPestana(nombre) {
  pestanaActiva = nombre;
  document.querySelectorAll(".pestana").forEach((b) => b.classList.toggle("activa", b.dataset.pestana === nombre));
  document.querySelectorAll(".vista").forEach((v) => v.classList.toggle("activa", v.id === nombre));
  const vistaClasificador = verMascara ? "mascara" : "clasificador";
  cambiarVideo($("img-clasificador"), nombre === "clasificador" ? `/video/${vistaClasificador}` : "");
  cambiarVideo($("img-cinta"), nombre === "cinta" ? "/video/cinta" : "");
  try { localStorage.setItem("pestana", nombre); } catch (e) { /* sin almacenamiento: no pasa nada */ }
}

function cambiarVideo(img, ruta) {
  if (img.dataset.ruta === ruta) return;
  img.dataset.ruta = ruta;
  img.src = ruta || "data:,";
}

document.querySelectorAll(".pestana").forEach((b) => b.addEventListener("click", () => activarPestana(b.dataset.pestana)));

// ---------- Coordenadas: de la página a la imagen original (1920 x 1080) ----------
function aImagen(evento, img) {
  const r = img.getBoundingClientRect();
  const ancho = estado ? estado.ancho_imagen : 1920;
  const alto = estado ? estado.alto_imagen : 1080;
  return {
    x: Math.round((evento.clientX - r.left) * ancho / r.width),
    y: Math.round((evento.clientY - r.top) * alto / r.height),
  };
}

function prepararCanvas(canvas) {
  canvas.width = canvas.clientWidth;
  canvas.height = canvas.clientHeight;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  return ctx;
}

// ---------- Pestaña Clasificador ----------
$("btn-calibrar").addEventListener("click", () => api("/api/calibrar"));
$("btn-foto").addEventListener("click", () => api("/api/foto"));
$("btn-mascara").addEventListener("click", () => {
  verMascara = !verMascara;
  $("btn-mascara").classList.toggle("activo", verMascara);
  $("btn-mascara").textContent = verMascara ? "Ver cámara" : "Ver máscara";
  activarPestana("clasificador");
});
$("btn-zona").addEventListener("click", () => {
  modoZona = !modoZona;
  $("btn-zona").classList.toggle("activo", modoZona);
  $("btn-zona").textContent = modoZona ? "Cancelar" : "Elegir zona";
  $("ayuda-zona").classList.toggle("oculto", !modoZona);
  prepararCanvas($("canvas-clasificador"));
});

const canvasClasificador = $("canvas-clasificador");
canvasClasificador.addEventListener("pointerdown", (e) => {
  if (!modoZona) return;
  inicioZona = { x: e.offsetX, y: e.offsetY, evento: e };
});
canvasClasificador.addEventListener("pointermove", (e) => {
  if (!modoZona || !inicioZona) return;
  const ctx = prepararCanvas(canvasClasificador);
  ctx.strokeStyle = "#f59a3c";
  ctx.lineWidth = 3;
  ctx.setLineDash([8, 6]);
  ctx.strokeRect(inicioZona.x, inicioZona.y, e.offsetX - inicioZona.x, e.offsetY - inicioZona.y);
});
canvasClasificador.addEventListener("pointerup", async (e) => {
  if (!modoZona || !inicioZona) return;
  const img = $("img-clasificador");
  const a = aImagen(inicioZona.evento, img);
  const b = aImagen(e, img);
  inicioZona = null;
  const r = await api("/api/zona", { x1: a.x, y1: a.y, x2: b.x, y2: b.y });
  if (r.ok) $("btn-zona").click();          // salir del modo zona
  else prepararCanvas(canvasClasificador);
});

// ---------- Pestaña Estación cinta ----------
// Clic en la imagen: la línea de decisión se pone donde se hizo clic,
// como fracción de la zona en el sentido en que avanzan las naranjas.
$("canvas-cinta").addEventListener("click", (e) => {
  if (!estado) return;
  const p = aImagen(e, $("img-cinta"));
  const [x1, y1, x2, y2] = estado.zona;
  const vertical = estado.direccion === "abajo" || estado.direccion === "arriba";
  const fraccion = vertical ? (p.y - y1) / (y2 - y1) : (p.x - x1) / (x2 - x1);
  api("/api/linea", { fraccion: Math.round(fraccion * 1000) / 1000 });
});
document.querySelectorAll(".flecha").forEach((b) =>
  b.addEventListener("click", () => api("/api/direccion", { direccion: b.dataset.direccion })));
$("btn-grabar").addEventListener("click", () => api("/api/grabar"));
$("btn-reiniciar").addEventListener("click", () => api("/api/reiniciar"));
$("btn-urls").addEventListener("click", () => api("/api/urls", { url4: $("url4").value, url5: $("url5").value }));
$("envio").addEventListener("change", (e) => api("/api/envio", { activo: e.target.checked }));

// ---------- Pestaña Simulador ----------
$("simulador-activo").addEventListener("change", (e) => api("/api/simulador", { activo: e.target.checked }));

// ---------- Mostrar el estado (3 veces por segundo) ----------
function etiqueta(calibre) {
  return `<span class="etiqueta ${calibre}">${calibre}</span>`;
}

function mostrarEstado(s) {
  // Encabezado
  const chipCal = $("chip-calibracion");
  if (s.autocalibrado) { chipCal.textContent = `● Autocalibrado ${s.escala.toFixed(4)} mm/px`; chipCal.className = "chip ok"; }
  else if (s.calibrado) { chipCal.textContent = `● Calibrado ${s.escala.toFixed(4)} mm/px`; chipCal.className = "chip medio"; }
  else { chipCal.textContent = "● Sin calibrar"; chipCal.className = "chip mal"; }
  $("chip-fps").textContent = `${s.fps} img/s`;
  $("chip-fuente").textContent = s.mensaje_fuente;
  $("chip-fuente").classList.toggle("oculto", !s.mensaje_fuente);
  $("envio").checked = s.envio_activo;

  // Clasificador: tabla de naranjas
  $("tabla-naranjas").innerHTML = s.naranjas.length
    ? s.naranjas.map((n) => `<tr><td>${n.id}</td><td>${n.completa ? n.mm.toFixed(1) + " mm" : "-"}</td><td>${etiqueta(n.calibre)}</td></tr>`).join("")
    : '<tr><td colspan="3" class="vacio">Sin naranjas</td></tr>';

  // Cinta: contadores, dirección, grabación, últimas
  for (const c of ["total", "chico", "mediano", "grande", "revision"]) $(`cont-${c}`).textContent = s.conteo[c];
  document.querySelectorAll(".flecha").forEach((b) => b.classList.toggle("activo", b.dataset.direccion === s.direccion));
  $("btn-grabar").classList.toggle("grabando", s.grabando);
  $("btn-grabar").lastChild.textContent = s.grabando ? "Detener" : "Grabar";
  $("lista-ultimas").innerHTML = s.ultimas.length
    ? s.ultimas.map((d) => `<li><span>#${d.id} · ${d.diametro_mm === null ? "sin medida" : d.diametro_mm.toFixed(1) + " mm"}</span>${etiqueta(d.calibre)}</li>`).join("")
    : '<li class="vacio">Todavía no pasa ninguna</li>';
  if (document.activeElement !== $("url4")) $("url4").value = s.url_estacion4;
  if (document.activeElement !== $("url5")) $("url5").value = s.url_estacion5;
  $("errores-envio").textContent = s.errores_envio ? `Envíos fallidos: ${s.errores_envio}. Último: ${s.ultimo_error}` : "Sin errores de envío";

  // Simulador
  const sim = s.simulador;
  $("simulador-activo").checked = s.simulador_activo;
  $("destino-envio").textContent = s.simulador_activo
    ? "Las naranjas se envían a las estaciones simuladas de esta app."
    : `Las naranjas se envían a las estaciones reales: ${s.url_estacion4} y ${s.url_estacion5}`;
  $("sim-servo").textContent = sim.estacion4.servo;
  $("sim-recibidas").textContent = sim.estacion4.recibidas;
  const u = sim.estacion4.ultima;
  $("sim-ultima").textContent = u ? `Última: #${u.id} ${u.calibre} (${u.diametro_mm ?? "-"} mm)` : "Última: -";
  for (const c of ["total", "chico", "mediano", "grande"]) $(`sim-${c}`).textContent = sim.estacion5[c];
  $("sim-registro").innerHTML = sim.registro.length
    ? sim.registro.map((t) => `<li>${t}</li>`).join("")
    : '<li class="vacio">Sin mensajes</li>';
}

async function actualizar() {
  try {
    const r = await fetch("/api/estado");
    estado = await r.json();
    mostrarEstado(estado);
  } catch (e) {
    $("chip-fuente").textContent = "Sin conexión con la app";
    $("chip-fuente").classList.remove("oculto");
  }
}

// ---------- Inicio ----------
try { pestanaActiva = localStorage.getItem("pestana") || "cinta"; } catch (e) { /* sin almacenamiento */ }
activarPestana(pestanaActiva);
actualizar();
setInterval(actualizar, 333);
