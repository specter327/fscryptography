# Operaciones transaccionales y límites ante interrupciones

## Objetivo

Las operaciones evitan publicar resultados parciales, no reemplazan destinos existentes y no retiran el origen hasta que el resultado completo se ha publicado. El estado transaccional se conserva únicamente en memoria; no existe journal persistente ni recuperación posterior.

## Secuencia de archivo

Cifrado y descifrado siguen este orden:

1. Validar el origen y capturar su identidad inicial.
2. Crear un nombre temporal aleatorio y exclusivo en el directorio padre.
3. Procesar el archivo en streaming. En descifrado, autenticar el flujo completo antes de publicar.
4. Sincronizar el archivo temporal con `fsync`.
5. Publicar mediante una primitiva atómica no-replace.
6. Sincronizar el directorio padre en GNU/Linux.
7. Mover el origen a un nombre hermano aleatorio mediante rename no-replace.
8. Verificar la identidad del objeto movido. Si no coincide, intentar restaurarlo sin sobrescribir una entrada competidora.
9. Retirar el objeto verificado. En Windows, la eliminación se solicita sobre el handle cuya identidad ya fue comprobada.
10. Sincronizar el directorio padre en GNU/Linux.

El estado lógico (`prepared`, `result_ready`, `published`, `source_retained`, `source_removed`, `complete`) vive solo en el objeto transaccional en memoria. No se serializa.

## Temporales hermanos

Los resultados temporales se crean en el mismo directorio padre para conservar el procesamiento streaming y permitir publicación dentro del mismo filesystem. La retirada del origen utiliza temporalmente otro nombre hermano aleatorio, necesario para verificar el objeto después del rename antes de solicitar su eliminación.

En ejecución normal, los temporales de resultado se eliminan durante la limpieza si no fueron publicados. Un temporal de origen que contenga un objeto inesperado o cuya eliminación haya fallado puede permanecer deliberadamente para evitar borrar un recurso no verificado.

## Interrupción abrupta y ausencia de recuperación

Una terminación abrupta del proceso, un cierre forzado o una pérdida de energía puede dejar:

- Un temporal de resultado completo o incompleto.
- Un origen movido a un nombre temporal hermano durante la retirada.
- El origen y el destino publicados simultáneamente, si la interrupción ocurrió después de publicar y antes de retirar el origen.

La librería no crea journals, directorios de transacción, registros persistentes ni identificadores consultables. No ofrece `inspect_recovery()`, `RecoveryRecord`, recuperación automática, rollback ni limpieza automática en una ejecución posterior. No puede distinguir de forma fiable un temporal propio antiguo de un archivo ajeno con un nombre parecido.

El consumidor debe inspeccionar manualmente el directorio y decidir qué conservar. Antes de borrar o restaurar un elemento, debe verificar su identidad y contenido. No debe asumir que un archivo con prefijo `.fscryptography-` pertenece necesariamente a una operación interrumpida.

Por tanto, la ausencia de journal reduce la persistencia auxiliar, pero renuncia explícitamente a la recuperación post-crash. No se garantiza ausencia absoluta de residuos tras apagones.

## Publicación y no sobrescritura

En GNU/Linux se utiliza `renameat2(RENAME_NOREPLACE)`; si la primitiva no está disponible, la operación falla de forma segura. En Windows se utiliza `os.rename`, que no reemplaza un destino existente. No se usa una secuencia check-then-rename como sustituto.

## Durabilidad por plataforma

- **GNU/Linux:** el resultado se sincroniza antes de publicación y el directorio padre se sincroniza después de publicar y retirar el origen. Las garantías finales dependen del kernel, filesystem, dispositivo y opciones de montaje.
- **Windows:** el archivo temporal se sincroniza y los cambios de nombre usan `os.rename`; no se promete durabilidad del cambio de nombre ante pérdida de energía porque no se realiza un flush verificable del directorio padre.
- **Otros sistemas:** no están soportados por la implementación actual.

## Seguridad y concurrencia

En GNU/Linux, antes de publicar el resultado y antes de retirar el origen, la librería vuelve a comprobar que la ruta del directorio padre sigue identificando al descriptor anclado. Las transformaciones de nombre de directorio realizan la misma comprobación antes del rename. Si detecta que el padre fue movido, sustituido, eliminado o reemplazado por un enlace simbólico, aborta la fase aún no ejecutada. Si la sustitución ocurre después de publicar y antes de retirar el origen, conserva el origen; el resultado ya publicado permanece en el directorio anclado, que puede haber sido movido fuera de su ruta original. Estas verificaciones detectan cambios persistentes, pero no son atómicas respecto de la siguiente operación: no impiden una carrera entre la comprobación de la ruta y renameat2. Los descriptores siguen anclando las operaciones al directorio original, no a la ruta visible.

La identidad del origen se valida antes y después del streaming. Antes de retirarlo, se mueve a un nombre hermano y se vuelve a comprobar identidad, número de enlaces, tamaño y mtime; así se detectan también escrituras ordinarias ocurridas entre el final del streaming y el staging. ctime se compara durante el streaming, pero no después del rename porque el propio cambio de nombre puede actualizarlo. Estas comprobaciones no constituyen una instantánea criptográfica ni protegen frente a un escritor hostil que pueda manipular metadatos o competir dentro de la granularidad temporal del filesystem.

La retirada del origen en GNU/Linux tiene un límite distinto y relevante: después de moverlo al nombre hermano y verificar su identidad mediante `stat`, la librería ejecuta `unlink` por nombre relativo al descriptor del directorio. La comprobación y la eliminación no son atómicas. Un proceso con permisos equivalentes sobre ese directorio puede sustituir la entrada retenida entre ambas llamadas y hacer que `unlink` elimine el sustituto. El descriptor ancla el directorio, pero no condiciona la eliminación al inode previamente verificado. La secuencia detecta sustituciones anteriores a la comprobación; no protege frente a una sustitución concurrente en esa ventana. Este comportamiento queda fuera del modelo de aislamiento de la librería y no debe interpretarse como eliminación segura frente a actores hostiles con permisos equivalentes. En Windows se solicita la eliminación sobre el handle abierto y verificado, por lo que este límite específico de `unlink` por nombre no describe esa ruta.

La limpieza de un temporal de resultado compara primero `(st_dev, st_ino)` con la identidad capturada al crearlo y solo intenta eliminarlo si coincide. Esta comprobación evita eliminar reemplazos que ya existían al momento de inspeccionar la entrada, pero la comparación y `unlink()` no son una operación atómica: un proceso con permisos equivalentes sobre el directorio puede sustituir el nombre entre ambas llamadas. Por tanto, la limpieza es de mejor esfuerzo y no constituye una defensa frente a procesos hostiles que puedan modificar el mismo directorio. Este límite también aplica al uso de un descriptor del directorio (`dir_fd`): ancla la resolución al directorio, pero no hace condicional el `unlink` respecto al inode verificado.

La publicación no-replace impide sobrescribir destinos existentes. Cuando se usa un destino determinista (por ejemplo, la extensión predeterminada), las operaciones concurrentes sobre el mismo origen compiten por el mismo nombre y solo una puede publicarlo. Con `encrypt_name=True`, cada operación genera un nombre cifrado aleatorio distinto: dos operaciones concurrentes pueden publicar dos ciphertexts válidos antes de competir por retirar el origen. Solo una puede completar esa retirada; la otra puede fallar y dejar su resultado publicado como duplicado. La librería no elimina automáticamente ese segundo resultado porque ya fue publicado y no puede asumir que sea prescindible. El consumidor debe revisar los resultados antes de retirar duplicados. Los temporales usan nombres aleatorios y creación exclusiva, pero no se consideran un mecanismo de aislamiento frente a procesos hostiles con permisos equivalentes.

## Límites y pruebas

La suite unitaria cubre round-trip, autenticación, colisiones de destino, modificación del origen durante streaming, sustitución de entradas durante la retirada, publicación no-replace y concurrencia. Las pruebas no equivalen a una simulación de pérdida de energía ni a una auditoría de filesystem.

Pendiente de validación ampliada:

- Fallos de kernel, caché de dispositivo y pérdida física de energía.
- Durabilidad de entradas de directorio en Windows.
- Comportamiento en todos los filesystems y configuraciones de montaje objetivo.
- Ataques de procesos hostiles con permisos equivalentes.
- Política de metadatos de archivos y directorios.
