# Proyecto vintage: gestión de bazares, inventario y vitrina

Resumen de consideraciones y decisiones. Estado al 10 de noviembre de 2026.
Alcance de este documento: planeación. No incluye código.

---

## 1. Contexto y objetivo

- **Cliente:** venta de ropa vintage de piezas únicas (una sola unidad por prenda).
- **Canales hoy:** el 70% de las ventas ocurre en bazares. La venta en línea se hace a través de GoTrendier.
- **Inventario hoy:** Excel y libretas sin estandarizar. Capturarlo bien es parte de la aplicación.
- **Objetivo:** crecer la venta en línea con una página disponible 24/7 para quienes no pueden asistir a los bazares, sin descuidar la operación de los bazares, que es el negocio actual.
- **Decisión de migración:** se migran todas las publicaciones de GoTrendier a la plataforma propia.
- **Enfoque inmediato:** construir los cimientos. Primero la administración del almacén y las ventas del bazar, el catálogo, una vitrina sencilla y un admin simple. La página crece de forma gradual.
- **Criterio de calidad:** que quede bien aunque sea básico, con posibilidad de escalar. La velocidad no es prioridad.
- **Quién opera:** el administrador del inventario es una persona distinta del arquitecto del proyecto. Debe poder trabajar sin ayuda técnica.
- **Forma de trabajo:** flujo agéntico. El arquitecto define reglas, arquitectura de agentes y del sitio. Se construye bloque por bloque y un tester verifica comportamientos. Sus reportes realimentan a los agentes.
- **App móvil:** Flutter, en una fase posterior.

---

## 2. Decisiones tomadas

| Tema | Decisión | Motivo principal |
|---|---|---|
| Backend | Django | Admin incluido, convenciones fuertes que acotan al agente, ORM y migraciones maduros |
| Admin del operador | Django admin con tema | Cubre catálogo, inventario y revisión de importaciones con poco costo. Es "simple" como se pidió |
| Render de páginas | En servidor, con templates de Django | SEO sin trabajo extra, un solo proceso en producción, menos lógica en el navegador |
| Base de datos | PostgreSQL | Las reglas de concurrencia de piezas únicas se resuelven aquí |
| Vite | Solo como pipeline de assets (JS y CSS) con Tailwind | No hay interfaz compleja que justifique una SPA |
| React | Fuera de los cimientos | Entraría más adelante si el admin necesita una interfaz propia |
| FastAPI | Descartado por ahora | Obliga a construir admin, auth y jobs, y duplica reglas si convive con Django |
| API con Django Ninja | Diferida | Se adopta cuando exista un consumidor: la app Flutter o un JS puntual |
| Modo evento (bazar) | Páginas móviles renderizadas en servidor | El admin de Django es incómodo en el teléfono |
| Etiquetas QR | Una por pieza | Identificación rápida en bazar y puente hacia la ficha pública |
| Regla de canales | Una pieza, un canal a la vez | Evita la venta doble entre bodega, evento, página y GoTrendier |

### Sobre renderizar en servidor y "no exponer el código"

Renderizar en servidor es la decisión correcta, pero conviene entender bien por qué:

- Una aplicación de una sola página (SPA) envía al navegador todo su código de interfaz. Está minificado, pero cualquiera puede leerlo. Eso no es un problema en sí mismo si ahí no viven reglas ni secretos.
- Lo que protege el negocio no es ocultar el frontend, sino que **las reglas, los precios, los permisos y las validaciones vivan en el backend**. Eso se cumple con cualquier arquitectura.
- Con render en servidor, el navegador recibe HTML y muy poco JavaScript. Hay menos lógica expuesta y menos superficie para errores.
- El admin de Django, además, no envía una aplicación al navegador: son páginas generadas por el servidor.
- Regla complementaria: no serializar datos personales ni tokens en el HTML. Un marketplace revisado como referencia incluía un token con un correo en el código fuente de sus páginas. No se debe repetir.

---

## 3. Arquitectura de información (resumen)

### 3.1 Dos capas

| Capa | Duración | Ejemplos | Función |
|---|---|---|---|
| Taxonomía | Permanente | Tipos de prenda, décadas, marcas | Capta demanda genérica |
| Modelos y drops | Semipermanente | Levi's 501, Drop 003 | Páginas con historia y archivo |
| Piezas | Efímera | SKU individual | Conversión y búsquedas específicas |

### 3.2 Taxonomía

- **Por tipo de prenda** (jerarquía primaria, define la URL).
- **Por década o era.**
- **Estilos** como etiquetas transversales, sin URL propia.
- **Marcas** como hub, con modelos y piezas.
- **Drops** (lanzamientos) con histórico permanente.
- Cada pieza tiene un solo camino primario (tipo y década) que define su URL. Estilos y marcas son facetas o enlaces, nunca duplican la URL.

### 3.3 Filtros

- Tipo, década, talla de referencia, **medidas reales en cm** con tolerancia ajustable, condición, precio, marca, corte, material, color por familias, origen y llegadas recientes.
- Filtro "Me queda como…": el usuario introduce las medidas de una prenda que ya le queda y el sistema busca piezas dentro de la tolerancia.
- Lógica AND entre facetas y OR dentro de cada una, con conteos en tiempo real.
- Alertas por búsqueda guardada, para compensar la falta de reposición.
- SEO de facetas: se indexan solo combinaciones curadas. El resto lleva `canonical` a la categoría base o `noindex, follow`.

### 3.4 Ficha de pieza

Debe mostrar, en este orden de importancia:

1. Título con fórmula (tipo, marca, década, detalle, talla de época), precio y estado visible antes del botón.
2. Entre 8 y 12 fotos, con defectos fotografiados y una referencia de escala.
3. Nivel en la escala de condición, enlazado a una guía, y defectos con ubicación y tamaño.
4. Medidas en cm a prenda plana, con el método explicado.
5. Época y origen, distinguiendo datos confirmados de estimados.
6. Etiqueta, composición, cuidado, autenticidad y política de devolución.
7. Envío y tiempos de preparación.
8. Enlaces al modelo y a la marca, y piezas similares reales.

Lo que no debe mostrar: "solo queda 1" (siempre es cierto y no aporta), precios tachados que no sean reales, historias de origen sin evidencia y relacionados aleatorios.

### 3.5 Escala de condición (propuesta)

| Nivel | Definición |
|---|---|
| Nuevo con etiqueta | Sin uso, con etiqueta original |
| Excelente | Sin uso visible ni defectos |
| Muy buena | Desgaste mínimo, normal para su época |
| Buena | Desgaste acorde a la edad, defectos menores documentados |
| Para reparar / coleccionista | Defectos notorios, precio reducido |

La condición es un conjunto cerrado de valores, no texto libre.

### 3.6 SEO de piezas vendidas o retiradas

| Estado de la URL | Código | Acción |
|---|---|---|
| Disponible o reservada | 200 | En el sitemap y enlazada desde la categoría |
| Vendida | 200, indexable por un tiempo | `availability: SoldOut`, bloque de similares, fuera del sitemap de disponibles |
| Archivada con equivalente claro | 301 | A la pieza más parecida, nunca a la home |
| Archivada sin equivalente | 410 | Eliminación permanente |

Reglas: la URL no incluye estado, precio ni fecha, el ID nunca se reutiliza y no se usan páginas "no disponible" con código 200 (soft 404). Los modelos, marcas y décadas son páginas permanentes con contenido editorial. En una baja manual, el motivo determina el código HTTP, no el operador.

---

## 4. Dominio: piezas, estados y canales

### 4.1 Estado y canal

Cada pieza tiene dos dimensiones:

- **Estado:** disponible, reservada, vendida, dada de baja.
- **Canal donde está activa:** bodega, evento, página propia o GoTrendier (durante la transición).

Solo un canal puede tenerla activa. Mientras una pieza está "En evento", no acepta reservas en línea.

### 4.2 Transiciones manuales

| Desde | Hacia | Exige |
|---|---|---|
| Disponible | En evento | Evento y fecha. Se rechaza si la pieza está reservada o con pago pendiente |
| En evento | Vendida en evento | Monto, método y evento |
| En evento | Disponible | Al cerrar el evento, si no se vendió |
| Disponible | Dada de baja | Motivo de un catálogo cerrado |
| Reservada | Disponible o dada de baja | Motivo. Si hubo pago, reembolso |
| Dada de baja | Disponible | Solo por error de captura, con permiso de supervisor |
| Vendida | Sin transición manual | Solo mediante un flujo de devolución |

### 4.3 Apartado (reserva)

Un solo mecanismo para todos los contextos: una pieza, el estado previo, un momento de expiración y acciones para extender o liberar. Al expirar, la pieza vuelve a su estado y canal anteriores.

| Contexto | Plazo | Al expirar |
|---|---|---|
| Transferencia en bazar | Minutos, configurable por evento | Vuelve a "En evento" |
| Carrito en la vitrina (futuro) | Unos 15 minutos | Vuelve a "Disponible" |

- El operador puede extender el plazo una sola vez, con motivo registrado.
- Un pago que llega después del plazo se rechaza hasta que el operador reactive el apartado, y solo si la pieza no se vendió a otra persona.
- La reserva es una operación atómica en la base de datos: la pieza se toma solo si sigue libre en ese instante. Quien pierde la carrera recibe un rechazo.

### 4.4 Controles de las acciones manuales

- Permisos separados para dar de baja, marcar venta fuera de plataforma y reactivar.
- Motivo obligatorio.
- Confirmación en dos pasos si afecta a un comprador con reserva o pago pendiente.
- Auditoría en la misma transacción que el cambio: estado anterior, nuevo, motivo, usuario y fecha.
- Reporte de bajas por operador y motivo.

---

## 5. Bazares: modo evento

Es la herramienta de la mayor parte de las ventas, por lo que va antes que la tienda.

**Flujo:**

1. Se abre un evento con fecha, nombre y plazo de apartado.
2. Se sacan a evento las piezas que se llevarán.
3. Se vende con efectivo o transferencia.
4. Al cerrar, se marcan las no vendidas y se hace el arqueo.

**Efectivo:** la venta se confirma en el momento y suma al efectivo esperado del evento. Al cerrar, se cuenta el efectivo y el sistema registra la diferencia con su motivo.

**Transferencia:** la pieza se aparta con una referencia única. El operador confirma solo contra el movimiento visible en su banca, nunca contra una captura enviada por el cliente. Hasta la confirmación, la venta no cuenta en el cierre.

**Precio:** se guarda el precio de lista y el precio cobrado por separado, con el motivo de la diferencia. En un bazar se negocia.

**QR:** la etiqueta de cada pieza apunta a su ficha pública. Con sesión de operador, el mismo QR lleva al modo evento. Se usa la cámara nativa del teléfono, sin escáner dentro de la aplicación.

**Teléfono:** el admin de Django no es cómodo en móvil. El modo evento son páginas del servidor pensadas para móvil, con cuatro acciones: buscar una pieza, sacarla a evento, marcarla vendida y generar el apartado.

**Sin conexión:** no es requisito inicial. Como las piezas en evento no pueden venderse en línea al mismo tiempo, agregar una cola sin conexión después no genera conflictos.

---

## 6. Pagos y cierre

- Una venta puede tener uno o varios pagos. Cada pago tiene método, monto, estado y referencia del proveedor si existe.
- Efectivo nace confirmado. Transferencia nace pendiente. Un pago con proveedor nace pendiente y se confirma por webhook.
- Agregar el webhook después añade un canal de confirmación, sin cambiar la estructura.
- Las confirmaciones de pago deben ser idempotentes: confirmar dos veces no duplica la venta.
- Dinero en centavos enteros o `Decimal`, nunca `float`.
- Los movimientos de dinero no se editan. Un error se corrige con un movimiento nuevo que referencia al original. Un cierre confirmado es inmutable.
- El cierre de periodo concilia ventas en línea, ventas de eventos y diferencias. Cada diferencia genera una alerta y no se corrige en silencio.
- Facturación CFDI: el modelo guarda el RFC cuando el cliente lo pide. El timbrado puede esperar.
- Descuentos: primero precio de oferta con vigencia. Las reglas combinables llegan después, con precio original y precio cobrado siempre registrados.
- Proveedor de pagos en línea: se evalúa al empezar el checkout de la vitrina. Opciones comunes: Mercado Pago o Stripe con pago hospedado, para no tocar datos de tarjeta.

---

## 7. Inventario y migración

### 7.1 Captura desde Excel y libretas

Este es el trabajo más costoso del proyecto y ningún framework lo resuelve.

- **Vocabularios controlados:** marcas (con alias), categorías, condiciones y tallas, tomados de los datos más frecuentes. Lo que no coincide queda como "otro" en revisión.
- **Modelo mínimo de pieza:** identificador estable, QR, estado, canal, precio en centavos, medidas y fotos. El resto se completa después.
- **Importador con cuarentena:** las filas que no se pueden mapear van a una lista de revisión, nunca se descartan en silencio. El Excel original se conserva como fuente de consulta durante la transición.
- **Alta rápida desde el teléfono:** foto, QR y cuatro campos obligatorios (marca, tipo, talla, precio).
- **Medidas numéricas en cm como campos estructurados**, no dentro de la descripción.

### 7.2 Lecciones de datos de un marketplace de referencia

Al revisar páginas de GoTrendier como ejemplo, se vieron errores que conviene evitar:

- Marca como texto libre, con variantes de la misma marca y marcas incorrectas.
- Categoría que no corresponde a la prenda.
- Condición que contradice la descripción.
- Moneda implícita.
- Títulos sin formato ni idioma consistente.
- Medidas dentro del texto libre de la descripción.

Para este proyecto: marca como entidad con alias, condición como valor cerrado, categoría como relación validada, moneda como campo de la publicación y medidas como campos numéricos.

### 7.3 Migración desde GoTrendier

- Primero exportar el historial de publicaciones y ventas, si es posible. Si no, capturar lo esencial a mano.
- Migrar por lotes alineados con el calendario de bazares. Orden por pieza: marcar como "migrando", quitarla de GoTrendier y solo después activarla en el canal propio. Nunca al revés.
- La reputación acumulada en GoTrendier no migra. La vitrina empieza sin esa confianza.
- Medir visitas y consultas por WhatsApp desde la primera semana. Mover las piezas no garantiza mantener el tráfico.

---

## 8. Vitrina

- Catálogo, ficha de pieza y un botón "Me interesa" que abre WhatsApp con el identificador de la pieza.
- El operador marca la reserva y expira sola si no se confirma.
- Se construye con la misma lógica de estados y apartados que el modo evento, para no reescribirla cuando llegue el checkout.
- Checkout en línea con pago hospedado, en una fase posterior. La confirmación de pago siempre llega por webhook, nunca solo por la redirección del navegador.
- Reglas de pago tardío: si confirma después del plazo y la pieza sigue libre, se vende. Si ya fue tomada, se reembolsa y se avisa.
- Tarifa de envío fija por zona al inicio.
- Fuera del alcance inicial: cuentas obligatorias, cupones, wishlists y cálculo de envío en tiempo real.

---

## 9. Stack y estructura

| Capa | Decisión |
|---|---|
| Backend y admin | Django, monolito modular por dominio: inventario, catálogo, eventos y ventas, pagos |
| Base de datos | PostgreSQL. Los tests de concurrencia usan Postgres real, no SQLite |
| Páginas | Templates de Django: vitrina y modo evento móvil |
| Assets | Vite con django-vite y Tailwind. Sin Node en producción (compilación en una etapa del Dockerfile) |
| Interacción | HTMX solo si hace falta |
| API | Django Ninja, diferida |
| Pruebas | Cliente de test de Django para HTML y reglas. Playwright para pocos flujos críticos |
| Entorno | Docker Compose: base de datos, backend y Vite en desarrollo. En producción, una imagen multi-stage |
| App móvil | Flutter, más adelante, consumiendo la API |

Notas de implementación:

- Con Tailwind v4, los templates deben declararse explícitamente como fuente, para que se generen las clases que solo aparecen allí.
- En desarrollo, el navegador carga los assets desde el servidor de Vite en el host, no desde el nombre del contenedor.
- Las versiones se fijan al iniciar el spike, verificando que cada paquete siga vigente (en particular el tema del admin).
- Modularidad: un módulo no importa los internals de otro, solo su interfaz pública. Así, separar uno en el futuro es un corte limpio.
- La lógica vive en servicios, no en vistas ni en el admin, para poder exponerla por API después.

---

## 10. Reglas para `AGENTS.md`

- Dinero en centavos enteros o `Decimal`.
- Guardar fechas en UTC y calcular días de cierre en `America/Mexico_City`.
- Las transiciones de estado solo ocurren por servicios del dominio. El campo de estado es de solo lectura en el admin y el operador usa acciones explícitas.
- La auditoría se escribe en la misma transacción que el cambio.
- Los permisos se validan en el backend, no solo en la interfaz.
- Ningún dato personal ni token en el HTML.
- El JavaScript solo agrega interacción, nunca reglas de negocio.
- Una pieza, un canal.
- Todo cambio de reglas lleva test.
- Versiones fijadas, con ejemplos del propio repositorio para cada convención.
- Un solo comando (`make check`) corre lint, typecheck y tests. El agente lo ejecuta antes de dar algo por terminado.

---

## 11. Flujo agéntico

1. El arquitecto escribe un spec por bloque antes del código, en formato dado/cuando/entonces, con criterios de aceptación que mapean a tests concretos y una sección de fuera de alcance.
2. El agente construye el bloque con `AGENTS.md` y `make check` como guía.
3. El tester valida comportamientos contra el spec. Sus reportes alimentan al agente.
4. El agente itera hasta que el comportamiento coincide con lo escrito, no con su interpretación.

Estructura sugerida del repositorio: `backend/` (Django, templates, dominio), `frontend/` (Vite y Tailwind), `docs/adr/` (decisiones), `docs/specs/` (specs por bloque), `compose.yml`, `AGENTS.md`, `Makefile`.

---

## 12. Spike (solo planeación)

Tres pruebas, en este orden, cada una con criterio de paso o no paso.

### Spike 1: pipeline

Una ficha renderizada por template con Tailwind y django-vite, en Docker.

Pasa si:

- Desarrollo con recarga en caliente y producción con assets con hash se ven igual.
- La imagen final no contiene Node.
- Título, meta y JSON-LD están en el HTML inicial.
- `make check` corre completo dentro del contenedor.

### Spike 2: núcleo de dominio

Pieza con estado y canal, apartado con expiración y transiciones solo por servicio.

Pasa si:

- Dos apartados simultáneos de la misma pieza dan un solo ganador, en muchas repeticiones.
- Una transición inválida se rechaza.
- Cada cambio deja su entrada de auditoría.

### Spike 3: datos reales

Importar entre 50 y 100 filas reales del Excel y las libretas.

Pasa si:

- Filas importadas más filas en cuarentena suman el total.
- Queda medida la tasa de cuarentena. Ese número decide cuánto cuesta la captura.

### En los tres

Se mide el flujo agéntico: iteraciones por bloque, errores de convención y si los reportes del tester bastan para que el agente corrija solo.

### Fuera del spike

Pagos con webhook, Flutter, modo sin conexión, descuentos, cierre de periodo, SEO completo y migración de GoTrendier.

---

## 13. Orden de construcción tras el spike

1. Vocabularios y modelo mínimo de pieza.
2. Importador con cuarentena.
3. Alta rápida desde el teléfono, con QR.
4. Modo evento: efectivo, transferencia con apartado y arqueo.
5. Vitrina: catálogo, ficha y "Me interesa" por WhatsApp.
6. Migración de GoTrendier por lotes.

Después: cierre de periodo, descuentos, checkout en línea con webhook, alertas de búsqueda y app Flutter.

---

## 14. Criterios de aceptación clave para el tester

**Estados y concurrencia**

- Una pieza reservada o con pago pendiente rechaza pasar a "En evento".
- Una pieza en evento no aparece como comprable ni acepta reservas.
- Una pieza vendida rechaza la transición manual a disponible.
- Dos reservas simultáneas de la misma pieza dan un solo ganador.
- Ninguna transición cambia el estado sin motivo y sin entrada de auditoría.
- Un usuario sin permiso de baja recibe rechazo en el backend aunque el botón esté oculto.

**Apartados**

- Un apartado por transferencia en bazar expira en el plazo del evento y la pieza vuelve a "En evento".
- Extender funciona una sola vez por apartado y queda registrado.
- Confirmar una transferencia vencida se rechaza hasta que el operador reactiva el apartado.
- Reactivar un apartado de una pieza ya vendida se rechaza.

**Dinero y cierre**

- El pago en efectivo actualiza el efectivo esperado del evento al momento.
- El arqueo registra la diferencia entre lo contado y lo esperado, con motivo.
- Una transferencia pendiente no suma al cierre hasta confirmarse.
- Confirmar dos veces el mismo pago no duplica la venta.
- Una venta con precio distinto al de lista guarda ambos precios y el motivo.
- Un cierre confirmado rechaza ediciones. Las correcciones entran como movimientos nuevos.

**Datos e importación**

- Filas del Excel igual a importadas más cuarentena.
- No hay dos piezas con el mismo QR.
- Una pieza migrada de GoTrendier tiene un solo canal activo.
- Una pieza marcada como "migrando" no aparece como comprable en ningún lado.
- Marca, categoría y condición solo aceptan valores válidos.

**QR y vitrina**

- Un escaneo sin sesión muestra la ficha pública. Con sesión de operador abre el modo evento.
- La URL de una pieza dada de baja responde con el código que corresponde a su motivo.
- La ficha incluye título, meta y JSON-LD en el HTML inicial.

---

## 15. Riesgos

- **La captura manual del inventario** toma tiempo y alguien tiene que hacerla. Es el costo más alto del proyecto.
- **La vitrina no reemplaza de inmediato el tráfico de GoTrendier.** Puede haber menos visitas al principio.
- **El admin de Django en el teléfono es incómodo.** Por eso el modo evento son páginas móviles propias.
- **Las acciones manuales de estado** pueden romper el inventario si se saltan las reglas. Se mitigan con acciones explícitas, permisos y auditoría.
- **Comprobantes de transferencia falsificables.** Confirmar solo contra la banca.
- **Una página en línea no genera demanda por sí sola.** El crecimiento necesita contenido, redes y, durante un tiempo, quizá GoTrendier como fuente de visitas.
- **Calidad de los datos de origen.** La tasa de cuarentena del spike 3 es la medida real del esfuerzo.

---

## 16. Pendientes e información por conseguir

**Del cliente**

- Muestra real del Excel y de las libretas.
- Exportación de publicaciones y ventas de GoTrendier, si existe.
- Número de operadores y sus roles (captura, ventas, supervisión).
- Volumen de piezas nuevas por semana y cantidad de bazares por mes.
- Si las fotos se toman desde el teléfono o desde una computadora.
- Política de devoluciones.
- Si se entrega la pieza al confirmar la transferencia o cuando el dinero está en cuenta (el plan asume lo primero).
- Si se aceptarán pagos en efectivo en línea (por ejemplo OXXO) y cómo manejar la reserva.

**Del arquitecto**

- Proveedor de pagos en línea, al iniciar el checkout.
- Tema del admin de Django y verificación de que siga vigente.
- Redacción del `AGENTS.md` inicial y del spec del primer bloque.
- Formato de reporte del tester que alimenta a los agentes.

---

## 17. Opciones descartadas, por si se reabren

- **SPA con Vite y React para la tienda:** mal SEO en fichas y estados HTTP difíciles de controlar. No hay interfaz compleja que lo justifique.
- **React Router v7 o Next.js con SSR:** funcionan, pero obligan a un proceso de Node en producción.
- **FastAPI como backend principal:** buena API, pero exige construir admin, auth y jobs.
- **Híbrido Django y FastAPI con la misma base:** duplica reglas de negocio y esquemas.
- **Todo 100% en línea:** descartado. El 70% de las ventas está en bazares.
- **Admin propio en React:** se pospone. Se reconsidera cuando lleguen cierres y descuentos complejos.
