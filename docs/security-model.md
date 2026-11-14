# Modelo de seguridad

## Activos

- Confidencialidad del contenido de archivos.
- Integridad y autenticidad del ciphertext y de los metadatos autenticados.
- Confidencialidad e integridad de los nombres cifrados.
- Material criptográfico contenido en MasterKey y primitivas abiertas.
- Estado de origen/destino durante operaciones interrumpidas.

## Adversario y límites de confianza

El diseño busca proteger frente a quien obtiene los archivos y nombres cifrados sin sus claves, y detectar alteraciones del ciphertext y de los metadatos autenticados.

No se asume que el host esté libre de malware, depuradores privilegiados, captura de memoria, compromiso del proceso, administrador/root, kernel malicioso o procesos hostiles con permisos equivalentes al usuario que ejecuta la librería. Los temporales hermanos no aíslan frente a procesos del mismo usuario.

## Garantías implementadas y validadas

La implementación utiliza primitivas de bibliotecas criptográficas establecidas, no algoritmos propios:

- Tink Streaming AEAD con AES256_GCM_HKDF_1MB para contenido.
- Tink AEAD AES256_GCM con keyset independiente para nombres.
- Argon2id v19 y AES-256-GCM para proteger opcionalmente el contenedor MasterKey.
- Cabeceras versionadas y autenticadas como AAD para contenido.
- Validación estricta de framing, longitudes, flags y versiones del contenedor.
- El plaintext no se publica como resultado definitivo hasta completar el flujo autenticado.
- Publicación sin reemplazo, temporales hermanos efímeros, comprobaciones de identidad del origen y estado transaccional en memoria.
- Detección de cambios concurrentes del origen y ciphertext, colisiones de destino, hard links múltiples, symlinks y reparse points Windows.
- Contextos de claves independientes para nombres y contenido; cada operación conserva una instantánea coherente durante la rotación.

La matriz CI ha ejecutado pruebas de integración sobre Ubuntu 22.04.5/24.04.5 con ext4 y Windows Server 2025 Datacenter con NTFS, Python 3.11–3.13. Esto valida esos entornos concretos, no todas las configuraciones de filesystem ni Windows 11 cliente.

## Límites y exposición de metadatos

No se ocultan:

- Tamaño aproximado y overhead del contenido.
- Cantidad de recursos y jerarquía del árbol.
- Timestamps, permisos, propietarios, ACL y patrones de acceso.
- Longitudes aproximadas de nombres, según el perfil y la representación.

Las operaciones de archivo crean objetos nuevos y no preservan automáticamente permisos, propietario/grupo, ACL, xattrs, alternate data streams, atributos especiales ni timestamps del origen. En GNU/Linux los archivos temporales de resultado usan modo restrictivo 0600. No se crean directorios transaccionales dedicados. En Windows los objetos nuevos reciben ACL heredadas del padre. Las operaciones de directorio renombran el mismo objeto y no recorren sus hijos.

La librería no protege contra eliminación, pérdida o corrupción irrecuperable del ciphertext. Perder la MasterKey o la contraseña necesaria implica pérdida práctica de acceso.

## Riesgos residuales

- Reutilización de nonce GCM: la generación se delega a Tink/cryptography; no se diseña un generador propio.
- Ataques sobre un host comprometido o procesos con permisos equivalentes.
- Cambios hostiles en directorios padre, condiciones TOCTOU específicas de cada sistema operativo y diferencias de API entre plataformas.
- Durabilidad ante pérdida de energía, fallo de kernel, caché del dispositivo o hardware defectuoso.
- Filtración de secretos en memoria, volcados, swap, depuradores o logs del consumidor.
- Ataques de denegación de servicio mediante recursos enormes o filesystem saturado.
- Manipulación, sustitución o retención maliciosa de temporales por actores con permisos suficientes.

## Contraseñas y memoria

El perfil protegido MasterKey v1 utiliza Argon2id versión 19, memoria 65.536 KiB, 3 iteraciones, paralelismo 1, salt de 16 bytes y salida de 32 bytes. El parser rechaza perfiles no admitidos antes de ejecutar la KDF. Estos parámetros son un perfil de interoperabilidad del formato, no una recomendación universal para todo dispositivo.

Python no garantiza borrado seguro de secretos. close() invalida el gestor y libera referencias; no revoca primitivas ya capturadas por operaciones en curso ni garantiza sobrescritura física de memoria.

## Integridad y estado transaccional

El estado transaccional solo existe en memoria. No hay journal persistente, inspección posterior ni recuperación automática. La terminación abrupta puede dejar temporales de resultado o de staging del origen en el directorio padre; la librería no los identifica ni los elimina en una ejecución posterior. El consumidor debe evaluar manualmente esos residuos, verificando identidad y contenido antes de cualquier eliminación o restauración.

Con `encrypt_name=True`, dos operaciones concurrentes sobre el mismo origen pueden generar nombres de destino aleatorios distintos y publicar ambos ciphertexts antes de competir por la retirada del origen. Una operación puede completar la retirada y la otra fallar dejando un ciphertext duplicado publicado. Este resultado parcial es intencionalmente visible y no se limpia automáticamente; el consumidor debe decidir cuál conservar.

Los tests de ejecución normal no equivalen a pruebas de pérdida de energía ni a garantías de durabilidad física.

## No objetivos

No es un filesystem cifrado transparente, gestor de secretos, sistema de intercambio de claves, herramienta de anonimización, protección de endpoints comprometidos ni solución para ocultar metadatos.

## Auditoría

No se ha completado una auditoría criptográfica independiente. Las pruebas automatizadas y los resultados CI no equivalen a una auditoría ni certifican ausencia de vulnerabilidades.


## Pruebas property-based

Los parsers de cabecera de archivo v1.0 y framing/Base64 de MasterKey disponen de pruebas property-based acotadas con Hypothesis. Estas pruebas buscan excepciones no clasificadas y verifican invariantes de round-trip para datos válidos. No sustituyen fuzzing de larga duración, sanitizadores, pruebas de hardware ni auditoría independiente.


El procedimiento y los criterios de campaña prolongada están definidos en [Plan de fuzzing y pruebas prolongadas](fuzzing-plan.md). La documentación del plan no implica que la campaña ya se haya ejecutado.