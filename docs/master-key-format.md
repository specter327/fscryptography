# Formato de MasterKey

## Objetivo y contrato

`MasterKey` es un contenedor autocontenido, versionado y opaco para el consumidor. Transporta los keysets secretos que necesita `fscryptography` para cifrar y descifrar recursos. No es una clave AES individual ni el formato de un archivo cifrado.

La representación pública es una cadena Base64 estándar con padding. Su decodificación produce un contenedor binario. Base64 solo proporciona codificación; no aporta confidencialidad, integridad ni protección frente a exposición.

El consumidor puede almacenar o transportar la cadena, pero debe tratar su contenido como material secreto. No debe registrar el valor en logs, mensajes de error, telemetría ni salidas de diagnóstico.

## Modos

Se definen dos modos mutuamente excluyentes:

| Valor | Modo | Protección del payload |
|---:|---|---|
| `0x00` | Aleatorio | Sin cifrado de envoltura; el contenedor completo es secreto |
| `0x01` | Protegido por contraseña | AEAD con clave derivada mediante Argon2id |

El modo se declara explícitamente. No se permite inferirlo mediante heurísticas ni intentar ambos modos silenciosamente.

## Payload lógico

El esquema de payload `0x01` contiene exactamente dos keysets Tink independientes, en este orden:

1. Keyset de Streaming AEAD para contenido de archivos.
2. Keyset AEAD para nombres.

Cada keyset se serializa mediante el formato binario Protobuf soportado por Tink. No se utiliza JSON, `pickle` ni deserialización ejecutable. La serialización y recuperación de keysets debe permanecer confinada al módulo interno de gestión de claves y utilizar el token explícito de acceso a material secreto exigido por Tink.

El payload aplica framing propio únicamente para delimitar los dos mensajes Protobuf:

| Campo | Tamaño | Codificación |
|---|---:|---|
| Longitud del keyset de contenido | 4 bytes | Entero sin signo, big-endian |
| Keyset de contenido | Longitud indicada | Protobuf binario de Tink |
| Longitud del keyset de nombres | 4 bytes | Entero sin signo, big-endian |
| Keyset de nombres | Longitud indicada | Protobuf binario de Tink |

No se permiten longitudes cero, bytes sobrantes ni campos adicionales en el esquema `0x01`. Los dos keysets deben validarse como tipos de primitivas esperados; no basta con que sean Protobuf sintácticamente válido.

Límites estructurales propuestos para v1:
- Cada keyset serializado: máximo 32 KiB.
- Payload lógico: máximo 128 KiB.
- Longitud del payload exterior: máximo 128 KiB en modo aleatorio y 128 KiB + 16 bytes en modo protegido (tag GCM incluido).
- Los límites se comprueban antes de reservar memoria o invocar el parser Protobuf.

El keyset de nombres utiliza la primitiva Tink `Aead` con la plantilla `AES256_GCM`, validada mediante prueba ejecutable en Tink 1.16.1 con Python 3.10–3.13. La representación textual aprobada es `~1` seguido de ciphertext Tink en Base64URL sin padding; para componentes de 255 bytes, el máximo derivado de plaintext UTF-8 es 156 bytes. La validación sobre filesystems objetivo sigue pendiente; véase [Cifrado de nombres](filename-encryption.md).

## Propuesta de formato binario v1

Todos los enteros multibyte usan big-endian. No hay padding implícito entre campos. La cabecera completa se utiliza como AAD en el modo protegido.

### Prefijo común

El prefijo ocupa exactamente 20 bytes:

| Offset | Tamaño | Campo | Valor / semántica |
|---:|---:|---|---|
| 0 | 8 | Magic | Bytes ASCII `FSCRKEY\0` |
| 8 | 1 | Major version | `0x01` |
| 9 | 1 | Minor version | `0x00` |
| 10 | 1 | Mode | `0x00` o `0x01` según la tabla de modos |
| 11 | 1 | Payload schema | `0x01` |
| 12 | 2 | Flags | `0x0000`; cualquier bit distinto de cero se rechaza en v1 |
| 14 | 2 | Header length | Longitud exacta de la cabecera, incluido el prefijo |
| 16 | 4 | Payload length | Longitud exacta de los bytes que siguen a la cabecera |

La longitud total del contenedor binario debe ser exactamente `header_length + payload_length`. No se aceptan bytes finales adicionales.

### Extensión del modo aleatorio

El modo `0x00` no añade campos a la cabecera:
- `header_length = 20`.
- El payload son directamente los bytes del payload lógico.
- No hay KDF, salt, nonce ni cifrado de envoltura.
- La cabecera no está autenticada criptográficamente. El parser valida estructura, pero no debe afirmar que detecta toda manipulación maliciosa del contenedor.

### Extensión del modo protegido

El modo `0x01` añade exactamente 41 bytes al prefijo; por tanto, `header_length = 61`.

| Offset | Tamaño | Campo | Valor / semántica |
|---:|---:|---|---|
| 20 | 1 | KDF identifier | `0x01` = Argon2id |
| 21 | 1 | Argon2 version | `0x13` = versión 19 |
| 22 | 4 | Memory cost | KiB, entero sin signo |
| 26 | 4 | Time cost | Iteraciones, entero sin signo |
| 30 | 2 | Parallelism | Grado de paralelismo, entero sin signo |
| 32 | 16 | Salt | Salt aleatorio de Argon2id |
| 48 | 1 | Wrapping AEAD identifier | `0x01` = AES-256-GCM |
| 49 | 12 | Nonce | Nonce GCM de 96 bits |

El payload es el resultado de AES-256-GCM aplicado al payload lógico:
- La clave de envoltura tiene 32 bytes y se deriva de la contraseña con Argon2id.
- La cabecera completa, desde el offset 0 hasta `header_length - 1`, se pasa sin transformación como AAD.
- El nonce se genera de forma segura y no se reutiliza con la misma clave.
- El resultado de AES-GCM incluye el tag de autenticación de 16 bytes.
- `payload_length` incluye ciphertext y tag.

La contraseña no se almacena. La API recibe texto y su codificación es UTF-8 estricto, sin normalización Unicode implícita. La política normativa de Argon2id y los límites de entrada están definidos en [Política de Argon2id y límites de apertura](argon2id-policy.md).

## Límites normativos de MasterKey v1

Los siguientes límites están aprobados y forman parte del contrato de parsing:

| Elemento | Límite |
|---|---:|
| Contenedor binario completo | 131.149 bytes máximo |
| Representación Base64 estándar con padding | 174.868 caracteres ASCII máximo |
| Contraseña | 1–1.024 bytes UTF-8 |
| Salt Argon2id | Exactamente 16 bytes |
| Nonce AES-256-GCM | Exactamente 12 bytes |
| Tag AES-256-GCM | Exactamente 16 bytes |
| Keyset serializado individual | 32 KiB máximo |
| Payload lógico | 128 KiB máximo |

El máximo binario se deriva del contenedor protegido: cabecera de 61 bytes + payload lógico máximo de 131.072 bytes + tag GCM de 16 bytes. El máximo Base64 corresponde a la codificación estándar con padding de ese tamaño binario.

Base64 se acepta estrictamente: se rechazan whitespace, saltos de línea, caracteres ajenos al alfabeto, padding incorrecto y cualquier representación no canónica. El límite se verifica antes de decodificar.

La contraseña se recibe como texto, se codifica con UTF-8 estricto y se valida por longitud en bytes. Se rechaza la cadena vacía y cualquier contraseña superior a 1.024 bytes. No se aplica normalización Unicode, trim ni transformación silenciosa. La contraseña nunca se registra ni se incluye en errores.

Los parámetros Argon2id productivos aceptados son exclusivamente versión 19, memoria 65.536 KiB, time_cost 3 y parallelism 1. Cualquier otra combinación se rechaza antes de ejecutar la KDF. Véase [Política de Argon2id](argon2id-policy.md).

## Reglas de parsing

El parser debe operar en este orden, sin ejecutar KDF ni deserializar keysets antes de validar el framing exterior:

1. Verificar que la entrada Base64 no excede 174.868 caracteres ASCII y cumple el alfabeto y padding estrictos.
2. Decodificar y verificar que el contenedor binario no excede 131.149 bytes.
3. Verificar tamaño mínimo, magic y versión soportada.
4. Verificar modo, schema y flags.
5. Verificar que `header_length` coincide exactamente con el modo y versión.
6. Verificar que `payload_length` no supera 128 KiB en modo aleatorio ni 128 KiB + 16 bytes en modo protegido, y que el tamaño total coincide exactamente con la entrada.
7. En modo protegido, validar identificadores, versión Argon2, tamaños fijos, límites de contraseña y el perfil Argon2id permitido antes de ejecutar la KDF.
8. En modo protegido, autenticar y descifrar el payload completo; no entregar bytes parciales.
9. Validar el framing interno, las longitudes y la ausencia de bytes sobrantes.
10. Parsear los dos keysets con Tink y verificar que corresponden a las primitivas esperadas.
11. Entregar ambos keysets solo si todas las validaciones concluyeron correctamente.

Cualquier fallo invalida el contenedor completo. Nunca se devuelve un keyset parcial ni se generan claves de reemplazo silenciosamente.

### Rechazos obligatorios

- Magic incorrecto, entrada truncada o versión no soportada.
- Modo, schema, identificador KDF/AEAD o flags desconocidos.
- Longitudes incoherentes, fuera de límites o que no coincidan con el tamaño real.
- Cabecera de tamaño inesperado, extensiones o bytes finales no definidos.
- Base64 no canónico, whitespace, padding incorrecto o tamaño excedido.\n- Contraseña vacía, UTF-8 inválido o superior a 1.024 bytes.\n- Parámetros Argon2id fuera del perfil permitido, antes de ejecutar la KDF.
- Contraseña incorrecta, nonce/AAD/ciphertext/tag alterados.
- Payload interno truncado, longitudes cero, longitudes fuera de límites o bytes sobrantes.
- Protobuf malformado, keysets vacíos o keysets de tipo inesperado.

## Autenticación y límites de seguridad

En el modo protegido, todos los campos que controlan la interpretación del contenedor están incluidos en el AAD: magic, versiones, modo, schema, flags, longitudes, parámetros KDF, salt, identificador AEAD y nonce. Una alteración de cualquiera de ellos debe impedir la apertura, ya sea por rechazo estructural o por fallo de autenticación.

En el modo aleatorio no existe autenticación de la cabecera ni del payload frente a modificación deliberada. La integridad de los keysets solo puede comprobarse parcialmente mediante sus validaciones internas; no se debe presentar este modo como autenticado.

Base64 no es cifrado. El modo aleatorio debe protegerse como una credencial secreta. El modo protegido depende de la fortaleza de la contraseña, de la política de coste Argon2id y de AES-256-GCM.

## Compatibilidad y evolución

- La versión inicial propuesta es `1.0`.
- Una versión major desconocida se rechaza.
- Una versión minor desconocida también se rechaza en v1; no se ignoran extensiones no definidas.
- Los identificadores de algoritmos y esquemas son explícitos; nunca se seleccionan algoritmos mediante heurísticas.
- No hay downgrade automático ni fallback criptográfico.
- No se promete migración automática de contenedores antiguos.

## Estado de decisiones

**Aprobado:**
- Layout binario `MasterKey v1.0`: magic, campos, offsets, tamaños y codificación big-endian.
- Framing del payload con dos longitudes Protobuf de Tink.
- Límites estructurales de 32 KiB por keyset y 128 KiB por payload lógico.
- Codificación UTF-8 estricta sin normalización implícita.
- Representación de nombres aprobada: marcador `~1` + Base64URL sin padding; máximo derivado de 156 bytes UTF-8 para componentes de 255 bytes.

**Validación de conformidad añadida:**
- Vectores golden sintéticos para los modos aleatorio y protegido en `tests/master_key_format/fixtures/master_key_v1_vectors.json`.
- Pruebas ejecutables de layout, framing, AAD, autenticación, alteraciones y truncamientos en `tests/master_key_format/test_master_key_format_vectors.py`.
- Los keysets de estos vectores son bytes opacos sintéticos, no keysets Tink válidos. Las pruebas no sustituyen la integración de keysets ni un parser productivo.

**Aprobado como contrato normativo v1:**
- Límites de entrada y contraseña definidos en [la política de Argon2id](argon2id-policy.md).
- Perfil Argon2id v1 y rechazo de cualquier parámetro distinto del perfil aprobado antes de ejecutar la KDF.

**Validado para el prototipo:**
- Perfil AEAD de nombres Tink `AES256_GCM` y keyset `Aead`, con prueba CI en Python 3.10–3.13.

**Aprobado como contrato de nombres v1:**
- Marcador `~1` seguido de ciphertext Tink codificado en Base64URL sin padding.
- Máximo derivado de 156 bytes UTF-8 cuando el límite del componente es 255 bytes. La compatibilidad real y las reglas específicas de cada filesystem aún deben validarse.

**Pendiente antes de implementar la gestión productiva de claves:**
- Vectores binarios golden definitivos y pruebas de integración con keysets Tink reales.
- Política de versiones y migración más allá de v1.

El layout binario v1.0 está aprobado y cuenta con vectores y pruebas de conformidad estructural. Esto no implica que exista ya un parser productivo ni una implementación funcional de gestión de claves.
