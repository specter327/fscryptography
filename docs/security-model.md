# Modelo de seguridad

## Activos
Confidencialidad del contenido, integridad/autenticidad del contenido, confidencialidad/integridad de nombres, material criptográfico y estado original de los recursos durante fallos.

## Adversario
Se busca proteger frente a quien obtiene archivos y nombres cifrados sin sus claves y detectar alteraciones del ciphertext y metadatos autenticados. No se asume que el host esté libre de malware, depuradores privilegiados, captura de memoria o compromiso del proceso.

## Garantías previstas
Sujetas a validación e implementación correcta:
- Confidencialidad mediante cifrado simétrico moderno.
- Integridad y autenticidad mediante AEAD.
- Detección de corrupción/truncamiento conforme al Streaming AEAD.
- Autenticación de metadatos que afecten al descifrado.
- No publicar plaintext parcial como resultado definitivo.
- Separación de claves de contenido y nombres.

## Limitaciones
No se ocultan tamaño ni overhead, cantidad de recursos, estructura de directorios, timestamps, permisos, propietarios, patrones de acceso ni necesariamente longitudes aproximadas de nombres. La librería no protege contra eliminación o pérdida del ciphertext. Perder la clave implica perder acceso práctico.

## Riesgos
Reutilización de nonce GCM; reutilización de claves entre dominios; publicación prematura de plaintext; parsing ambiguo; carreras y colisiones de filesystem; temporales con permisos excesivos; filtración de secretos; supuestos erróneos sobre atomicidad.

## Contraseñas y memoria
Argon2id utilizará salt aleatorio y parámetros adecuados. Los costes predeterminados requieren validación. Python no garantiza borrado seguro de secretos; close() solo puede ofrecer limpieza de mejor esfuerzo.

## No objetivos
No es un filesystem cifrado transparente, gestor de secretos, sistema de intercambio de claves, herramienta de anonimización ni solución para ocultar metadatos.
