# Arquitectura

## Principios

La API pública, las operaciones de filesystem, el formato y el backend criptográfico mantienen responsabilidades separadas. La arquitectura interna no debe filtrar objetos específicos del backend a la API pública.

## Componentes lógicos

- Manager: inicialización, ciclo de vida, almacenamiento binario de la clave y contexto reutilizable de operaciones.
- File operations: cifrado y descifrado del contenido.
- Directory operations: transformación del nombre de directorio.
- Name codec: codificación y validación de nombres cifrados.
- Key management: generación, derivación, parsing y separación de claves.
- Format: cabeceras, metadatos y versionado.
- Filesystem operations: rutas, temporales, publicación no-replace, sincronización y manejo de fallos.
- Cryptographic backend: integración interna de Tink, Argon2id y AES-GCM de envoltura.
- Transaction state: estado transaccional exclusivamente en memoria y temporales hermanos efímeros para resultados y retirada segura del origen.

Esta división define responsabilidades, no obliga a crear un archivo por componente.

## Dependencias

La biblioteca estándar proporciona I/O, rutas y operaciones de sistema. Google Tink proporciona las primitivas AEAD y Streaming AEAD. Argon2id se integra mediante argon2-cffi y AES-GCM de envoltura mediante cryptography.

La primera versión utiliza un único backend criptográfico; no se diseña una arquitectura de backends intercambiables.

## Estado de componentes

- **Implementado:** validación y codec de nombres Tink; generación/apertura de MasterKey; recuperación de keysets; API `generate()`/`Manager`; cambio y exportación de clave; formato binario de archivo v1.0; cifrado/descifrado de archivos con Tink Streaming AEAD; cifrado/descifrado de nombres de archivos y directorios; temporales privados; publicación no-replace; sincronización del archivo temporal y del directorio padre en GNU/Linux.
- **Implementado:** estado transaccional en memoria, temporales hermanos exclusivos, publicación no-replace y retirada del origen mediante staging con verificación de identidad.
- **Validado en CI:** escenarios de integración sobre ext4 en Ubuntu 22.04.5/24.04.5 y NTFS en Windows Server 2025, con Python 3.11–3.13. La matriz no representa todos los filesystems, configuraciones de montaje ni Windows 11 cliente.
- **Pendiente de ampliación:** validación en más versiones y configuraciones de Windows/filesystems, durabilidad del namespace en Windows, escenarios adversariales adicionales y política de preservación de metadatos.

## Flujo de cifrado implementado

Validar origen y destino; crear temporal exclusivo en el mismo directorio; escribir la cabecera y cifrar secuencialmente; finalizar el flujo autenticado; sincronizar el archivo temporal; publicar sin reemplazar destinos existentes; sincronizar el directorio padre en GNU/Linux; revalidar y retirar el origen; volver a sincronizar el directorio padre en GNU/Linux. Si falla la primera sincronización del directorio, se conservan origen y destino.

## Flujo de descifrado implementado

Reconocer y validar la cabecera; preparar temporal privado; descifrar y autenticar todos los segmentos; validar el cierre; sincronizar el archivo temporal; validar el nombre original; publicar únicamente tras autenticación completa; sincronizar el directorio padre en GNU/Linux; retirar el ciphertext y sincronizar nuevamente el directorio padre.

## Estado transaccional y límites

El estado de cada operación vive exclusivamente en memoria y desaparece al terminar el proceso. No hay journal, directorio de transacción persistente, API de inspección ni recuperación posterior. Los archivos de resultado se escriben mediante temporales hermanos para conservar el procesamiento streaming; la retirada del origen usa un nombre hermano aleatorio y comprueba la identidad después del rename. Una interrupción abrupta puede dejar temporales de resultado o de origen. La librería no puede clasificarlos ni limpiarlos automáticamente. Si el destino se publicó pero la retirada del origen falló, ambos recursos pueden permanecer y se informa AtomicOperationError.

No implementar primitivas propias. No publicar plaintext parcial. No sobrescribir destinos por defecto. No asumir que múltiples renames forman una transacción. No prometer borrado seguro absoluto de secretos en memoria Python.
