# Gestión de claves

## Terminología

`master_key` representa el contenedor autocontenido de material criptográfico raíz que el consumidor entrega a `Crypto`. No debe llamarse `private_key`, término asociado a criptografía asimétrica.

## API implementada

```python
from fscryptography import Crypto

# Material aleatorio
master_key = Crypto.generate()
crypto = Crypto(master_key=master_key)

# Material protegido mediante contraseña
master_key = Crypto.generate(password="passphrase")
crypto = Crypto(master_key=master_key, password="passphrase")

# Alias explícito de generación protegida
master_key = Crypto.derive(text="passphrase")
crypto = Crypto(master_key=master_key, password="passphrase")

with Crypto(master_key=master_key, password="passphrase") as crypto:
    ...
```

`Crypto.generate(password=...)` es un alias de `Crypto.derive(text=...)`. Ambos producen un contenedor de claves protegido por contraseña. La contraseña es necesaria cada vez que se inicializa `Crypto` desde ese contenedor y no se almacena en la instancia ni en el contenedor.

## Modelo de clave

La salida pública es una representación autocontenida y versionada de `MasterKey`, codificada en Base64 estándar con padding. La cadena Base64 es una codificación de transporte, no una protección criptográfica. No debe asumirse que representa directamente 32 bytes AES.

El contenedor contiene keysets independientes para las operaciones criptográficas de contenido y nombres. En el modo protegido, el payload que contiene esos keysets se cifra y autentica. `MasterKey` es opaco para el consumidor: no expone keysets, claves derivadas, nonces internos ni detalles del backend.

El contenedor de claves es distinto del formato de cada archivo o nombre cifrado. La estructura binaria v1 aprobada se especifica en [Formato de MasterKey](master-key-format.md); el perfil Argon2id y los límites de apertura se definen en [la política Argon2id](argon2id-policy.md).

## Generación aleatoria

`Crypto.generate()` crea keysets Tink independientes para contenido y nombres mediante generadores criptográficos seguros y serializa el material secreto en un contenedor versionado.

El payload del modo aleatorio no está protegido por contraseña ni cifrado por una clave de envoltura. La seguridad de este modo depende de proteger el propio valor `master_key`. La codificación Base64 no oculta ni protege el material secreto. El consumidor debe tratar el valor como una credencial secreta.

## Derivación y protección mediante contraseña

`Crypto.derive(text=...)` genera keysets criptográficos aleatorios y los protege mediante una clave de envoltura derivada de la contraseña con Argon2id y un salt aleatorio.

El contenedor protegido incluye identificadores/versiones, parámetros de KDF, salt, identificador AEAD, nonce y ciphertext autenticado. La cabecera completa se utiliza como AAD. El payload contiene los dos keysets Tink serializados en formato Protobuf binario, delimitados mediante longitudes big-endian.

El perfil Argon2id v1 utiliza versión 19, memoria 65.536 KiB, 3 iteraciones, paralelismo 1, salt de 16 bytes y salida de 32 bytes. El parser acepta exactamente ese perfil y rechaza cualquier otra combinación antes de ejecutar Argon2id. Los límites de entrada y contraseña están definidos en [la política Argon2id](argon2id-policy.md).

`Crypto(master_key=..., password=...)` deriva la clave de protección y abre el contenedor. Una contraseña incorrecta o un contenedor protegido alterado produce `AuthenticationError`; no se generan keysets nuevos silenciosamente.

La contraseña se interpreta como texto UTF-8 estricto, sin normalización Unicode implícita, no puede estar vacía y no puede exceder 1.024 bytes una vez codificada. El contenedor binario no puede exceder 131.149 bytes y su representación Base64 no puede exceder 174.868 caracteres ASCII. Los límites completos y el orden obligatorio de validación se definen en [la política Argon2id](argon2id-policy.md).

## Separación

Los keysets de contenido y nombres son independientes. El keyset de contenido produce una primitiva Tink Streaming AEAD con la plantilla `AES256_GCM_HKDF_1MB`; el keyset de nombres produce una primitiva Tink AEAD con la plantilla `AES256_GCM`. No se reutiliza directamente una misma clave AEAD para ambos propósitos.

## Estado de implementación

El módulo interno `fscryptography._master_key` implementa la generación y apertura del contenedor binario v1.0, incluidos los dos keysets Tink reales, el framing, Base64 estricto, Argon2id con el perfil productivo aprobado y AES-256-GCM con la cabecera completa como AAD. La apertura recupera las primitivas Tink de Streaming AEAD y AEAD de nombres; los keysets no se exponen como parte de la API pública.

La fachada pública `Crypto` implementa generación, derivación, inicialización y ciclo de vida (`close()` y context manager). La integración del codec de nombres con el keyset recuperado está cubierta por pruebas unitarias. Las operaciones sobre archivos/directorios todavía no están implementadas; tampoco existe aún publicación atómica de recursos sobre el filesystem.

## Responsabilidad del consumidor

La librería no administra almacenamiento, transporte, intercambio, backup, recuperación, rotación ni revocación. El consumidor debe conservar el contenedor `MasterKey` y, cuando esté protegido, la contraseña. Perder cualquiera de los elementos requeridos implica pérdida práctica de acceso.

## Memoria

La instancia ofrece `close()` y administrador de contexto. Tras el cierre, el acceso a las primitivas internas se rechaza. La limpieza es de mejor esfuerzo: Python no garantiza borrar todas las copias de secretos. `__del__` no constituye garantía de borrado seguro.
