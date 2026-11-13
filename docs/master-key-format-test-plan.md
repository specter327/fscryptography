# Plan de pruebas: formato MasterKey

## Propósito

Definir la suite de conformidad del contenedor `MasterKey` antes de implementar el parser y la gestión de claves. Este documento especifica resultados esperados y límites de prueba; no contiene una implementación alternativa del formato.

Las pruebas se dividirán entre:
- **Pruebas de estructura:** framing binario, longitudes, versiones y campos.
- **Pruebas criptográficas:** KDF, AEAD, AAD y rechazo de alteraciones.
- **Pruebas de integración:** generación y recuperación de keysets Tink.
- **Pruebas de robustez:** entradas adversariales, límites y ausencia de filtración parcial.

## Fixtures y vectores

La suite deberá mantener vectores golden independientes de la implementación:
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
| KDF | Parámetros por debajo/encima de límites | Rechazo antes de ejecutar Argon2id |
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

La selección del perfil de nombres debe cerrarse antes de marcar esta matriz como completa.

## Propiedades y fuzzing

Una vez exista el parser, ejecutar pruebas generativas/fuzzing para:
- Cualquier secuencia de bytes arbitraria: nunca provocar crash del proceso, bucle no acotado ni asignación desproporcionada.
- Cualquier longitud declarada: no leer fuera de límites ni reservar memoria antes de validar.
- Cualquier campo desconocido: rechazo determinista.
- Cualquier truncamiento en cualquier offset: rechazo controlado.
- Re-serializar un contenedor válido: producir bytes canónicos idénticos para la misma estructura lógica, salvo que la política permita variación explícita.

El fuzzing no sustituye vectores golden ni pruebas criptográficas.

## Criterios de aceptación previos a implementación funcional

La fase de especificación del formato se considera cerrada cuando:
1. Se aprueba el layout binario v1 y sus límites.
2. Se fijan los límites de contraseña y parámetros Argon2id.
3. Se aprueba el perfil de nombres y su tipo de keyset.
4. Se publican vectores golden válidos e inválidos.
5. Se acuerda el catálogo de errores de parsing/autenticación.
6. Se define la matriz de plataformas para ejecutar la conformidad.

La implementación funcional de archivos y directorios permanece bloqueada hasta completar esta fase.
