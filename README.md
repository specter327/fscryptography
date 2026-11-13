# fscryptography

**fscryptography** (*filesystem-cryptography*) es una librería Python para cifrar y descifrar archivos y nombres de archivos y directorios de un sistema de archivos.

Proporciona una interfaz de alto nivel basada en rutas, con procesamiento autenticado y segmentado de archivos. Su diseño es autónomo: no depende de herramientas de exploración de recursos ni de aplicaciones concretas.

> **Estado del proyecto:** especificación en consolidación. La implementación todavía no está disponible.

## Alcance

- Cifrado y descifrado del contenido de archivos.
- Cifrado y descifrado de nombres de archivos y directorios.
- Procesamiento segmentado interno para archivos grandes.
- Metadatos autocontenidos para recuperar los recursos cifrados.

Las operaciones sobre directorios transforman únicamente su nombre; no recorren ni cifran su contenido. La librería no ofrece una API pública de cifrado de bytes o streams, exploración recursiva ni operaciones por lotes.

## Diseño

El diseño criptográfico contempla AES-256-GCM y procesamiento autenticado segmentado, con un tamaño objetivo predeterminado de 1 MiB. Google Tink es el backend candidato para Streaming AEAD y Argon2id es la KDF seleccionada conceptualmente para derivación desde contraseñas. Estas decisiones requieren validación técnica antes de considerarse cerradas.

## Independencia

fscryptography opera sobre rutas y no depende de fsresource-tree. Puede utilizarse junto con librerías externas de exploración y orquestación, pero esa integración pertenece a la aplicación consumidora.

## Documentación

La [documentación técnica](docs/index.md) contiene el alcance detallado, arquitectura, diseño criptográfico, gestión de claves, formatos, operaciones atómicas, API, errores, modelo de seguridad y compatibilidad.

## Estado de desarrollo

El trabajo se realizará en este orden:

1. Completar y validar la especificación en `docs/`.
2. Implementar el paquete en `src/fscryptography/`.
3. Construir la suite de pruebas en `tests/`.
4. Preparar la distribución y publicación en PyPI.

No debe interpretarse la especificación como evidencia de que las funciones ya están implementadas.
