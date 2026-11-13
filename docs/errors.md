# Errores y excepciones

## Contrato público
La API utiliza excepciones tipadas para comunicar fallos. Las operaciones que modifican recursos no devuelven False para representar errores.

- Crypto.file.encrypt(), Crypto.file.decrypt(), Crypto.dir.encrypt() y Crypto.dir.decrypt() devuelven None cuando terminan correctamente.
- Si una operación no puede completarse, lanza una excepción.
- Las funciones de generación y derivación de claves devuelven un MasterKey o lanzan una excepción.
- Los errores de programación y validación de argumentos conservan TypeError o ValueError cuando esas excepciones estándar describen el problema.
- No se capturan indiscriminadamente excepciones para convertirlas en False.

Este contrato evita que un booleano oculte la causa, la etapa o la gravedad de un fallo.

## Jerarquía de excepciones
Todas las excepciones propias de la librería derivan de FsCryptographyError, que deriva de Exception.

- FsCryptographyError
  - InvalidPathError
  - UnsupportedResourceError
  - FormatError
    - UnsupportedFormatVersionError
  - AuthenticationError
  - KeyDerivationError
  - DestinationConflictError
  - NameConstraintError
  - BackendError
  - ClosedInstanceError
  - AtomicOperationError
    - RecoveryError

### Definiciones

- **FsCryptographyError:** clase base pública para los errores propios de fscryptography.
- **InvalidPathError:** la ruta o el componente proporcionado no puede utilizarse como entrada de la operación. No sustituye errores del sistema como FileNotFoundError.
- **UnsupportedResourceError:** el recurso existe, pero su tipo o condición no está admitido por la operación.
- **FormatError:** encabezado, framing, metadatos o estructura binaria malformados, incompletos o no reconocibles.
- **UnsupportedFormatVersionError:** versión mayor, menor o esquema que esta implementación no admite. Deriva de FormatError; no se intenta downgrade ni interpretación alternativa.
- **AuthenticationError:** fallo de autenticación AEAD, contraseña incorrecta al abrir un contenedor protegido, ciphertext alterado o flujo autenticado incompleto. No se debe revelar si el fallo del contenedor protegido se debió específicamente a contraseña incorrecta o a alteración.
- **KeyDerivationError:** fallo operativo del backend KDF al derivar una clave. No se utiliza para contraseña incorrecta ni para parámetros rechazados antes de ejecutar Argon2id.
- **DestinationConflictError:** el destino ya existe o no puede publicarse porque existe una colisión. No se sobrescribe el destino por defecto.
- **NameConstraintError:** nombre no representable, reservado o superior al límite aplicable del filesystem.
- **BackendError:** fallo inesperado de una dependencia criptográfica o de su integración que no sea un error de autenticación ni de formato.
- **ClosedInstanceError:** se intenta operar con una instancia de Crypto después de close().
- **AtomicOperationError:** fallo durante la publicación o durante la coordinación de cambios que impide asegurar el estado esperado de la operación.
- **RecoveryError:** fallo al ejecutar rollback o recuperación de una operación. Deriva de AtomicOperationError e indica que el estado puede requerir intervención o inspección externa.

## Excepciones estándar del sistema
Los errores ordinarios del filesystem deben conservar, siempre que sea posible, su tipo estándar de Python y su información causal. Entre ellos:

- FileNotFoundError
- FileExistsError
- PermissionError
- NotADirectoryError
- IsADirectoryError
- OSError

La librería no debe traducir indiscriminadamente todos los OSError a una excepción propia. Los conflictos semánticos de destino se expresan como DestinationConflictError; los errores reales de acceso e I/O permanecen como excepciones del sistema cuando sea posible.

Los errores de tipo o valor de argumentos siguen utilizando TypeError y ValueError, salvo que exista una categoría propia claramente más precisa.

## Reglas de clasificación

1. Validar límites y estructura antes de ejecutar operaciones costosas como Argon2id.
2. Rechazar versiones y parámetros no admitidos sin fallback ni downgrade.
3. Clasificar un contenedor protegido que no supera AES-GCM como AuthenticationError; no distinguir públicamente contraseña incorrecta de alteración autenticada.
4. Clasificar estructuras inválidas antes de la autenticación como FormatError.
5. Clasificar truncamiento o alteración de un flujo Streaming AEAD como AuthenticationError cuando el backend detecte fallo de autenticación.
6. No confundir una ruta inexistente con un formato inválido: conservar FileNotFoundError.
7. No confundir un destino existente con un error criptográfico: utilizar DestinationConflictError.
8. No utilizar BackendError como contenedor genérico de cualquier excepción.
9. Al traducir una excepción de dependencia, preservar la causa original mediante encadenamiento de excepciones (raise ... from exc).
10. No incluir contraseñas, claves, plaintext ni ciphertext completo en mensajes, atributos de error o logs.

## Operaciones atómicas y estado
Un fallo durante el procesamiento temporal que pueda limpiarse sin comprometer el original debe propagar su error específico, por ejemplo OSError, AuthenticationError o BackendError.

Utilizar AtomicOperationError cuando falle la publicación o la coordinación de cambios y no pueda garantizarse el estado final esperado. Utilizar RecoveryError cuando también falle el rollback o la recuperación.

No afirmar que una operación fue revertida si la recuperación no pudo confirmarse. El error debe permitir inspeccionar la cadena causal sin exponer material sensible.

## Estado
La jerarquía y la política de retornos/excepciones quedan definidas como contrato de la API v1. La implementación de las clases, sus exportaciones públicas y las pruebas de clasificación siguen pendientes.
