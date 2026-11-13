# ADR 0001: Diseño inicial

- Estado: aceptado como línea de diseño; detalles sujetos a validación.
- Fecha: 2026-11-12

## Contexto
Se requiere una librería Python autónoma para cifrar y descifrar contenido de archivos y nombres del filesystem mediante rutas, sin asumir exploración ni administración de recursos.

## Decisiones
1. Nombre del paquete: fscryptography.
2. API centrada en rutas del filesystem.
3. Operaciones de directorio transforman solo el nombre.
4. No hay API pública de cifrado de bytes/streams.
5. AES-256-GCM es la familia elegida para cifrado autenticado.
6. Procesamiento segmentado; tamaño objetivo predeterminado de 1 MiB.
7. Google Tink es candidato principal para Streaming AEAD.
8. Argon2id es la KDF seleccionada conceptualmente para contraseñas.
9. Los nombres usan clave separada del contenido y cifrado autenticado.
10. Descifrado autocontenido: recurso cifrado más clave original.
11. Temporales y publicación controlada; no sobrescribir por defecto.
12. No existe dependencia de fsresource-tree.
13. Asimetría para envolver/intercambiar claves queda fuera de v1.

## Consecuencias
Antes de implementar deben cerrarse formato autocontenido, separación de claves, contrato de errores, reglas de nombres y recuperación. La atomicidad debe describirse por niveles; os.replace() no garantiza transacción multioperación ni durabilidad universal.

## Rechazos
No implementar primitivas propias, no crear API genérica de bytes/streams, no añadir exploración recursiva ni lotes, no acoplar a fsresource-tree y no introducir múltiples backends sin necesidad demostrada.
