# Compatibilidad de plataformas

## Alcance y vocabulario

Este documento separa tres estados que no deben confundirse:

- **Objetivo de soporte:** combinación que el diseño v1 pretende soportar y para la que se deben implementar y ejecutar pruebas antes de declarar soporte.
- **Validación ejecutada:** combinación en la que existe evidencia de pruebas ejecutadas. Una prueba de backend criptográfico no valida por sí sola las operaciones de filesystem.
- **No soportado / no declarado:** combinación que no forma parte de la matriz inicial. Puede funcionar, pero no se promete compatibilidad.

La librería no debe inferir compatibilidad por el mero hecho de que Python o una dependencia pueda instalarse en una plataforma.

## Matriz objetivo v1

| Dimensión | Objetivo inicial | Estado |
|---|---|---|
| Sistema operativo | Windows 11 x86-64 | Objetivo; pendiente validación específica en cliente Windows 11. CI ejecutado en Windows Server 2025 Datacenter x86-64, build 26100 |
| Sistema operativo | Ubuntu 22.04 LTS x86-64 | Integración CI aprobada en Ubuntu 22.04.5 LTS, x86-64 |
| Sistema operativo | Ubuntu 24.04 LTS x86-64 | Integración CI aprobada en Ubuntu 24.04.5 LTS, x86-64 |
| Python | CPython 3.11 | Objetivo; backend criptográfico validado en Ubuntu |
| Python | CPython 3.12 | Objetivo; backend criptográfico validado en Ubuntu |
| Python | CPython 3.13 | Objetivo; backend criptográfico validado en Ubuntu |
| Filesystem Windows | NTFS local | Integración CI aprobada en volumen NTFS de Windows Server 2025; cliente Windows 11 pendiente |
| Filesystem GNU/Linux | ext4 local | Integración CI aprobada en volúmenes ext4 de Ubuntu 22.04.5 y 24.04.5 |
| Arquitectura | x86-64 | Objetivo inicial |

La matriz anterior define el alcance que debe cubrir la validación; **no constituye una declaración de soporte ya alcanzado**.

### Fuera de la matriz inicial

- Windows 10: no se declara soportado en v1.
- macOS: fuera de alcance inicial; podrá evaluarse después.
- ARM64 y otras arquitecturas: no declaradas hasta disponer de CI y pruebas de backend/filesystem.
- Filesystems distintos de NTFS y ext4, incluidos exFAT, FAT32, ReFS, XFS, Btrfs, ZFS, NFS, SMB y volúmenes removibles: no declarados en v1 hasta validarlos.
- Python distinto de CPython 3.11–3.13, incluidos PyPy y versiones futuras: no declarado.

No se debe ampliar esta matriz por analogía. Cada nueva combinación requiere pruebas reproducibles.

## Evidencia de validación existente

El workflow [backend-validation.yml](../.github/workflows/backend-validation.yml) ejecuta pruebas de backend en GitHub Actions sobre Ubuntu para Python 3.10, 3.11, 3.12 y 3.13. El workflow [real-filesystem-integration.yml](../.github/workflows/real-filesystem-integration.yml) ejecuta integración sobre `ubuntu-22.04`, `ubuntu-24.04` y `windows-latest`, con Python 3.11–3.13.

- Tink Streaming AEAD con `AES256_GCM_HKDF_1MB`.
- Tink AEAD convencional `AES256_GCM` para nombres.
- Protección MasterKey mediante Argon2id y AES-256-GCM.
- Vectores iniciales del formato MasterKey.

Los cuatro entornos de Python pasaron en el run documentado de CI. Esta evidencia valida las integraciones criptográficas probadas en esos entornos; **no valida** operaciones reales de filesystem, NTFS, Windows, ext4 ni atomicidad en ninguna plataforma.

Python 3.10 aparece en esa ejecución histórica de backend, pero no forma parte del objetivo de soporte v1. La matriz objetivo comienza en CPython 3.11.

## Requisitos de filesystem

Las plataformas difieren en longitud máxima de componentes, codificación, normalización, sensibilidad a mayúsculas, nombres reservados, caracteres no permitidos, semántica de rename/reemplazo, permisos/ACL, bloqueos y enlaces.

La implementación debe consultar límites reales cuando la plataforma lo permita y validar el nombre final antes de modificar el recurso. GNU/Linux mide el límite de componente en bytes; Windows lo mide en unidades de código UTF-16. No debe asumir que la misma métrica se aplica a todos los filesystems.

### NTFS / Windows

La validación debe cubrir, como mínimo:

- Límites de longitud de componentes medidos en unidades UTF-16 y límites de rutas, considerando las APIs y configuración de rutas largas de Windows.
- Caracteres no permitidos, nombres reservados de dispositivos y restricciones de nombres/trailing dots o spaces.
- Comparación de nombres sin distinguir mayúsculas en el comportamiento habitual de NTFS, y directorios con sensibilidad a mayúsculas habilitada cuando sea aplicable.
- Colisiones por equivalencia de nombres, no solo por igualdad textual.
- ACL, permisos, archivos abiertos/bloqueados y errores de rename/reemplazo.
- Comportamiento con antivirus u otros procesos que mantengan handles abiertos.

El perfil conservador de nombres Windows y las reglas de validación antes de restaurar plaintext se definen en [Cifrado de nombres](filename-encryption.md). No se debe asumir que una ruta válida en GNU/Linux es representable en Windows.

### ext4 / GNU/Linux

La validación debe cubrir, como mínimo:

- Límite de bytes UTF-8 por componente del filesystem y límite total de ruta impuesto por el sistema.
- Nombres como secuencias de bytes y la conversión estricta UTF-8 exigida por el contrato de fscryptography.
- Sensibilidad a mayúsculas y comportamiento de directorios con casefold cuando esté habilitado.
- Permisos, ownership, ACL cuando estén presentes, enlaces simbólicos, hard links y archivos abiertos.
- Rename dentro del mismo filesystem, colisiones y errores de I/O.

No se debe asumir que todos los nombres existentes en ext4 son UTF-8 válido.

## Contrato de rutas y tipos de recurso

La API acepta rutas de archivos y directorios, pero el soporte de tipos de entrada debe ser explícito:

- Aceptar `str` y `os.PathLike[str]`; rechazar explícitamente `PathLike[bytes]` para mantener un contrato Unicode coherente.
- No seguir enlaces simbólicos ni aceptar junctions/reparse points de Windows como recursos fuente.
- Rechazar tipos de recurso no admitidos antes de iniciar una transformación.
- No permitir que una validación de ruta obsoleta se trate como garantía frente a cambios concurrentes externos.
- No recorrer directorios ni cifrar sus contenidos: el alcance de la librería se limita al recurso indicado y, para directorios, a su propio nombre.

## Atomicidad y durabilidad

Un rename dentro del mismo filesystem suele ser una operación atómica de namespace, pero reemplazo, persistencia y durabilidad dependen de la plataforma y del filesystem.

- Los temporales deben residir en el mismo filesystem que el destino cuando se dependa de rename atómico.
- No sobrescribir destinos existentes por defecto.
- No publicar plaintext descifrado hasta autenticar el flujo completo, incluido su cierre/trailer.
- Ante errores controlables, preservar el original y limpiar temporales cuando sea seguro.
- Evaluar flush/fsync y sincronización del directorio según las capacidades de cada plataforma.
- No prometer atomicidad transaccional de varias modificaciones (por ejemplo, contenido y nombre) sin un mecanismo explícito de recuperación.
- Para cambios de nombre, usar publicación que falle si el destino existe; una comprobación previa de existencia no es suficiente frente a carreras externas.

La validación debe registrar el estado observable del origen, destino y temporales después de cada fallo inducido. Las garantías y límites generales se documentan en [Operaciones atómicas](atomic-operations.md).

## Plan mínimo de validación antes de declarar soporte

Cada combinación objetivo de sistema operativo, Python y filesystem debe cubrir:

1. Archivos vacíos, pequeños y grandes; memoria acotada y procesamiento secuencial.
2. Round-trip de cifrado/descifrado de archivos, directorios y nombres.
3. Nombres ASCII, Unicode, UTF-8 multibyte, nombres cercanos a los límites y nombres no representables.
4. Nombres reservados, colisiones por mayúsculas/minúsculas y equivalencias propias del filesystem.
5. Nombre ya cifrado, marcador malformado, ciphertext truncado y alterado.
6. Destino existente y carrera de creación del destino.
7. Permisos insuficientes, archivo abierto/bloqueado y errores de I/O.
8. Enlaces simbólicos, hard links y tipos de recurso no admitidos.
9. Fallos inducidos durante escritura temporal, cierre/autenticación, publicación, rename y limpieza.
10. Verificación de que el original permanece intacto ante errores y que no se publica plaintext parcial.
11. Residuos temporales tras terminación abrupta; comprobar el estado observable y documentar que no existe rollback ni recuperación automática.
12. Límites de ruta y componente reales del filesystem probado.

Los resultados de `real-filesystem-integration.yml` registran OS/build, arquitectura, versión exacta de Python, versiones de fscryptography/Tink/argon2-cffi/cryptography/pytest y filesystem con opciones relevantes de montaje. El runner Windows de GitHub es evidencia de comportamiento NTFS en ese entorno, no una prueba equivalente a Windows 11 cliente. Un resultado de una combinación no se extrapola a otra.

## Dependencias y empaquetado

Las versiones mínimas y máximas de Tink, argon2-cffi y cryptography están declaradas en `pyproject.toml`. La matriz normal instala las versiones más recientes que satisfacen esos rangos. El workflow [dependency-compatibility.yml](../.github/workflows/dependency-compatibility.yml) instala las versiones mínimas directas en Python 3.11 sobre Ubuntu 22.04 y Windows y ejecuta las suites de unidad, filesystem real y backends criptográficos. La compatibilidad de mínimos y máximos debe revisarse al actualizar esos rangos.

Antes de publicar soporte v1 se debe:

- Declarar explícitamente las versiones de Python soportadas en los metadatos del paquete.
- Ejecutar CI de backend en Windows y GNU/Linux para cada versión soportada.
- Ejecutar pruebas de filesystem sobre NTFS y ext4 en runners representativos.
- Verificar instalación limpia del paquete y resolución de dependencias.
- Documentar las combinaciones que hayan pasado la suite completa.

## Estado

- [x] Definir una matriz objetivo inicial: Windows 11 y Ubuntu 22.04/24.04 LTS, x86-64, CPython 3.11–3.13, NTFS/ext4.
- [x] Separar evidencia de backend criptográfico de validación integral de filesystem.
- [x] Definir contrato de nombres reservados Windows, UTF-8 estricto y semántica de equivalencia/casefold por filesystem.
- [x] Ejecutar CI de backend criptográfico en Windows y GNU/Linux para CPython 3.11–3.13; la matriz documentada terminó correctamente. Esta evidencia no sustituye la integración real de filesystem.
- [x] Ejecutar pruebas integrales de filesystem sobre ext4 y NTFS en runners representativos y registrar el tipo real del volumen: Ubuntu 22.04/24.04 y Windows Server 2025.
- [x] Medir nombres GNU/Linux en bytes UTF-8 y nombres Windows en unidades UTF-16; probar round-trip Unicode en la matriz de filesystem.
- [x] Definir el contrato `str`/`os.PathLike[str]` y rechazar `PathLike[bytes]`.
- [x] Añadir round-trip de filesystem con rutas largas, incluida una ruta Windows superior a MAX_PATH cuando el runner la soporta.
- [ ] Ejecutar la matriz integral de filesystem específicamente en Windows 11 cliente; Windows Server 2025 no sustituye esa validación. Procedimiento reproducible: [Validación manual en Windows 11](windows-11-validation.md).
- [x] Declarar rangos runtime de dependencias y metadatos de empaquetado en `pyproject.toml`; la validación CI de versiones mínimas está cubierta. La validación de límites superiores y de futuras actualizaciones debe repetirse al modificar los rangos.
- [ ] Declarar soporte únicamente después de que todas las pruebas requeridas pasen.


## Evidencia de filesystem observada en CI

La ejecución del workflow de integración con matriz explícita (GitHub Actions, run 33) completó **9/9 jobs**: Ubuntu 22.04, Ubuntu 24.04 y Windows, cada uno con CPython 3.11, 3.12 y 3.13.

Los reportes de entorno identificaron:

| Runner | SO/build observado | Filesystem del workspace |
|---|---|---|
| `ubuntu-22.04` | Ubuntu 22.04.5 LTS, x86-64 | ext4 |
| `ubuntu-24.04` | Ubuntu 24.04.5 LTS, x86-64 | ext4 |
| `windows-latest` | Microsoft Windows Server 2025 Datacenter, build 26100, 64-bit | NTFS, unidad de asignación de 4096 bytes |

El runner Windows **no es Windows 11 cliente**. Por tanto, estos resultados prueban el comportamiento de la implementación sobre NTFS en Windows Server 2025; no sustituyen una validación específica sobre Windows 11.

Los logs registran además kernel, versión exacta de Python, dependencias instaladas y opciones de montaje. En los runners Ubuntu observados, ext4 se montó con opciones que incluyen `nobarrier` y `data=writeback`. Por ello, estos resultados son pruebas de integración filesystem en el entorno CI, no ensayos de pérdida de energía ni evidencia de durabilidad física del dispositivo.

La matriz demuestra ejecución sobre ext4 y NTFS en esos runners y versiones. No permite extrapolar a todas las configuraciones de montaje, dispositivos, builds de Windows o instalaciones locales.
