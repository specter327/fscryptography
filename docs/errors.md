# Errores y excepciones

## Principios
Los errores deben ser explícitos, clasificables y no ambiguos. No se deben ocultar fallos del filesystem ni errores de autenticación. No incluir claves, contraseñas, plaintext ni ciphertext completo en mensajes o logs.

## Categorías propuestas
- ConfigurationError: clave malformada, versión de contenedor no soportada o parámetros inválidos.
- KeyDerivationError: fallo o parámetros inválidos de Argon2id.
- InvalidPathError / UnsupportedResourceError: ruta inválida o tipo no admitido.
- PermissionError: permisos insuficientes o recurso bloqueado.
- FormatError: formato desconocido o malformado.
- AuthenticationError: tag inválido, segmento alterado, truncamiento o fallo de autenticación.
- DestinationConflictError: destino existente o colisión.
- NameConstraintError: nombre no representable o que excede límites.
- BackendError: fallo del backend criptográfico.
- AtomicOperationError / RecoveryError: fallo de publicación, rollback o recuperación.

Los nombres concretos y herencia de clases son propuestas, no contrato definitivo.

## Política
- No sobrescribir destinos existentes por defecto.
- No publicar plaintext antes de autenticar el flujo completo.
- No borrar el original antes de confirmar publicación.
- Limpiar temporales en errores controlables.
- Preservar la excepción original como causa al traducirla.
- No convertir indiscriminadamente todos los errores en False.
- No registrar secretos ni datos sensibles.

## Retornos
El diseño inicial contempla bool, pero la especificación debe resolver si los errores se expresan mediante excepciones tipadas o resultados estructurados. Un booleano silencioso es insuficiente para una librería de seguridad.
