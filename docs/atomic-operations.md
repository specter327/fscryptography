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

La identidad del origen se valida antes y después del procesamiento. Para archivos se comparan identidad, tamaño, mtime y ctime observables del descriptor. Esto detecta modificaciones ordinarias, pero no constituye una instantánea criptográfica ni protege frente a un escritor hostil que pueda manipular metadatos o competir dentro de la granularidad temporal del filesystem.

La publicación no-replace impide sobrescribir destinos existentes. Las operaciones concurrentes sobre un mismo origen compiten por el nombre y la identidad del recurso; solo una debe poder completar la retirada segura. Los temporales usan nombres aleatorios y creación exclusiva, pero no se consideran un mecanismo de aislamiento frente a procesos hostiles con permisos equivalentes.

## Límites y pruebas

La suite unitaria cubre round-trip, autenticación, colisiones de destino, modificación del origen durante streaming, sustitución de entradas durante la retirada, publicación no-replace y concurrencia. Las pruebas no equivalen a una simulación de pérdida de energía ni a una auditoría de filesystem.

Pendiente de validación ampliada:

- Fallos de kernel, caché de dispositivo y pérdida física de energía.
- Durabilidad de entradas de directorio en Windows.
- Comportamiento en todos los filesystems y configuraciones de montaje objetivo.
- Ataques de procesos hostiles con permisos equivalentes.
- Política de metadatos de archivos y directorios.
