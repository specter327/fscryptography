# Cifrado de nombres

## Alcance

Se transforma exclusivamente un componente de nombre de ruta. No se explora ni recorre el directorio. Cifrar un directorio no modifica sus hijos.

## Requisitos

- Reversibilidad con la clave correspondiente.
- Confidencialidad, autenticidad y detección de modificaciones.
- Metadatos autocontenidos; sin sidecars ni bases de datos.
- Keyset independiente del destinado al contenido.
- Representación válida en los filesystems soportados.
- Validación previa de longitud y colisiones.
- No sobrescribir destinos existentes por defecto.
- No revelar plaintext antes de autenticar el ciphertext completo.

## Perfil criptográfico validado

El candidato de v1 es Tink AEAD convencional con la plantilla `AES256_GCM` y un keyset independiente de tipo `Aead`.

La prueba `tests/backend_validation/test_tink_aead_names.py` valida en Tink 1.16.1 la generación del keyset, serialización y recuperación Protobuf, round-trip de nombres ASCII/Unicode y rechazo de AAD incorrecto, ciphertext alterado y truncado. GitHub Actions Run 10 aprobó los cuatro entornos Python 3.10–3.13.

Tink administra la generación del nonce y el formato del ciphertext. Con el prefijo de salida TINK, el ciphertext añade 5 bytes de prefijo, 12 bytes de nonce y 16 bytes de tag: 33 bytes de overhead sobre el plaintext. No se debe implementar manualmente AES-GCM ni gestionar nonces por fuera de Tink.

**Estado:** perfil AEAD y tipo de keyset técnicamente validados para el prototipo. La representación textual `~1` + Base64URL sin padding y el límite derivado de 156 bytes UTF-8 para componentes de 255 bytes quedan aprobados como contrato de nombres v1. La prueba no implementa ni valida operaciones reales de filesystem.

## Representación del componente cifrado — contrato aprobado

- Prefijo ASCII `~1`, que identifica la versión de la representación de nombres.
- Seguido por el ciphertext Tink codificado como Base64URL sin padding.
- Alfabeto Base64URL: `A-Z`, `a-z`, `0-9`, `-` y `_`.
- El ciphertext Tink incluye su prefijo de salida, nonce, ciphertext y tag. No se añade un nonce externo.
- AAD constante: `fscryptography:filename:v1`. No incluir la ruta padre, porque mover el recurso no debe impedir descifrar su nombre.
- El plaintext es el nombre original codificado en UTF-8 estricto. No se aplica normalización Unicode implícita.

El marcador identifica un candidato de formato, pero por sí solo no demuestra autenticidad. La autenticidad solo se establece al verificar AEAD.

La representación no contiene separadores de ruta ni NUL. El nombre descifrado debe validarse de nuevo como un único componente de nombre en el filesystem de destino.

La decodificación Base64URL debe ser estricta y canónica: sin padding, whitespace ni caracteres ajenos al alfabeto; después de decodificar, volver a codificar debe producir exactamente la misma representación. El ciphertext debe ser aceptable por el formato Tink esperado. No intentar formatos alternativos ni downgrade.

## Presupuesto de longitud

Para un filesystem con límite de componente de 255 bytes:

- Ciphertext Tink: longitud del plaintext UTF-8 + 33 bytes.
- Base64URL sin padding: expansión del ciphertext a aproximadamente 4/3.
- Prefijo `~1`: 2 bytes adicionales.
- Un plaintext de 156 bytes produce una representación de 254 caracteres ASCII.
- Un plaintext de 157 bytes produce una representación de 256 caracteres y excede el límite.

Por tanto, **156 bytes UTF-8 es el máximo derivado para esta representación cuando el límite del componente es 255 bytes**. Es un límite en bytes, no en caracteres Unicode.

La implementación debe consultar el límite real del componente en el filesystem de destino cuando la plataforma lo permita y validar la longitud final codificada antes de modificar el recurso. Si el límite real es inferior, prevalece ese límite. No truncar ciphertext, no cambiar silenciosamente de codificación y no intentar una segunda representación.

La restricción aprobada de 156 bytes reduce el conjunto de nombres que pueden cifrarse. No es una limitación de AES-GCM en sí, sino de la combinación de formato Tink, Base64URL y límite de componente.

## Política de nombres de entrada y doble cifrado — contrato v1

La cadena `~1` no es un escape reservado para nombres plaintext. Un nombre original puede comenzar legítimamente con esos dos caracteres, incluso si el resto se parece a Base64URL. Por ello, **no clasificar un nombre como cifrado únicamente por su prefijo**.

### Cifrado

1. Tratar el nombre de origen como plaintext y validarlo como componente UTF-8.
2. Antes de cifrar, si el nombre tiene la sintaxis canónica completa de una representación `~1` y la autenticación AEAD con la clave activa tiene éxito, rechazar la operación como recurso ya cifrado. No volver a cifrarlo.
3. Si la autenticación no tiene éxito, el nombre sigue siendo un posible plaintext. Cifrarlo normalmente; no revelar si una representación con apariencia de ciphertext fue creada con otra clave.
4. Validar la longitud y la colisión del nombre de destino antes de publicar el cambio.

Esta regla evita el doble cifrado accidental detectable con la clave activa. No permite identificar de forma fiable un nombre cifrado con otra clave: el formato no incluye un identificador público de clave ni un registro externo, y no se deben probar múltiples claves automáticamente.

### Descifrado

1. Exigir el marcador `~1`. Su ausencia es un error de formato.
2. Exigir Base64URL canónico y una estructura compatible con el ciphertext Tink esperado. Una representación malformada produce `FormatError`.
3. Verificar AEAD con el keyset de nombres y el AAD fijo. Si la autenticación falla, producir `AuthenticationError`; no tratar el nombre como plaintext ni probar otra clave/formato.
4. Decodificar el plaintext como UTF-8 estricto y validar que sea un único componente admisible en el filesystem de destino.
5. Publicar el rename solo después de completar todas las validaciones.

Un nombre plaintext que empiece por `~1` puede ser interpretado como candidato al invocar explícitamente descifrado. Si no es una representación válida, se rechaza como formato inválido; no se realiza fallback a plaintext.

## Reglas de portabilidad y semántica del filesystem — contrato v1

### Perfil de nombres Windows

En Windows, validar el nombre plaintext que se vaya a crear o restaurar. Rechazar:

- Los caracteres `<`, `>`, `:`, `"`, `/`, `\\`, `|`, `?` y `*`.
- Los caracteres de control U+0000 a U+001F.
- Componentes que terminen en punto o espacio.
- Los nombres de dispositivo reservados, sin distinguir mayúsculas y aunque lleven extensión: `CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9` y `LPT1`–`LPT9`.
- De forma conservadora, también `CONIN$`, `CONOUT$`, `CLOCK$` y las variantes de `COM`/`LPT` que usan los dígitos superíndice ¹, ² y ³.

La comprobación de nombres reservados se aplica al componente completo antes del primer punto, con comparación insensible a mayúsculas. No se debe asumir que añadir una extensión vuelve admisible un nombre reservado.

El nombre cifrado `~1` + Base64URL utiliza un alfabeto permitido por el perfil Win32 anterior. El plaintext recuperado debe validarse otra vez: un nombre válido en GNU/Linux puede ser imposible de crear en Windows.

### Perfil de nombres GNU/Linux

Exigir UTF-8 estricto para los nombres que procesa la librería, aunque el filesystem subyacente pueda almacenar secuencias de bytes que no sean UTF-8 válidas. Rechazar NUL y el separador de componentes `/`. Respetar el límite de bytes por componente del filesystem real.

No imponer en GNU/Linux las restricciones de nombres reservados o caracteres de Windows salvo que el consumidor solicite explícitamente un perfil portátil más restrictivo.

### Mayúsculas, equivalencia y normalización

- Preservar exactamente la secuencia UTF-8 del nombre original; no aplicar NFC, NFD, NFKC, NFKD, lowercase ni Unicode casefold.
- No asumir que NTFS y ext4 comparan nombres de la misma forma.
- En NTFS, respetar el comportamiento de comparación del directorio concreto; normalmente es insensible a mayúsculas, pero puede existir sensibilidad habilitada por directorio.
- En ext4, respetar la configuración efectiva del directorio, incluyendo si está habilitado `casefold`.
- No implementar una equivalencia global propia que sustituya la decisión del filesystem. La existencia y publicación del destino deben resolverse usando la semántica efectiva del filesystem.

### Colisiones y concurrencia

Una comprobación previa de existencia no elimina carreras con procesos externos. La publicación debe usar una operación de rename/creación que no reemplace un destino existente. Si la plataforma no permite garantizar esa condición, la implementación debe fallar de forma segura en lugar de sobrescribir.

La colisión se determina por la semántica real del namespace de destino, no solo por comparar las cadenas Python. Esto incluye equivalencias por mayúsculas/minúsculas y reglas de casefold del directorio. Si dos representaciones Base64URL distintas colisionan bajo la comparación del filesystem, una de ellas no puede publicarse allí.

No se debe normalizar ni renombrar automáticamente para resolver una colisión. Informar el conflicto mediante `DestinationConflictError` y preservar el origen.

## Longitud y colisiones

El nombre cifrado puede superar el límite por componente. La operación debe detectarlo antes de modificar el recurso y fallar preservando el original.

No sobrescribir destinos existentes por defecto. La comprobación previa no elimina carreras con procesos externos; la publicación debe manejar colisiones reales y conservar el original si el destino no puede publicarse.

La aleatoriedad del nonce implica que cifrar dos veces el mismo nombre puede producir representaciones distintas. No asumir que el cifrado es determinista ni utilizar igualdad de ciphertext para inferir igualdad de nombres.

## Extensión

Con `encrypt_name=False`, el nombre permanece visible y `new_extension` determina la extensión cifrada.

Con `encrypt_name=True`, se cifra el nombre completo incluida la extensión original; esta se recupera del plaintext autenticado al descifrar. No conservar una extensión visible fuera del ciphertext.

El cifrado no oculta jerarquía, cantidad de recursos ni otros metadatos del filesystem.

## Decisiones y estado

- [x] Validar Tink `AES256_GCM` como AEAD convencional y el tipo de keyset `Aead`.
- [x] Aprobar el marcador `~1` y la codificación Base64URL sin padding.
- [x] Aprobar el límite derivado de 156 bytes UTF-8 para componentes con máximo de 255 bytes.
- [x] Definir la validación conservadora de nombres Windows.
- [x] Definir preservación UTF-8 y respeto a la semántica efectiva de mayúsculas/casefold del filesystem.
- [x] Definir política de detección de doble cifrado y tratamiento de candidatos `~1`.
- [x] Definir manejo de colisiones y publicación sin sobrescritura.
- [x] Implementar el primer codec `~1` + Base64URL, la validación de nombres y el adaptador de keysets Tink.
- [x] Añadir pruebas unitarias para reglas de nombres, canonicalidad, límites y round-trip AEAD.
- [x] Integrar el keyset de nombres con el contenedor MasterKey y probar su recuperación en la fachada Crypto.
- [ ] Integrar cifrado/descifrado con operaciones reales de rename y publicación sin sobrescritura.
- [ ] Validar la representación y las reglas sobre NTFS y ext4 reales.


## Platform-specific component-length measurement

The internal component limit uses the native filesystem unit:

- GNU/Linux: bytes in the strict UTF-8 sequence.
- Windows: UTF-16 code units (a supplementary character occupies two units).

The encrypted representation (~1 plus Base64URL) is ASCII, so its length is identical in bytes and UTF-16 code units. For the recovered plaintext name, Windows validation must count UTF-16 code units; measuring UTF-8 bytes would incorrectly reject Unicode names that fit in NTFS. The implementation does not normalize Unicode or emulate the filesystem's own equivalence/case-folding rules.
