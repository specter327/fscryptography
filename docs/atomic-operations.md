# Operaciones atómicas y recuperación

## Objetivo

Un fallo no debe destruir el original ni publicar contenido parcial como resultado válido. Se utilizarán temporales y una fase de publicación.

## Cifrado de archivo

1. Validar origen y destino.
2. Crear temporal exclusivo en el mismo directorio/filesystem.
3. Escribir la cabecera del formato y procesar el contenido secuencialmente hacia el temporal.
4. Finalizar el cifrador y completar el flujo autenticado.
5. Cerrar y sincronizar cuando se requiera durabilidad.
6. Preparar y validar el nombre destino.
7. Publicar el resultado mediante una operación que falle si el destino ya existe.
8. Retirar el original solo después de confirmar la publicación.
9. Sincronizar directorio cuando aplique.

## Descifrado

El plaintext se escribe en temporal privado. No se publica en la ruta definitiva hasta autenticar todos los segmentos y el cierre del flujo, validar los metadatos y validar el nombre de destino. Ante fallo de autenticación, eliminar temporal y preservar ciphertext original.

## Niveles de garantía

- **Atomicidad de publicación individual:** el destino no aparece parcialmente escrito.
- **No sobrescritura:** la publicación debe fallar de forma atómica si el destino ya existe, incluyendo colisiones según la semántica real del filesystem.
- **Rollback ante errores controlables:** restaurar estado inicial mientras el proceso puede ejecutar recuperación.
- **Recuperación tras interrupción abrupta:** requiere journal/protocolo persistente; no la proporciona un simple temporal.
- **Durabilidad:** puede requerir flush, fsync del archivo y sincronización de directorio; depende de SO y filesystem.

os.replace() puede reemplazar un destino existente y, por tanto, no satisface por sí solo el contrato de no sobrescritura. Una comprobación previa de existencia seguida de rename tampoco elimina TOCTOU. La implementación debe utilizar una primitiva de publicación no-replace apropiada para cada plataforma/filesystem objetivo; si no puede garantizarla, debe fallar de forma segura. La selección y validación de esas primitivas sigue pendiente.

La atomicidad de una publicación individual no hace indivisible la secuencia completa de publicación del contenido, cambio del nombre y retirada del origen.

## Directorios

Renombrar un directorio dentro del mismo filesystem suele ser atómico como operación de namespace, pero la operación concreta debe preservar la política de no sobrescritura. No se modifica el contenido del directorio.

## Destinos y temporales

No sobrescribir destinos existentes por defecto. Crear temporales exclusivos y con permisos restrictivos, especialmente para plaintext. Limpiar temporales en errores controlables y definir política para huérfanos.

## Pendiente

Protocolo transaccional de cambios conjuntos, recuperación de temporales huérfanos, permisos/propietario/timestamps, enlaces, concurrencia y garantías específicas por plataforma.
