# Compatibilidad de plataformas

## Objetivo
La intención inicial es soportar Windows y GNU/Linux. macOS podrá incorporarse tras validar backend y operaciones de filesystem. La matriz exacta de versiones de Python y sistemas operativos se fijará antes de PyPI.

## Variaciones de filesystem
Las plataformas difieren en longitud máxima de componentes, codificación y normalización, sensibilidad a mayúsculas, nombres reservados, caracteres no permitidos, rename/reemplazo, permisos/ACL, bloqueos y enlaces.

La librería debe detectar y comunicar restricciones, no asumir semántica uniforme.

## Rutas
La API conceptual utiliza str. El soporte de os.PathLike y pathlib.Path debe definirse en el contrato. No seguir enlaces simbólicos implícitamente ni permitir que cambios concurrentes invaliden silenciosamente validaciones de ruta.

## Atomicidad
Un rename dentro del mismo filesystem suele ser atómico como operación de namespace, pero reemplazo y durabilidad dependen de plataforma. Los temporales deben residir en el mismo filesystem cuando se dependa de rename atómico. fsync y sincronización de directorios varían.

## Matriz de validación
Antes de declarar soporte se probarán archivos vacíos, pequeños y grandes; nombres Unicode y límites; colisiones; destinos existentes; permisos; archivos bloqueados; fallos de I/O/publicación; ciphertext truncado/corrupto; limpieza de temporales; enlaces y tipos no admitidos.

La matriz exacta de versiones y filesystems queda pendiente.
