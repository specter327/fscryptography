# Propuesta: backend criptográfico transparente para Termux

## Estado

**Propuesta corregida. No implementada. No declara soporte Termux.**

Esta propuesta está subordinada a una restricción invariable: el cambio de backend debe ser imperceptible para quien utiliza fscryptography.

## Requisitos no negociables

La implementación para Termux:

1. **No modifica la API pública:** no añade, elimina ni cambia funciones, clases, métodos, argumentos, propiedades, excepciones documentadas ni valores de retorno.
2. **No modifica las capacidades:** todas las operaciones y garantías disponibles en las plataformas actuales deben seguir disponibles en Termux.
3. **No modifica los formatos persistentes:** MasterKey, contenido cifrado, nombres y metadatos conservan sus formatos, versiones, reglas de serialización y semántica actuales.
4. **No requiere migración:** los datos existentes se abren y procesan sin conversión, exportación ni intervención del usuario.
5. **No expone selección de backend:** no añade opciones, marcadores, configuración ni decisiones de plataforma a la API o al flujo de uso.
6. **No altera el comportamiento observable:** errores, validaciones, integridad, atomicidad, límites y semántica de las operaciones deben mantenerse equivalentes.
7. **No reduce la seguridad:** no se relajan algoritmos, tamaños de clave, derivación, autenticación, validaciones ni tratamiento de errores.

La única diferencia permitida es interna: la implementación concreta que proporciona las primitivas criptográficas en Termux.

## Contexto técnico

El runtime actual depende de Google Tink. Los keysets Tink para contenido (`AES256_GCM_HKDF_1MB`) y nombres (`AES256_GCM`) se serializan dentro de MasterKey v1.0. Además, fscryptography utiliza las primitivas abiertas desde esos keysets y emplea `cryptography` AES-GCM y `argon2-cffi` Argon2id para la protección opcional por contraseña.

Por tanto, sustituir Tink por una biblioteca con primitivas distintas, aunque sean criptográficamente seguras, no preserva automáticamente los datos ni el comportamiento actuales.

En Termux se reparó el enlace de Protobuf: `protoc --version` devuelve `libprotoc 36.2`. La instalación aislada de `tink==1.16.1` continúa requiriendo Bazel. El objetivo es evitar que la instalación normal del usuario dependa de ese toolchain, sin trasladar el coste a cambios de API o de formato.

## Estrategia: implementación alternativa compatible

Investigar una implementación interna específica para Termux que proporcione las mismas primitivas y respete exactamente los contratos actuales de Tink.

No se trata de diseñar un segundo formato criptográfico para fscryptography. Se trata de proporcionar, mediante un proveedor distinto, compatibilidad con el formato y las operaciones existentes.

### Compatibilidad obligatoria

El backend alternativo deberá preservar:

- La lectura y escritura de los keysets serializados actualmente en MasterKey v1.0.
- Los tipos de keyset, identificadores, parámetros y reglas de serialización que utiliza el proyecto.
- La semántica y el formato binario de AES256_GCM para nombres.
- La semántica y el formato binario de AES256_GCM_HKDF_1MB para contenido en streaming.
- La protección de MasterKey con contraseña: Argon2id, parámetros, salt, nonce, AES-GCM, AAD y estructura persistida actuales.
- Los límites, errores de autenticación, detección de corrupción y comportamiento ante entradas inválidas.
- La interoperabilidad cruzada: datos creados en Termux deben poder abrirse en las plataformas actuales y viceversa, usando la implementación estándar existente.

No se aceptará compatibilidad basada únicamente en que ambas bibliotecas implementen AES-GCM. Deben coincidir los detalles completos de los formatos, derivación, framing, nonces, AAD y serialización.

### Proveedores candidatos

Se pueden evaluar libsodium/PyNaCl, PyCA/cryptography u otros proveedores mantenidos como fuentes de primitivas de bajo nivel.

La biblioteca candidata no define el formato de fscryptography. Por ejemplo, la interfaz `secretstream` de libsodium no puede reemplazar directamente el formato Tink Streaming AEAD. Solo se podrá utilizar si una implementación demuestra compatibilidad exacta con el contrato y el formato actuales; no se permitirá introducir un framing incompatible.

Si no existe una implementación alternativa viable que preserve esos contratos, se deberá resolver la distribución/instalación de Tink en Termux (por ejemplo, mediante artefactos binarios compatibles o un proceso de empaquetado reproducible). No se cambiará la API ni el formato para sortear el problema de instalación.

## Arquitectura interna

- Mantener intactas las capas públicas y de dominio.
- Introducir, solo si el inventario demuestra que es necesario, una frontera interna para las operaciones criptográficas actualmente acopladas a Tink.
- Mantener el backend estándar actual como referencia de comportamiento y compatibilidad.
- Implementar el proveedor Termux detrás de esa frontera, sin filtrar tipos ni conceptos del proveedor.
- Seleccionar la implementación internamente mediante disponibilidad/entorno de ejecución, sin almacenar esa selección en los datos ni exponerla al usuario.
- Al abrir datos, interpretar siempre el formato existente; nunca elegir un formato según la plataforma.
- Si el backend alternativo no puede interpretar o producir exactamente el formato actual, debe fallar la validación de viabilidad y no activarse.

La detección de plataforma puede seleccionar una implementación interna, pero nunca puede cambiar el algoritmo, el formato, la semántica o el resultado observable.

## Plan de trabajo

### Fase 0 — Inventario y caracterización

- Revisar todos los usos directos de Tink y de sus primitivas.
- Identificar exactamente los formatos persistentes y sus invariantes.
- Registrar key templates, keysets, parámetros, AAD, framing, nonces, límites y excepciones.
- Crear o consolidar vectores de caracterización con la implementación estándar.
- Registrar el comportamiento público actual mediante pruebas de caracterización.
- No modificar runtime, API, dependencias ni formatos en esta fase.

### Fase 1 — Viabilidad del proveedor

- Comprobar instalación de candidatos en Termux ARM64/Bionic y en la versión de CPython objetivo.
- Verificar disponibilidad de RNG seguro y primitivas requeridas.
- Probar si el candidato permite reproducir los formatos exactos existentes.
- Registrar versiones, ABI, comandos y resultados reproducibles.
- Descartar cualquier candidato que requiera cambiar formatos o semántica.
- No activar el candidato en el runtime todavía.

### Fase 2 — Especificación de equivalencia

Para cada operación criptográfica, definir pruebas diferenciales contra la implementación estándar:

- apertura de keysets existentes;
- cifrado y descifrado AEAD de nombres;
- cifrado y descifrado Streaming AEAD;
- protección y apertura de MasterKey con y sin contraseña;
- interoperabilidad bidireccional entre backend estándar y backend Termux;
- errores por autenticación fallida, corrupción, truncamiento y parámetros inválidos.

Los vectores deben incluir datos vacíos, pequeños y grandes, límites de segmentos, nombres Unicode y casos negativos. La equivalencia debe comprobarse a nivel de formato y semántica, no solo mediante round-trip dentro del mismo backend.

### Fase 3 — Adaptación interna

- Implementar la frontera interna mínima que exija el código real.
- Mantener sin cambios los contratos públicos.
- Adaptar el backend estándar sin modificar sus bytes ni su semántica.
- Implementar el proveedor Termux únicamente contra la especificación de equivalencia aprobada.
- No introducir identificadores de backend en archivos ni nuevas versiones de formato.
- No añadir configuración pública para seleccionar proveedores.

### Fase 4 — Validación integral

- Ejecutar las pruebas de caracterización y la suite existente.
- Ejecutar pruebas diferenciales e interoperabilidad cruzada en ambos sentidos.
- Verificar que la API pública y sus firmas no cambiaron.
- Verificar que no se alteraron capacidades, límites ni comportamiento de filesystem.
- Probar instalación limpia en Termux sin exigir Bazel al usuario final.
- Ejecutar pruebas de filesystem en almacenamiento privado y documentar por separado los límites del almacenamiento compartido de Android.
- Someter el diseño y la implementación criptográfica a revisión de seguridad.

### Fase 5 — Distribución y soporte

- Declarar dependencias por plataforma solo con evidencia reproducible.
- Evitar que Termux instale Tink si el proveedor alternativo compatible puede operar sin él.
- No declarar soporte hasta superar todos los criterios de aceptación.
- Mantener la matriz de plataformas y versiones probadas.

## Criterios de aceptación

La implementación solo se acepta si se cumplen todos estos puntos:

- No hay cambios en la API pública ni en sus firmas.
- No hay cambios en las capacidades ni en las garantías documentadas.
- No hay cambios en los formatos, versiones ni bytes estructurales persistidos.
- Los datos preexistentes se abren en Termux sin migración.
- Los datos creados en Termux se abren en las plataformas existentes, y viceversa.
- La suite criptográfica y las pruebas diferenciales pasan.
- Los resultados y errores observables conservan la semántica actual.
- La instalación limpia de Termux no exige al usuario instalar Bazel ni un toolchain de compilación.
- No se han relajado controles ni garantías de seguridad.
- La revisión de seguridad aprueba la equivalencia criptográfica.

## Decisiones y límites

| Tema | Decisión |
|---|---|
| API pública | Inmutable |
| Capacidades | Inmutables |
| Formatos persistentes | Inmutables |
| Migración de datos | No requerida ni introducida |
| Selección de backend por usuario | No existe |
| Selección interna por plataforma | Permitida solo si es transparente |
| Tink | Referencia de compatibilidad y backend estándar |
| libsodium/PyNaCl | Candidatos no validados; no implican cambio de formato |
| Bazel en instalación final | Debe evitarse |
| Si no se logra equivalencia | Resolver empaquetado/distribución de Tink; no cambiar contratos |

## Decisión solicitada

Autorizar el inventario del contrato actual y la prueba de viabilidad de proveedores con el requisito de equivalencia transparente. No autorizar cambios de API, capacidades, formatos, migraciones ni algoritmos incompatibles. La implementación solo podrá avanzar si demuestra interoperabilidad exacta con los datos y operaciones actuales.
