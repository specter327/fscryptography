# Validación del backend criptográfico

## Alcance

Esta revisión contrasta las decisiones criptográficas propuestas con las APIs públicas documentadas de las dependencias. Es una revisión documental de fuentes oficiales; **no equivale a una prueba de ejecución, auditoría criptográfica ni certificación de compatibilidad**.

Fecha de revisión: 2026-11-12.

## Resultado ejecutivo

| Área | Resultado | Conclusión |
|---|---|---|
| Tink Python: AEAD | API documentada | Puede crear primitivas AEAD y serializar keysets. |
| Tink Python: Streaming AEAD | **Validado en CI** | `AES256_GCM_HKDF_1MB` generó keysets, se serializó/recuperó y superó pruebas de cifrado autenticado en Tink 1.16.1 con Python 3.10–3.13 sobre Ubuntu 26.04. |
| Serialización de keysets Tink | API binaria documentada | Puede utilizarse el formato Protobuf propio de Tink; requiere autorización explícita para material secreto. |
| Argon2id | API disponible en argon2-cffi | La derivación de una clave binaria fija puede hacerse con la API low-level. |
| AES-GCM para envolver MasterKey | API disponible en cryptography | Candidato apropiado para el payload pequeño del contenedor, no para cifrado segmentado de archivos. |

## Tink Python

Proyecto Python oficial: [tink-py](https://github.com/tink-crypto/tink-py).

### AEAD convencional

La API documenta la creación de keysets mediante `tink.new_keyset_handle(...)`, la obtención de primitivas con `KeysetHandle.primitive(...)` y el uso de `Aead.encrypt(plaintext, associated_data)` / `decrypt(ciphertext, associated_data)`.

Esto cubre el caso de cifrado autenticado de mensajes pequeños, como nombres de recursos, siempre que se seleccione una plantilla admitida y se genere un keyset independiente del keyset de contenido.

### Streaming AEAD

La API Python expone `StreamingAead`, `new_encrypting_stream(...)` y `new_decrypting_stream(...)`. El módulo también define la plantilla `AES256_GCM_HKDF_1MB`, con clave AES de 32 bytes, HKDF-SHA256, clave derivada de 32 bytes y segmento de ciphertext de 1 MiB.

Sin embargo, el código fuente del módulo de plantillas contiene una advertencia explícita: esas plantillas no pueden utilizarse actualmente para generar keysets y solo pueden utilizarse para generar claves individuales. En cambio, la guía general de Python muestra generación de keysets para una plantilla Streaming AEAD AES-CTR-HMAC. Las fuentes, por tanto, no permiten afirmar sin prueba que la plantilla GCM-HKDF pueda generar un keyset completo en la versión publicada que se vaya a fijar.

**Resultado de validación:** la prueba automatizada pasó en Tink `1.16.1` para Python `3.10.22`, `3.11.18`, `3.12.16` y `3.13.18`, en runners Ubuntu 26.04. En cada entorno se generó un keyset con `AES256_GCM_HKDF_1MB`, se serializó y recuperó mediante el formato Protobuf de Tink, y la primitiva recuperada superó los round-trips y los rechazos de AAD incorrecto, truncamiento y alteración del ciphertext.

**Decisión:** queda validada la viabilidad técnica de `AES256_GCM_HKDF_1MB` en Tink Python `1.16.1` para la matriz ejecutada. Tink pasa de candidato no verificado a backend seleccionado para el prototipo de Streaming AEAD. Antes de fijar la dependencia en producción aún deben ejecutarse pruebas en los sistemas operativos/plataformas objetivo y pruebas de integración sobre archivos reales.

No se sustituye AES-GCM por AES-CTR-HMAC.

### Serialización de keysets

Tink Python documenta serialización binaria mediante `tink.proto_keyset_format.serialize(handle, secret_key_access.TOKEN)` y carga mediante `parse(serialized, secret_key_access.TOKEN)`. También expone formato JSON, pero el contenedor de fscryptography no necesita JSON: el formato binario Protobuf de Tink evita inventar una representación de keysets.

El acceso al material secreto exige un token explícito. Tink advierte que los keysets en claro son sensibles y no deben persistirse sin protección. En fscryptography:
- El modo aleatorio sin contraseña debe tratar todo el MasterKey como secreto.
- El modo protegido debe cifrar el payload serializado antes de incluirlo en el contenedor.
- El token de acceso a material secreto debe quedar confinado al módulo interno de gestión de claves; nunca debe formar parte de la API pública.

No se debe confundir serializar un keyset en Protobuf con cifrarlo: la serialización binaria por sí sola no protege el material secreto.

## Argon2id con argon2-cffi

La biblioteca documenta `argon2.low_level.hash_secret_raw(..., type=Type.ID, ...)`, que produce bytes de longitud fija y permite especificar salt, coste temporal, memoria, paralelismo, longitud de salida y versión.

Para el contenedor protegido, esta API se ajusta mejor que `PasswordHasher`: se necesita una clave binaria de envoltura, no una cadena de hash de contraseña destinada a verificación. La salida prevista es de 32 bytes para AES-256.

Requisitos:
- Variante Argon2id (`Type.ID`).
- Salt aleatorio único por contenedor.
- Parámetros y versión guardados en el contenedor.
- Validación de límites de parámetros antes de ejecutar Argon2id.
- Longitud de salida fija de 32 bytes.
- Parámetros de coste finales pendientes de benchmark en hardware objetivo y de establecer límites contra entradas maliciosas.

Los valores predeterminados de `PasswordHasher` no se adoptan automáticamente como parámetros normativos de fscryptography.

## AEAD para proteger el contenedor MasterKey

`cryptography` ofrece `AESGCM`, que acepta claves AES de 128, 192 o 256 bits, nonce de 12 bytes y AAD; el resultado incorpora un tag de 16 bytes. La API falla con `InvalidTag` cuando no coincide la clave, el nonce, el AAD o el ciphertext.

Esto es adecuado como candidato para proteger el payload completo del contenedor: el tamaño del payload de keysets es acotado y no requiere streaming. La clave de 32 bytes procede de Argon2id.

La implementación debe generar un nonce nuevo y aleatorio por contenedor y nunca reutilizar un nonce con la misma clave. La cabecera y los parámetros que controlan la interpretación del contenedor se autentican como AAD. La selección de `cryptography` como dependencia normativa queda pendiente de fijar versión mínima y compatibilidad de plataformas.

**No utilizar `AESGCM` para cifrar archivos grandes por bloques manuales.** Eso exigiría diseñar un protocolo de segmentación, nonce, framing, autenticación y cierre propio. El cifrado de archivos debe permanecer delegado a un Streaming AEAD mantenido.

## Arquitectura candidata resultante

- **Archivos:** Streaming AEAD de Tink con AES256-GCM-HKDF-1MB, únicamente si la prueba de generación y round-trip del keyset pasa. Si no pasa, detener la selección del backend y evaluar alternativas; no implementar un protocolo propio.
- **Nombres:** AEAD convencional de Tink con keyset independiente, sujeto a validar una plantilla y límites de longitud de nombres.
- **MasterKey protegido:** Argon2id de argon2-cffi para derivar 32 bytes y AES-GCM de cryptography para envolver el payload serializado.
- **Keysets:** formato binario Protobuf soportado por Tink, contenido dentro del payload del contenedor; no definir un formato alternativo de keyset.

Esta arquitectura es una propuesta de integración, no una selección definitiva de dependencias ni una afirmación de que el backend de archivos ya funciona.

## Ejecución automatizada de la prueba Tink Python

El repositorio incluye una prueba de integración ejecutable en
`tests/backend_validation/test_tink_streaming_aead.py`. Comprueba, sin
fallback a otro perfil:

1. Disponibilidad de `AES256_GCM_HKDF_1MB` en la API Python instalada.
2. Generación del keyset mediante `tink.new_keyset_handle(...)`.
3. Serialización binaria Protobuf y recuperación mediante las APIs de Tink.
4. Creación de la primitiva desde el keyset recuperado.
5. Round-trip de payload vacío, pequeño y de 2 MiB.
6. Rechazo de AAD incorrecto, ciphertext truncado y ciphertext alterado.

Ejecución local:

```bash
python -m pip install "tink>=1.11,<2"
python tests/backend_validation/test_tink_streaming_aead.py
```

El workflow `.github/workflows/backend-validation.yml` ejecuta la misma prueba
en GitHub Actions con Python 3.10, 3.11, 3.12 y 3.13. El rango de dependencia
permite observar el comportamiento de las versiones publicadas de Tink dentro
de la serie mayor 1; el log registra la versión efectiva.

**Resultado observado — GitHub Actions Run 2:** [ejecución](https://github.com/specter327/fscryptography/actions/runs/43354754020), commit `ac75c5e2b062ec7030bce87ae88e2d7a103b83ba`, conclusión `success`. Los cuatro jobs (Python 3.10, 3.11, 3.12 y 3.13) finalizaron correctamente; cada job ejecutó y aprobó los cinco tests. En todos se instaló Tink `1.16.1`. El job Python 3.12 registró además un keyset serializado de 131 bytes.

**Interpretación:** un fallo de generación del keyset para el perfil exacto
bloquea la selección de ese backend. No se interpreta como permiso para cambiar
a AES-CTR-HMAC. Un workflow verde valida únicamente los entornos de CI
ejecutados; no sustituye la matriz de sistemas operativos/plataformas objetivo
ni la auditoría de seguridad.

## Pruebas de validación obligatorias

1. Instalar la versión candidata de Tink en cada plataforma objetivo.
2. Registrar Streaming AEAD y generar un keyset con `AES256_GCM_HKDF_1MB`.
3. Serializarlo en formato binario y volverlo a cargar.
4. Crear la primitiva Streaming AEAD y ejecutar round-trip con archivos vacíos, pequeños, mayores que un segmento y archivos grandes.
5. Verificar que truncamiento, alteración, reordenamiento y AAD incorrecto no producen plaintext aceptado.
6. Verificar que el plaintext de descifrado no se publica antes de autenticar el final del stream.
7. Repetir para el keyset AEAD de nombres.
8. Verificar Argon2id con contraseña correcta/incorrecta, parámetros fuera de límites y contenedor alterado.
9. Verificar AES-GCM de envoltura con nonce/AAD/ciphertext alterados.
10. Registrar versiones exactas de Python, Tink, argon2-cffi, cryptography y plataformas.

## Fuentes oficiales consultadas

- [Tink Python: HOWTO](https://github.com/tink-crypto/tink-py/blob/main/docs/PYTHON-HOWTO.md)
- [Tink Python: plantillas Streaming AEAD](https://github.com/tink-crypto/tink-py/blob/main/tink/streaming_aead/_streaming_aead_key_templates.py)
- [Tink Python: formato binario de keysets](https://github.com/tink-crypto/tink-py/blob/main/tink/_proto_keyset_format.py)
- [Tink: Streaming AEAD](https://developers.google.com/tink/streaming-aead)
- [Tink: serialización de keysets](https://developers.google.com/tink/wire-format)
- [argon2-cffi: API](https://argon2-cffi.readthedocs.io/en/stable/api.html)
- [cryptography: AEAD](https://cryptography.io/en/stable/hazmat/primitives/aead/)
