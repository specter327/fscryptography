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

**Estado:** perfil AEAD y tipo de keyset técnicamente validados para el prototipo. La representación textual del nombre y sus restricciones todavía requieren aprobación contractual. La prueba no implementa ni valida operaciones reales de filesystem.

## Representación del componente cifrado — propuesta

Propuesta de representación:

- Prefijo ASCII reservado `~1`, que identifica la versión de la representación de nombres.
- Seguido por el ciphertext Tink codificado como Base64URL sin padding.
- Alfabeto resultante: `A-Z`, `a-z`, `0-9`, `-` y `_`, además del prefijo `~1`.
- El ciphertext Tink incluye su prefijo de salida, nonce, ciphertext y tag. No se añade un nonce externo.
- AAD constante de dominio para la operación de nombres y versión correspondiente; no incluir la ruta padre, porque mover el recurso no debe impedir descifrar su nombre.
- El plaintext es el nombre original codificado en UTF-8 estricto. No se aplica normalización Unicode implícita.

El marcador permite reconocer el formato y rechazar entradas malformadas sin intentar múltiples decodificadores. La marca por sí sola no demuestra que el nombre sea auténtico: la autenticidad se determina al verificar AEAD.

No se permiten separadores de ruta, NUL, bytes inválidos UTF-8 ni caracteres fuera del alfabeto de representación. El nombre descifrado debe volver a validarse como un único componente de nombre.

## Presupuesto de longitud

Para un filesystem con límite de componente de 255 bytes:

- Ciphertext Tink: longitud del plaintext UTF-8 + 33 bytes.
- Base64URL sin padding: expansión del ciphertext a aproximadamente 4/3.
- Prefijo `~1`: 2 bytes adicionales.
- Un plaintext de 156 bytes produce una representación de 254 caracteres ASCII.
- Un plaintext de 157 bytes produce una representación de 256 caracteres y excede el límite.

Por tanto, **156 bytes UTF-8 es el máximo derivado para esta representación cuando el límite del componente es 255 bytes**. Es un límite en bytes, no en caracteres Unicode.

La implementación debe consultar el límite real del componente en el filesystem de destino cuando la plataforma lo permita y validar la longitud final codificada antes de modificar el recurso. Si el límite real es inferior, prevalece ese límite. No truncar ciphertext, no cambiar silenciosamente de codificación y no intentar una segunda representación.

La restricción de 156 bytes reduce el conjunto de nombres que pueden cifrarse. Debe aceptarse explícitamente antes de cerrar el contrato de nombres v1. No debe presentarse como una limitación de AES-GCM en sí, sino de la combinación de formato Tink, Base64URL y límite de componente.

## Longitud y colisiones

El nombre cifrado puede superar el límite por componente. La operación debe detectarlo antes de modificar el recurso y fallar preservando el original.

No sobrescribir destinos existentes por defecto. La comprobación previa no elimina carreras con procesos externos; la publicación debe manejar colisiones reales y conservar el original si el destino no puede publicarse.

La aleatoriedad del nonce implica que cifrar dos veces el mismo nombre puede producir representaciones distintas. No asumir que el cifrado es determinista ni utilizar igualdad de ciphertext para inferir igualdad de nombres.

## Extensión

Con `encrypt_name=False`, el nombre permanece visible y `new_extension` determina la extensión cifrada.

Con `encrypt_name=True`, se cifra el nombre completo incluida la extensión original; esta se recupera del plaintext autenticado al descifrar. No conservar una extensión visible fuera del ciphertext.

El cifrado no oculta jerarquía, cantidad de recursos ni otros metadatos del filesystem.

## Decisiones pendientes

- [x] Validar Tink `AES256_GCM` como AEAD convencional y el tipo de keyset `Aead`.
- [ ] Aprobar el marcador `~1` y la codificación Base64URL sin padding.
- [ ] Aprobar el límite derivado de 156 bytes UTF-8 para componentes con máximo de 255 bytes.
- [ ] Definir tratamiento de nombres reservados y sensibilidad a mayúsculas en Windows y GNU/Linux.
- [ ] Definir la política de nombres ya cifrados y evitar doble cifrado.
- [ ] Validar la representación sobre los filesystems objetivo.
