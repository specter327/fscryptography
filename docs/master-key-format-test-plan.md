# Plan de pruebas: formato MasterKey

## Propósito

Definir la suite de conformidad del contenedor `MasterKey` y mantener verificable su implementación productiva. Este documento especifica resultados esperados y límites de prueba; no contiene una implementación alternativa del formato.

Las pruebas se dividirán entre:
- **Pruebas de estructura:** framing binario, longitudes, versiones y campos.
- **Pruebas criptográficas:** KDF, AEAD, AAD y rechazo de alteraciones.
- **Pruebas de integración:** generación y recuperación de keysets Tink.
- **Pruebas de robustez:** entradas adversariales, límites y ausencia de filtración parcial.

## Fixtures y vectores

Se mantienen dos capas separadas de vectores golden:\n\n- `master_key_v1_vectors.json` + `test_master_key_format_vectors.py`: vectores estructurales del contenedor. Sus keysets son marcadores sintéticos opacos y no son Protobuf Tink válido; los parámetros Argon2id son deliberadamente modestos y exclusivos de esa suite estructural.\n- `master_key_tink_v1_vectors.json` + `test_master_key_tink_vectors.py`: contenedores completos con keysets Tink Protobuf válidos e independientes del generador/parser productivo. Incluyen `AES256_GCM_HKDF_1MB` para contenido (`RAW`) y `AES256_GCM` para nombres (`TINK`), con material determinista exclusivo de pruebas. Incluyen un contenedor aleatorio y uno protegido con el perfil Argon2id productivo (64 MiB / 3 / p=1), además de variantes inválidas con primitive intercambiado y Protobuf malformado. Los tests abren los contenedores mediante `open_master_key()` y ejercitan ambos primitives restaurados.\n\nLos bytes de estas fixtures son vectores de conformidad de pruebas; nunca deben reutilizarse como claves de producción.

La suite deberá ampliar y mantener vectores golden independientes de la implementación:
- Contenedor aleatorio v1 válido con dos keysets de prueba válidos.
- Contenedor protegido v1 válido con parámetros KDF de fixture deliberadamente modestos, nunca reutilizados como configuración de producción.
- Cabeceras válidas de ambos modos con sus bytes AAD exactos.
- Casos inválidos con un solo campo alterado para identificar el rechazo esperado.

Los fixtures criptográficos deben ser reproducibles. La generación aleatoria de producción no debe sustituirse por valores deterministas; las fixtures solo pertenecen al entorno de pruebas.

## Matriz de conformidad estructural

| Grupo | Caso | Resultado esperado |
|---|---|---|
| Entrada | Contenedor aleatorio válido | Aceptado |
| Entrada | Contenedor protegido válido + contraseña correcta | Aceptado |
| Entrada | Base64 inválido o padding incorrecto | Error de formato |
| Magic | Cada byte del magic alterado | Error de formato |
| Versiones | Major o minor no soportado | Error de versión |
| Modo | Valor desconocido | Error de formato |
| Schema | Valor desconocido | Error de formato |
| Flags | Cualquier bit reservado activado | Error de formato |
| Header | Longitud menor, mayor o incompatible con el modo | Error de formato |
| Payload | Longitud menor/mayor que los bytes disponibles | Error de formato |
| Payload | Payload aleatorio por encima de 128 KiB | Error de formato antes de asignación grande |
| Payload | Payload protegido por encima de 128 KiB + tag de 16 bytes | Error de formato antes de asignación grande |
| Framing interno | Longitud cero o superior al máximo | Error de formato |
| Framing interno | Segundo keyset ausente o truncado | Error de formato |
| Framing interno | Bytes sobrantes | Error de formato |
| Protobuf | Mensaje malformado | Error de formato |
| Keysets | Keyset vacío o tipo de primitiva inesperado | Error de configuración/formato |
| Robustez | Entrada vacía, de un byte y truncada en cada frontera | Rechazo controlado, sin excepción no prevista |

## Matriz criptográfica

| Grupo | Caso | Resultado esperado |
|---|---|---|
| KDF | Misma contraseña, salt y parámetros | Misma clave derivada |
| KDF | Cambiar contraseña o salt | Clave derivada diferente |
| KDF | Variante o versión desconocida | Rechazo antes de derivar |
| KDF | Parámetros distintos del perfil productivo permitido | Rechazo antes de ejecutar Argon2id |
| KDF | Parámetros extremos de memoria, iteraciones o paralelismo | Rechazo temprano, sin invocar Argon2id |
| Entrada | Base64 por encima de 174.868 caracteres ASCII o con caracteres/padding inválidos | Rechazo antes de decodificar completamente |
| Entrada | Contenedor binario superior a 131.149 bytes | Rechazo antes de parsear campos variables |
| Contraseña | Vacía o superior a 1.024 bytes UTF-8 | Rechazo antes de ejecutar Argon2id |
| Campos fijos | Salt distinto de 16 bytes, nonce distinto de 12 bytes o tag distinto de 16 bytes | Rechazo estructural/criptográfico |
| Contraseña | Contraseña correcta | Apertura correcta |
| Contraseña | Contraseña incorrecta | Fallo de autenticación, sin keysets |
| AAD | Alterar cada campo de cabecera protegido | Rechazo estructural o de autenticación |
| AEAD | Alterar nonce, ciphertext o tag | Fallo de autenticación |
| AEAD | Truncar ciphertext/tag | Fallo de autenticación |
| AEAD | Payload vacío o menor que tag | Rechazo |
| Secretos | Error durante apertura | No incluir contraseña, clave ni payload en excepción/log |

## Integración Tink

- Generar independientemente el keyset Streaming AEAD de contenido y el keyset AEAD de nombres.
- Serializar y recuperar ambos con el formato binario Protobuf de Tink y el token de acceso secreto requerido.
- Confirmar que ambos keysets sobreviven al round-trip del contenedor.
- Confirmar que el parser rechaza keysets de tipo incorrecto.
- Confirmar que una apertura fallida no entrega el primer keyset si falla el segundo.
- No usar un formato de keyset propio ni exponer keysets a la API pública.

El perfil Tink `AES256_GCM` y el keyset `Aead` ya pasaron la prueba de backend en CI. La integración productiva genera y restaura ambos keysets Tink dentro del MasterKey. La nueva suite de vectores golden ejercita la apertura productiva de ambos keysets, su uso criptográfico y el rechazo de keysets inválidos o de primitive incorrecto; su resultado de CI debe comprobarse antes de marcar cerrada esta ampliación.

## Propiedades y fuzzing

Ejecutar pruebas generativas/fuzzing sobre el parser productivo para:
- Cualquier secuencia de bytes arbitraria: nunca provocar crash del proceso, bucle no acotado ni asignación desproporcionada.
- Cualquier longitud declarada: no leer fuera de límites ni reservar memoria antes de validar.
- Cualquier campo desconocido: rechazo determinista.
- Cualquier truncamiento en cualquier offset: rechazo controlado.
- Re-serializar un contenedor válido: producir bytes canónicos idénticos para la misma estructura lógica, salvo que la política permita variación explícita.

El fuzzing no sustituye vectores golden ni pruebas criptográficas.

## Criterios de aceptación previos a implementación funcional

La fase de especificación del formato se considera cerrada cuando:
1. [x] Se aprueba el layout binario v1 y sus límites.
2. [x] Se ejecuta el benchmark de referencia y se aprueba el perfil Argon2id v1 (64 MiB / 3 / p=1), junto con los límites normativos de entrada y contraseña de [la política de Argon2id](argon2id-policy.md).
3. [~] Se valida el perfil AEAD de nombres Tink `AES256_GCM` y el tipo `Aead`; se aprobaron `~1` + Base64URL sin padding y el límite de 156 bytes UTF-8 para componentes de 255 bytes. La validación sobre filesystems objetivo sigue pendiente.
4. [~] Se publican vectores golden estructurales y se añaden vectores independientes con keysets Tink válidos e inválidos; la ampliación queda pendiente de CI verde y revisión del resultado.
5. [x] Se acuerda el catálogo de errores de parsing/autenticación en docs/errors.md.
6. [x] Se define la matriz de plataformas objetivo en docs/platform-compatibility.md.

La política de producción aprobada para v1 utiliza Argon2id v19 con 64 MiB, 3 iteraciones y paralelismo 1; exige aceptación estricta del perfil antes de ejecutar la KDF. Los valores de fixtures de bajo coste no deben ser aceptados por el parser productivo. Los límites de entrada y contraseña están aprobados contractualmente; véase [Política de Argon2id y límites de apertura](argon2id-policy.md).

El parser/generador productivo MasterKey v1.0 y la fachada pública están implementados. La cobertura productiva y sus límites se describen en el estado de ejecución.


## Estado de ejecución

Las pruebas de `tests/master_key_format/test_master_key_format_vectors.py` validan el layout aprobado mediante un verificador exclusivo de pruebas y fixtures sintéticas. La nueva suite `tests/master_key_format/test_master_key_tink_vectors.py` abre contenedores golden con keysets Tink Protobuf válidos mediante el parser productivo y prueba ambos primitives; incluye variantes inválidas por primitive incorrecto y Protobuf malformado. El parser productivo de `src/fscryptography/_master_key.py` también genera y restaura keysets Tink reales. `tests/unit/test_master_key.py` cubre la integración productiva: generación y apertura en ambos modos, uso de la primitiva AEAD de nombres, contraseña incorrecta, alteración del payload, Base64 canónico, límites de contraseña y rechazo de cada campo del perfil Argon2id no admitido antes de ejecutar la KDF, además del rechazo de contraseñas UTF-8 fuera de límite. El control de concurrencia/admisión de aperturas protegidas corresponde a la aplicación integradora; la librería no implementa un limitador interno. Los vectores sintéticos de estructura usan Argon2id de bajo coste y keysets opacos no válidos; nunca deben aceptarse como contenedores productivos.
