# fscryptography

**fscryptography** (*filesystem-cryptography*) es una librería Python para cifrar y descifrar archivos y nombres de archivos y directorios de un sistema de archivos.

Proporciona una interfaz de alto nivel basada en rutas, con procesamiento autenticado y segmentado de archivos. Su diseño es autónomo: no depende de herramientas de exploración de recursos ni de aplicaciones concretas.

> **Estado del proyecto:** implementación inicial en curso. Están implementados la validación y codec de nombres, la generación/apertura del contenedor MasterKey v1 con keysets Tink reales y la API pública `generate()`/`Manager` para mantener un contexto criptográfico reutilizable. Las operaciones de cifrado/descifrado de archivos y directorios sobre rutas reales todavía no están implementadas.

## Alcance

- Cifrado y descifrado del contenido de archivos.
- Cifrado y descifrado de nombres de archivos y directorios.
- Procesamiento segmentado interno para archivos grandes.
- Metadatos autocontenidos para recuperar los recursos cifrados.

Las operaciones sobre directorios transforman únicamente su nombre; no recorren ni cifran su contenido. La librería no ofrece una API pública de cifrado de bytes o streams, exploración recursiva ni operaciones por lotes.

## Diseño

El diseño criptográfico utiliza Google Tink como backend para Streaming AEAD (`AES256_GCM_HKDF_1MB`) y AEAD convencional de nombres (`AES256_GCM`). La integración productiva genera, serializa, protege, abre y recupera keysets Tink independientes para contenido y nombres. El contenedor MasterKey protegido utiliza Argon2id y AES-256-GCM. Las pruebas automatizadas en CI validan las composiciones y los rechazos implementados; no equivalen a una auditoría criptográfica ni a validación multiplataforma.

El formato de archivo está en especificación: existe una propuesta de cabecera mínima autenticada como AAD, pero la semántica de extensión y el contrato exacto de `new_extension` siguen pendientes de aprobación. No debe implementarse un formato provisional como definitivo.

## Independencia

fscryptography opera sobre rutas y no depende de fsresource-tree. Puede utilizarse junto con librerías externas de exploración y orquestación, pero esa integración pertenece a la aplicación consumidora.

## Documentación

La API pública expone fscryptography.generate() y fscryptography.Manager(key=...); las operaciones de archivos/directorios aún están pendientes. La [documentación técnica](docs/index.md) contiene el alcance detallado, arquitectura, diseño criptográfico, gestión de claves, formatos, operaciones atómicas, API, errores, modelo de seguridad y compatibilidad.

## Estado de desarrollo

El trabajo se realizará en este orden:

1. Completar y aprobar las especificaciones en `docs/`.
2. Crear vectores golden y pruebas de conformidad para los formatos.
3. Implementar el paquete en `src/fscryptography/`.
4. Validar operaciones reales y garantías específicas de filesystem.
5. Preparar la distribución y publicación en PyPI.

No debe interpretarse la especificación como evidencia de que las funciones ya están implementadas.
