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
| Sistema operativo | Windows 11 x86-64 | Objetivo; falta validación integral |
| Sistema operativo | Ubuntu 22.04 LTS x86-64 | Objetivo; falta validación integral |
| Sistema operativo | Ubuntu 24.04 LTS x86-64 | Objetivo; falta validación integral |
| Python | CPython 3.11 | Objetivo; backend criptográfico validado en Ubuntu |
| Python | CPython 3.12 | Objetivo; backend criptográfico validado en Ubuntu |
| Python | CPython 3.13 | Objetivo; backend criptográfico validado en Ubuntu |
| Filesystem Windows | NTFS local | Filesystem de referencia; falta validación integral |
| Filesystem GNU/Linux | ext4 local | Filesystem de referencia; falta validación integral |
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

El workflow [backend-validation.yml](../.github/workflows/backend-validation.yml) ejecutó pruebas de backend en GitHub Actions sobre Ubuntu para Python 3.10, 3.11, 3.12 y 3.13:

- Tink Streaming AEAD con `AES256_GCM_HKDF_1MB`.
- Tink AEAD convencional `AES256_GCM` para nombres.
- Protección MasterKey mediante Argon2id y AES-256-GCM.
- Vectores iniciales del formato MasterKey.

Los cuatro entornos de Python pasaron en el run documentado de CI. Esta evidencia valida las integraciones criptográficas probadas en esos entornos; **no valida** operaciones reales de filesystem, NTFS, Windows, ext4 ni atomicidad en ninguna plataforma.

Python 3.10 aparece en esa ejecución histórica de backend, pero no forma parte del objetivo de soporte v1. La matriz objetivo comienza en CPython 3.11.

## Requisitos de filesystem

Las plataformas difieren en longitud máxima de componentes, codificación, normalización, sensibilidad a mayúsculas, nombres reservados, caracteres no permitidos, semántica de rename/reemplazo, permisos/ACL, bloqueos y enlaces.

La implementación debe consultar límites reales cuando la plataforma lo permita y validar el nombre final antes de modificar el recurso. No debe asumir que el límite común de 255 bytes se aplica a todos los filesystems.

### NTFS / Windows

La validación debe cubrir, como mínimo:

- Límites de longitud de componentes y rutas, considerando las APIs y configuración de rutas largas de Windows.
- Caracteres no permitidos, nombres reservados de dispositivos y restricciones de nombres/trailing dots o spaces.
- Comparación de nombres sin distinguir mayúsculas en el comportamiento habitual de NTFS, y directorios con sensibilidad a mayúsculas habilitada cuando sea aplicable.
- Colisiones por equivalencia de nombres, no solo por igualdad textual.
- ACL, permisos, archivos abiertos/bloqueados y errores de rename/reemplazo.
- Comportamiento con antivirus u otros procesos que mantengan handles abiertos.

El perfil conservador de nombres Windows y las reglas de validación antes de restaurar plaintext se definen en [Cifrado de nombres](filename-encryption.md). No se debe asumir que una ruta válida en GNU/Linux es representable en Windows.

### ext4 / GNU/Linux

La validación debe cubrir, como mínimo:

- Límite de bytes por componente del filesystem y límite total de ruta impuesto por el sistema.
- Nombres como secuencias de bytes y la conversión estricta UTF-8 exigida por el contrato de fscryptography.
- Sensibilidad a mayúsculas y comportamiento de directorios con casefold cuando esté habilitado.
- Permisos, ownership, ACL cuando estén presentes, enlaces simbólicos, hard links y archivos abiertos.
- Rename dentro del mismo filesystem, colisiones y errores de I/O.

No se debe asumir que todos los nombres existentes en ext4 son UTF-8 válido.

## Contrato de rutas y tipos de recurso

La API acepta rutas de archivos y directorios, pero el soporte de tipos de entrada debe ser explícito:

- Definir y probar `str` y `pathlib.Path`/`os.PathLike` antes de declararlos compatibles.
- No seguir enlaces simbólicos implícitamente.
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
11. Temporales huérfanos y fallos de rollback/recuperación.
12. Límites de ruta y componente reales del filesystem probado.

Los resultados deben registrar OS/build, arquitectura, versión exacta de Python, versión de dependencias, filesystem y opciones relevantes de montaje/configuración. Un resultado de una combinación no se extrapola a otra.

## Dependencias y empaquetado

Las versiones mínimas y máximas de Tink, argon2-cffi y cryptography deben quedar fijadas en los metadatos de empaquetado y probarse en la matriz objetivo. El workflow de backend actual instala rangos de dependencias para validación; esos rangos no sustituyen una política de dependencias runtime ni prueban el empaquetado de la librería.

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
- [ ] Añadir CI de backend para Windows y todas las versiones Python objetivo.
- [ ] Ejecutar pruebas integrales de filesystem en NTFS y ext4.
- [ ] Definir el contrato de rutas `PathLike` y validar rutas largas.
- [ ] Fijar rangos runtime de dependencias y metadatos de empaquetado.
- [ ] Declarar soporte únicamente después de que todas las pruebas requeridas pasen.
