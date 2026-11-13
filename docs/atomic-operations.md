# Operaciones atómicas y recuperación

## Objetivo
Un fallo no debe destruir el original ni publicar contenido parcial como resultado válido. Se utilizarán temporales y una fase de publicación.

## Cifrado de archivo
1. Validar origen y destino.
2. Crear temporal exclusivo en el mismo directorio/filesystem.
3. Procesar contenido hacia el temporal.
4. Finalizar el cifrador y completar el formato.
5. Cerrar y sincronizar cuando se requiera durabilidad.
6. Preparar y validar nombre destino.
7. Publicar el resultado.
8. Retirar el original solo después de confirmar publicación.
9. Sincronizar directorio cuando aplique.

## Descifrado
El plaintext se escribe en temporal privado. No se publica en la ruta definitiva hasta autenticar todos los segmentos y el cierre. Ante fallo de autenticación, eliminar temporal y preservar ciphertext original.

## Niveles de garantía
- Atomicidad de publicación individual: el destino no aparece parcialmente escrito.
- Rollback ante errores controlables: restaurar estado inicial mientras el proceso puede ejecutar recuperación.
- Recuperación tras interrupción abrupta: requiere journal/protocolo persistente; no la proporciona un simple temporal.
- Durabilidad: puede requerir flush, fsync del archivo y sincronización de directorio; depende de SO y filesystem.

os.replace() puede publicar atómicamente un archivo dentro del mismo filesystem, pero no hace indivisible una secuencia de cambios de contenido y nombre ni garantiza por sí solo durabilidad ante pérdida eléctrica.

## Directorios
Renombrar un directorio dentro del mismo filesystem suele ser atómico como operación de namespace. No se modifica su contenido.

## Destinos y temporales
No sobrescribir destinos existentes por defecto. Crear temporales exclusivos y con permisos restrictivos, especialmente para plaintext. Limpiar temporales en errores controlables y definir política para huérfanos.

## Pendiente
Protocolo transaccional de cambios conjuntos, recuperación de temporales huérfanos, permisos/propietario/timestamps, enlaces, concurrencia y garantías específicas por plataforma.
