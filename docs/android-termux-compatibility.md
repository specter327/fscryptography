# Android y Termux: evaluación de compatibilidad

## Estado

**Estado: investigación y habilitación pendientes. No declarar soporte todavía.**

Objetivo: permitir instalar y ejecutar fscryptography en Android mediante Termux, manteniendo la API pública y las garantías criptográficas. La compatibilidad no se deduce de que el código Python sea portable: deben funcionar el intérprete, las distribuciones binarias o compilaciones nativas de todas las dependencias y las operaciones del filesystem.

Este documento registra la evaluación inicial y define una ruta de implementación verificable. No introduce un backend criptográfico alternativo ni cambia el formato MasterKey o de archivos.

## Diagnóstico reproducido

El entorno reportado por un usuario es Termux sobre Android, CPython 3.14, arquitectura Android ARM64 (pendiente confirmar con `uname -m`).

Instalación editable:

```text
pip install -e ./fscryptography
...
Collecting tink<2,>=1.16.1
Downloading tink-1.16.1.tar.gz
...
FileNotFoundError: Could not find protoc executable.
```

El ejecutable `protoc` existe en `$PREFIX/bin/protoc`, pero no puede iniciarse:

```text
CANNOT LINK EXECUTABLE "protoc":
cannot locate symbol "_ZNSt6__ndk113__hash_memoryEPKvm"
referenced by "$PREFIX/lib/libprotoc.so"
```

Esto es un fallo de enlace dinámico del entorno Termux (la biblioteca protobuf/libc++ instalada), no un error de ejecución de fscryptography. Pip no ha completado la instalación de Tink; por tanto, todavía no se ha importado ni ejecutado el código de fscryptography en ese dispositivo.

## Hallazgos de arquitectura

### Dependencia criptográfica directa

El runtime declara:

- `tink>=1.16.1,<2`
- `argon2-cffi>=23.1,<26`
- `cryptography>=42,<47`

El código de producción importa Tink directamente desde `_master_key.py`. Ese módulo:

1. Genera keysets Tink para contenido (`AES256_GCM_HKDF_1MB`) y nombres (`AES256_GCM`).
2. Serializa esos keysets dentro del contenedor MasterKey v1.0.
3. Los vuelve a parsear para reconstruir primitivas Streaming AEAD y AEAD.
4. Usa `cryptography` AES-GCM y `argon2-cffi` Argon2id para la protección opcional por contraseña del contenedor.

El resto de las operaciones consume las primitivas abiertas desde `_KeyMaterial`. Sin embargo, el formato persistente de MasterKey contiene keysets serializados específicos de Tink. Por tanto, Tink no es hoy un adaptador intercambiable: forma parte del formato de claves existente.

### Consecuencia

No se debe reemplazar Tink por otra biblioteca bajo la misma versión de formato. Hacerlo podría invalidar MasterKeys y archivos ya creados, o crear incompatibilidades silenciosas.

La alternativa de desacoplar el backend es viable, pero requiere:

- especificación de un contrato interno de primitivas;
- identificador explícito de backend y perfil criptográfico en un nuevo formato versionado;
- lectores de compatibilidad para los contenedores Tink existentes;
- estrategia de migración explícita y pruebas de interoperabilidad;
- revisión criptográfica independiente antes de adoptar otro backend.

La primera opción a investigar debe ser compilar/instalar Tink en Termux correctamente. Solo si no es viable o mantenible debe abrirse un proyecto separado de backend alternativo y formato versionado.

## Causas que deben comprobarse por separado

1. **Protobuf/libc++ del dispositivo:** el error actual de `protoc` indica que el binario y las bibliotecas instaladas no son ABI compatibles. Primero se debe reparar el entorno de paquetes Termux y verificar `protoc --version`.
2. **Build de Tink:** una vez operativo protoc, Tink puede requerir toolchain, Bazel y dependencias adicionales. La disponibilidad de `protoc` por sí sola no garantiza que Tink pueda compilarse.
3. **CPython 3.14:** el proyecto declara `requires-python >=3.11`, pero sus clasificadores solo enumeran 3.11–3.13. Esa declaración no constituye evidencia de compatibilidad con 3.14. Se debe validar cada dependencia y el propio paquete antes de ampliar los clasificadores.
4. **argon2-cffi y cryptography:** ambas pueden necesitar extensiones nativas. Debe probarse su instalación en Android/Bionic de forma independiente.
5. **Filesystem Android:** el acceso a almacenamiento compartido en Termux está mediado por permisos y SAF/almacenamiento de Android. La compatibilidad del backend no demuestra que todas las rutas o semánticas de filesystem estén soportadas.

## Ruta de trabajo

### Fase 1 — Reproducibilidad del entorno

Registrar en cada prueba:

- modelo/versión Android y arquitectura (`uname -a`, `uname -m`);
- versión de Termux y origen del paquete;
- `python --version`, `python -m pip --version`;
- versiones de `protobuf`, `libc++`, `clang`, `make`, `pkg-config`;
- `command -v protoc`, `protoc --version`;
- resultado de `ldd`/herramientas disponibles y variables `LD_LIBRARY_PATH` y `LD_PRELOAD`;
- salida completa de pip con `-v`.

No copiar bibliotecas compartidas manualmente ni mezclar paquetes de distintos repositorios para forzar el enlace.

### Fase 2 — Aislar las dependencias

En un entorno Termux limpio, probar por separado:

1. `python -m pip install tink==1.16.1`
2. `python -m pip install argon2-cffi`
3. `python -m pip install cryptography`

Registrar si cada una instala desde wheel o compila desde fuente. No modificar todavía los rangos de dependencias para ocultar fallos.

### Fase 3 — Prueba de backend sin filesystem

Cuando las tres dependencias estén instaladas:

- importar Tink, Argon2 y AESGCM;
- generar y abrir los dos keysets Tink;
- cifrar/descifrar datos con Streaming AEAD y AEAD;
- generar y abrir MasterKey aleatoria;
- generar y abrir MasterKey protegida por contraseña;
- verificar errores de autenticación ante contraseña incorrecta y ciphertext alterado.

La suite existente de `tests/backend_validation` y `tests/master_key_format` debe reutilizarse cuando sea ejecutable en Android. No se debe declarar backend validado solo por una importación exitosa.

### Fase 4 — Integración filesystem en Termux

Probar en almacenamiento privado de Termux primero (`$HOME`), y luego en almacenamiento compartido únicamente después de `termux-setup-storage`:

- archivos vacíos, pequeños y grandes;
- round-trip con comparación SHA-256;
- nombres ASCII y Unicode;
- conflictos de destino y permisos;
- enlaces simbólicos y tipos no admitidos;
- fallos y temporales;
- rutas de almacenamiento privado y compartido.

No usar datos originales: las operaciones transforman archivos in-place.

### Fase 5 — Decisión de arquitectura

- **Si Tink compila y pasa la suite:** conservar el backend actual y documentar Termux/Android como combinación validada solo para las versiones probadas.
- **Si Tink no puede mantenerse en Termux:** preparar una propuesta de backend desacoplado con formato versionado. No cambiar el backend ni los formatos existentes sin especificación, vectores, migración y revisión de seguridad.
- **Si Python 3.14 es el único bloqueo:** mantener el soporte limitado a versiones comprobadas; no declarar 3.14 solo por `requires-python`.

## Criterios para declarar soporte Android/Termux

- Instalación reproducible desde un entorno limpio, sin intervención manual no documentada.
- Todas las dependencias instaladas y fijadas dentro de los rangos declarados.
- Suite criptográfica y de formato MasterKey aprobada.
- Round-trip de filesystem y verificación de integridad aprobados.
- Pruebas en almacenamiento privado y definición explícita de límites para almacenamiento compartido.
- CI reproducible o procedimiento de validación manual versionado, con evidencia del dispositivo y versiones.
- Documentación de limitaciones y matriz exacta de combinaciones probadas.

## No hacer

- No cambiar Tink por PyCA/cryptography sin cambiar y versionar el formato que almacena los keysets.
- No relajar autenticación, algoritmos, tamaños de clave ni validaciones para facilitar compatibilidad.
- No declarar Android compatible porque el paquete se importe.
- No añadir Python 3.14 a los clasificadores antes de ejecutar la matriz.
- No incorporar hacks de `LD_LIBRARY_PATH`, copias de `libc++` ni binarios `protoc` de otras distribuciones como solución del paquete.
- No modificar la MasterKey v1.0 ni el formato de archivos existente en esta fase.

## Resultado de esta fase

Se ha identificado que el acoplamiento con Tink atraviesa la serialización de MasterKey v1.0, por lo que una sustitución de backend no es un cambio local. El primer bloqueo observado es el entorno de compilación/enlace de protobuf en Termux. La siguiente acción técnicamente correcta es reparar y aislar el toolchain Termux y probar cada dependencia por separado; después se puede decidir con evidencia si hace falta una abstracción de backend.


## Actualización de decisión — 2026-11-19

La evaluación práctica posterior cambió la decisión de ruta:

- Se ejecutó `pkg reinstall libc++ protobuf` en Termux.
- `protoc --version` pasó a funcionar y devolvió `libprotoc 36.2`.
- La instalación aislada de `tink==1.16.1` avanzó hasta la preparación del build, pero se detuvo porque no encontró el ejecutable Bazel.
- El repositorio Termux consultado ofrece Bazel `9.3.2` para ARM64. Su mera disponibilidad no demuestra que esa versión sea compatible con el proceso de compilación de Tink 1.16.1 ni que el build completo vaya a ser mantenible.

Dado que exigir al usuario final que instale y mantenga un toolchain de compilación pesado no satisface el objetivo de distribución de fscryptography, se propone investigar una implementación interna alternativa para Termux. Esta implementación queda sujeta a equivalencia estricta con el backend actual; no constituye un formato criptográfico alternativo.

Esta dirección **sustituye la recomendación anterior de priorizar indefinidamente la compilación de Tink en Termux**. No elimina la necesidad de conservar Tink para leer MasterKey v1.0 y los datos existentes.

libsodium/PyNaCl y otros proveedores son únicamente candidatos para suministrar primitivas. No se autoriza cambiar algoritmos, API, capacidades, formatos persistentes, serialización, semántica ni comportamiento observable. El backend Termux deberá leer y escribir exactamente los formatos actuales y demostrar interoperabilidad bidireccional con el backend estándar. No se añadirán identificadores de backend a los datos, nuevas versiones de formato, migraciones ni opciones de selección para el usuario. Si no es posible demostrar esa equivalencia, deberá resolverse el empaquetado/distribución de Tink para Termux en lugar de cambiar los contratos existentes.

El alcance inicial queda limitado a Termux en Android ARM64. No se declara soporte Android general ni soporte Termux hasta superar los criterios de aceptación de la propuesta.


## Restricción de transparencia — aclaración del 2026-11-19

La propuesta de backend queda corregida por el requisito de que el cambio sea imperceptible para el usuario:

- API pública y firmas: sin cambios.
- Características, capacidades y garantías: sin cambios.
- MasterKey, keysets, contenido cifrado, nombres y metadatos: formatos y serialización existentes, sin migración.
- Uso, configuración, errores y semántica observable: sin cambios.
- Solo se permite sustituir internamente la implementación criptográfica en Termux, y únicamente si reproduce exactamente los contratos actuales y supera pruebas de interoperabilidad cruzada.

Queda descartado introducir un formato MasterKey nuevo, formatos separados de contenido/nombres, identificadores persistentes de backend, selección pública de backend o migraciones. La propuesta detallada y sus criterios de equivalencia están en [Propuesta: backend criptográfico transparente para Termux](termux-backend-proposal.md).

Si no puede implementarse un proveedor alternativo compatible byte a byte y semánticamente, la alternativa será distribuir/instalar Tink de forma reproducible en Termux. No se cambiará el contrato de fscryptography para acomodar las limitaciones de una dependencia.
