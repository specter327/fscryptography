# Diseño criptográfico

## Objetivos

Confidencialidad e integridad autenticada del contenido y nombres. No se implementarán primitivas ni protocolos criptográficos propios.

## Contenido

Decisión de diseño: AES-256-GCM mediante Streaming AEAD para archivos grandes. El procesamiento será secuencial y segmentado para mantener memoria acotada. El esquema debe detectar alteración, reordenamiento, truncamiento y flujos incompletos conforme a las garantías del backend.

Tamaño de segmento objetivo predeterminado: **1 MiB**. Solo se expondrán tamaños configurables que el backend admita realmente. El tamaño interno puede incluir overhead y no equivaler exactamente a 1 MiB de plaintext.

Google Tink es el backend seleccionado. La plantilla Python `AES256_GCM_HKDF_1MB` se genera y recupera mediante la API Protobuf de keysets de Tink en la implementación actual. Las pruebas automatizadas validan round-trip y rechazo de alteración/truncamiento en los entornos CI ejecutados. La compatibilidad con sistemas operativos y filesystems objetivo y la integración sobre rutas reales siguen pendientes. No se cambiará silenciosamente a AES-CTR-HMAC.

La estructura propuesta del archivo se documenta en [Formato de archivos](file-format.md): cabecera mínima autenticada como AAD seguida directamente por el flujo Tink. El layout y la política de extensión aún no están cerrados para implementación.

## Nombres

El perfil AEAD de nombres es Tink `AES256_GCM`, mediante la interfaz convencional `Aead` y un keyset independiente del destinado al contenido. El codec usa la representación `~1` + Base64URL sin padding, AAD constante `fscryptography:filename:v1` y validación estricta de nombres. El límite derivado es 156 bytes UTF-8 cuando el límite del componente es 255 bytes. La integración con MasterKey está implementada y probada a nivel unitario; las operaciones reales de rename y publicación sin sobrescritura siguen pendientes. Véase [Cifrado de nombres](filename-encryption.md).

## Separación de claves

El contenedor MasterKey contiene keysets independientes para contenido y nombres. Los keysets se generan independientemente mediante el backend; no se reutiliza directamente una misma clave AEAD para distintos propósitos ni se diseña una KDF propia para separarlos.

## Nonces y AAD

La generación y unicidad de nonces se delega al backend. Todo metadato que influya en interpretación o descifrado debe autenticarse como AAD o quedar dentro del formato autenticado. Para archivos, la cabecera completa propuesta se utilizará como AAD de Streaming AEAD. Para nombres, el codec utiliza el AAD constante versionado aprobado.

## KDF y protección del contenedor

Argon2id es la KDF seleccionada para proteger el contenedor de claves cuando el consumidor proporciona una contraseña. La derivación utiliza un salt aleatorio y parámetros almacenados en el propio contenedor. Argon2id produce una clave de envoltura de 256 bits; esta clave protege mediante AEAD los keysets serializados.

La implementación utiliza la API low-level de `argon2-cffi` para derivación binaria de longitud fija mediante Argon2id y `cryptography` AES-GCM para el payload acotado del contenedor. La integración productiva del contenedor MasterKey y su validación automatizada están implementadas. Los resultados CI no sustituyen una auditoría criptográfica ni validan por sí mismos la matriz completa de sistemas operativos y filesystems.

La contraseña es necesaria al inicializar Crypto con un contenedor protegido. La contraseña no se almacena. `Crypto.generate(password=...)` es alias de `Crypto.derive(text=...)`. `Crypto.generate()` sin contraseña genera un contenedor aleatorio no protegido por contraseña.

Perfil Argon2id aprobado para MasterKey v1: versión 19, memoria 65.536 KiB, 3 iteraciones, paralelismo 1, salt de 16 bytes y salida de 32 bytes. El parser rechaza cualquier parámetro distinto antes de ejecutar la KDF. Los límites de entrada y contraseña se detallan en [la política Argon2id](argon2id-policy.md).

La criptografía asimétrica para envolver claves queda fuera de la primera versión.
