# fscryptography

**fscryptography** (*filesystem-cryptography*) es una librería Python para cifrar y descifrar archivos y nombres de archivos y directorios de un sistema de archivos.

Proporciona una interfaz de alto nivel basada en rutas, con procesamiento autenticado y segmentado de archivos. Su diseño es autónomo: no depende de herramientas de exploración de recursos ni de aplicaciones concretas.

> **Estado del proyecto:** implementación inicial en curso. Están implementados el contenedor MasterKey v1, el codec de nombres, la cabecera binaria de archivo v1.0 y las operaciones `Manager.file` / `Manager.dir` sobre rutas reales. Las operaciones de contenido usan Tink Streaming AEAD y temporales privados; la publicación no-replace usa `renameat2(RENAME_NOREPLACE)` en GNU/Linux y `os.rename` en Windows. En GNU/Linux también se sincroniza el directorio padre después de publicar y retirar recursos. El protocolo de journal persistente ya está especificado, pero todavía no está implementado.

## Alcance

- Cifrado y descifrado del contenido de archivos.
- Cifrado y descifrado de nombres de archivos y directorios.
- Procesamiento segmentado interno para archivos grandes.
- Metadatos autocontenidos para recuperar los recursos cifrados.

Las operaciones sobre directorios transforman únicamente su nombre; no recorren ni cifran su contenido. La librería no ofrece una API pública de cifrado de bytes o streams, exploración recursiva ni operaciones por lotes.

## Diseño

El diseño criptográfico utiliza Google Tink como backend para Streaming AEAD (`AES256_GCM_HKDF_1MB`) y AEAD convencional de nombres (`AES256_GCM`). La integración productiva genera, serializa, protege, abre y recupera keysets Tink independientes para contenido y nombres. El contenedor MasterKey protegido utiliza Argon2id y AES-256-GCM. Las pruebas automatizadas en CI validan las composiciones y los rechazos implementados; no equivalen a una auditoría criptográfica ni a validación multiplataforma.

El formato binario de archivo v1.0 está definido e implementado: la cabecera completa se autentica como AAD y almacena las extensiones original y de salida cuando el nombre permanece visible. `new_extension=None` selecciona `.fscrypt`, `""` elimina el sufijo visible y un valor como `.locked` establece uno personalizado. Con `encrypt_name=True` se cifra el nombre completo.

## Independencia

fscryptography opera sobre rutas y no depende de fsresource-tree. Puede utilizarse junto con librerías externas de exploración y orquestación, pero esa integración pertenece a la aplicación consumidora.

## Documentación

La API pública expone `fscryptography.generate()` y `fscryptography.Manager(key=...)`, con operaciones `manager.file.encrypt/decrypt()` y `manager.dir.encrypt/decrypt()`. La [documentación técnica](docs/index.md) contiene el alcance detallado, arquitectura, diseño criptográfico, gestión de claves, formatos, operaciones atómicas, protocolo de recuperación, API, errores, modelo de seguridad y compatibilidad.

## Estado de desarrollo

El trabajo se realizará en este orden:

1. Ampliar vectores golden, pruebas negativas y mutación de formatos.
2. Validar el comportamiento en Windows/NTFS y GNU/Linux/ext4 reales.
3. Integrar el journal persistente y la inspección explícita de operaciones interrumpidas; después diseñar resolución segura.
4. Completar durabilidad multiplataforma y pruebas de concurrencia.
5. Consolidar la documentación, distribución y publicación en PyPI.

No debe interpretarse la especificación como evidencia de que las funciones ya están implementadas.
