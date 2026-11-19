# Propuesta: backend criptográfico para Termux

## Estado

**Propuesta de arquitectura. No implementada. No habilita todavía soporte Android/Termux.**

## Contexto y decisión que motiva esta propuesta

El backend actual depende directamente de Google Tink. Tink se compila desde fuente en el entorno Termux observado y su instalación requiere Protobuf y Bazel. En el dispositivo de validación:

- Se corrigió el enlace dinámico de Protobuf actualizando `libc++` y reinstalando `protobuf`.
- `protoc --version` ya funciona y devuelve `libprotoc 36.2`.
- La instalación de `tink==1.16.1` avanza hasta la fase de preparación de build, pero falla porque no encuentra un ejecutable Bazel.
- Termux ofrece un paquete Bazel ARM64, pero hacer depender la instalación cotidiana de una compilación de Tink con Bazel no satisface el objetivo de distribución simple.

La decisión propuesta es dejar de exigir Tink en instalaciones Termux nuevas y desarrollar un backend alternativo específico para Termux. No se pretende reemplazar ni reinterpretar silenciosamente los formatos existentes.

## Objetivos

1. Instalar y ejecutar fscryptography en Termux sin exigir Tink ni Bazel al usuario final.
2. Mantener la API pública de fscryptography.
3. Mantener un backend Tink para leer y operar con los contenedores y datos existentes.
4. Identificar inequívocamente el backend y el perfil criptográfico usados por cada formato persistente.
5. Permitir que una instalación pueda abrir datos creados por otro backend cuando exista un lector compatible.
6. Evitar implementaciones criptográficas caseras y cambios de algoritmo sin revisión.
7. Aislar la selección del backend del código de operaciones del filesystem.

## Fuera de alcance

- Declarar Android completo como plataforma soportada. El alcance inicial es Termux en Android ARM64.
- Cambiar el formato Tink existente o invalidar MasterKey v1.0.
- Hacer migraciones automáticas o destructivas.
- Reducir tamaños de clave, requisitos de autenticación o parámetros de derivación de claves para facilitar la instalación.
- Prometer compatibilidad con cualquier versión de Android, Termux, Python o arquitectura antes de probarla.

## Propuesta arquitectónica

### 1. Contrato interno de backend

Introducir una interfaz interna independiente del filesystem y de la serialización concreta. El contrato debe exponer las operaciones criptográficas que realmente necesita el dominio:

- creación y restauración de material de claves;
- AEAD para nombres/metadatos;
- cifrado autenticado de contenido en streaming;
- cifrado autenticado para envolver/proteger material de claves;
- identificación estable del backend y del perfil criptográfico;
- validación estricta de parámetros y errores de autenticación.

El contrato no debe exponer tipos de Tink, PyNaCl ni de otra biblioteca. Los adaptadores convierten entre tipos específicos de proveedor y el contrato interno.

Las capas de filesystem y de gestión de archivos no deben conocer qué backend está activo.

### 2. Backends iniciales

**TinkBackend**
- Conserva la implementación actual y la lectura de los keysets serializados en MasterKey v1.0.
- Se mantiene como backend de compatibilidad y como opción para los entornos donde Tink se instala de forma reproducible.
- No se debe eliminar mientras existan datos que dependan de él.

**TermuxBackend (nombre provisional)**
- Backend alternativo para nuevas MasterKeys y nuevos datos creados en Termux.
- No debe depender de Google Tink ni de Bazel.
- Debe utilizar primitivas de una biblioteca criptográfica mantenida y revisada.
- Candidato inicial a evaluar: libsodium mediante sus bindings Python mantenidos (por ejemplo, PyNaCl), especialmente las interfaces AEAD y secretstream. Esta elección es una hipótesis de implementación, no una decisión cerrada: primero deben verificarse disponibilidad, mantenimiento, instalación reproducible y soporte real en Termux/Bionic.
- No implementar un protocolo de streaming propio basado en concatenar llamadas AES-GCM sin especificación formal, análisis de nonce, framing, autenticación de orden/truncamiento y revisión criptográfica.

La elección definitiva de proveedor y algoritmos queda bloqueada hasta completar una prueba de viabilidad en Termux y una revisión de seguridad del diseño.

### 3. Selección del backend

La selección debe ser explícita al crear datos nuevos y determinada por metadatos autenticados al abrir datos existentes.

- La detección de plataforma puede proponer un backend predeterminado para nuevas instalaciones Termux.
- La detección de plataforma nunca debe decidir cómo descifrar un archivo existente.
- El identificador persistido de backend/perfil determina qué lector debe abrir cada objeto.
- Si el backend indicado no está instalado, se devuelve un error claro de backend no disponible. No se intenta otro backend silenciosamente.
- Debe existir una opción explícita para seleccionar backend cuando la API pública lo necesite, sin filtrar tipos internos de proveedor.

### 4. Versionado y compatibilidad de formatos

El formato actual que serializa keysets Tink no es intercambiable con material de claves de otro proveedor.

Se propone:

- Mantener MasterKey v1.0 como formato Tink legacy, con lector compatible.
- Definir una nueva versión de MasterKey para el nuevo backend. Debe incluir versión, identificador de backend, identificador de perfil criptográfico, parámetros necesarios y material de claves protegido.
- Versionar también el formato de contenido y el formato de nombres si sus estructuras o primitivas cambian.
- Los identificadores de algoritmo/perfil deben ser constantes registradas, no nombres de clases Python ni versiones de paquetes.
- Los metadatos que controlan la interpretación del formato deben quedar autenticados.
- Rechazar versiones, perfiles, parámetros o identificadores desconocidos; nunca degradar silenciosamente a otro algoritmo.

No se debe asumir que basta con cambiar la serialización de keysets: el cifrado de contenido, el streaming, los nombres y el envoltorio de MasterKey también deben quedar especificados.

### 5. Compatibilidad y migración

- Los objetos Tink existentes deben seguir abriéndose mediante TinkBackend.
- TermuxBackend solo crea objetos con el nuevo formato/perfil.
- La migración, si se implementa, será una operación explícita, con origen y destino identificados, verificación de integridad y preservación del original hasta confirmar el resultado.
- No se realizará conversión in-place implícita al abrir.
- Deben existir vectores de interoperabilidad que permitan comprobar apertura entre plataformas y versiones del paquete.

## Dependencias y distribución

La meta es que la instalación Termux no necesite Bazel ni un compilador para instalar Tink. Eso no significa que cualquier binding alternativo sea automáticamente instalable: PyNaCl u otro candidato puede tener dependencias nativas.

Antes de adoptarlo se debe probar:

1. Disponibilidad de la biblioteca nativa en los repositorios Termux oficiales.
2. Disponibilidad de wheel compatible o procedimiento de build reproducible para CPython/Android ABI.
3. Instalación desde un entorno Termux limpio.
4. Ejecución de primitivas en Android ARM64/Bionic.
5. Ausencia de dependencias de compilación en el camino normal de instalación, si se distribuye un wheel adecuado.

Las dependencias deben declararse por extra o marcador de plataforma solo después de validar el mecanismo de instalación. No se deben añadir marcadores especulativos ni hacer que Termux instale Tink innecesariamente.

## Plan de trabajo

### Fase 0 — Inventario del contrato actual
- Revisar todos los usos directos de Tink y los formatos persistentes.
- Identificar las operaciones requeridas por nombres, contenido y MasterKey.
- Documentar invariantes, límites, tamaños, AAD, framing y errores.
- Añadir pruebas de caracterización del backend actual sin cambiar su comportamiento.

### Fase 1 — Prueba de viabilidad de proveedor
- Evaluar libsodium/PyNaCl y, si no cumple los requisitos de Termux, comparar alternativas mantenidas.
- Probar instalación en Termux limpio con la versión de Python objetivo.
- Probar AEAD, secretstream, manejo de errores y disponibilidad de RNG seguro.
- Registrar versiones exactas, ABI, arquitectura y comandos reproducibles.
- No integrar el candidato en el runtime todavía.

### Fase 2 — Especificación criptográfica y de formatos
- Especificar perfiles y formatos versionados para MasterKey, contenido y nombres.
- Definir derivación de claves, nonces, AAD, framing, detección de truncamiento/reordenamiento y límites de tamaño.
- Definir comportamiento ante corrupción, autenticación fallida y parámetros inválidos.
- Solicitar revisión de seguridad antes de implementar el formato de producción.

### Fase 3 — Abstracción y adaptadores
- Introducir el contrato interno.
- Adaptar Tink sin cambiar bytes ni semántica de los formatos actuales.
- Implementar el backend alternativo solo contra la especificación aprobada.
- Mantener las capas superiores libres de dependencias de proveedor.

### Fase 4 — Formatos, pruebas y migración
- Implementar lectores/escritores versionados.
- Crear vectores de prueba fijos y pruebas cruzadas entre plataformas.
- Probar compatibilidad legacy Tink y rechazo seguro de formatos desconocidos.
- Implementar migración explícita únicamente después de validar los lectores y escritores.

### Fase 5 — Distribución y soporte Termux
- Definir dependencias y extras por plataforma con evidencia de instalación.
- Construir y probar wheels cuando sea posible.
- Ejecutar la suite criptográfica en Termux ARM64/Bionic y las pruebas filesystem en almacenamiento privado.
- Documentar por separado límites del almacenamiento compartido de Android.
- Declarar soporte solo para las combinaciones de Android, Termux, Python y arquitectura probadas.

## Criterios de aceptación

La propuesta no se considera implementada hasta que:

- Tink no sea necesario para instalar el backend Termux.
- La instalación sea reproducible en un Termux limpio sin intervención manual no documentada.
- Los formatos legacy Tink sigan siendo legibles en plataformas con Tink disponible.
- Los formatos nuevos identifiquen y autentiquen su backend/perfil.
- Existan vectores de prueba y pruebas negativas para autenticación, corrupción, truncamiento y parámetros inválidos.
- Se hayan probado archivos vacíos, pequeños y grandes, nombres Unicode, integridad y errores de filesystem.
- Una revisión de seguridad apruebe el diseño criptográfico y el formato.
- La distribución no requiera Bazel en el dispositivo usuario.

## Riesgos y decisiones pendientes

| Tema | Estado |
|---|---|
| Proveedor alternativo | Pendiente de prueba; libsodium/PyNaCl es candidato |
| Disponibilidad de bindings en Termux | No verificada |
| Algoritmos y perfiles definitivos | Pendientes de especificación/revisión |
| Nuevo formato MasterKey | Requerido; diseño pendiente |
| Nuevo formato de contenido/nombres | Requerido si cambia la primitiva o estructura |
| Lectura legacy Tink | Requisito obligatorio |
| Migración entre backends | Explícita y posterior; no incluida en la primera entrega |
| Android fuera de Termux | Fuera del alcance inicial |

## Decisión solicitada

Aprobar la dirección arquitectónica de desarrollar un backend alternativo específico para Termux, manteniendo Tink como backend legacy/interoperable, y autorizar únicamente la fase de inventario y prueba de viabilidad del proveedor. La selección final del algoritmo, el formato nuevo y la implementación quedan condicionados a resultados reproducibles y revisión de seguridad.
