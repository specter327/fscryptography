# Gestión de claves

## Terminología
master_key representa el material simétrico que el consumidor entrega a Crypto. No debe llamarse private_key, término asociado a criptografía asimétrica.

## API conceptual
    master_key = Crypto.generate()
    master_key = Crypto.generate(password="passphrase")
    master_key = Crypto.derive(text="passphrase")
    crypto = Crypto(master_key=master_key)

Crypto.generate(password=...) se plantea como alias de Crypto.derive(text=...).

## Representación
La API contempla una cadena Base64 para facilitar almacenamiento y transporte por el consumidor. No se debe asumir que representa directamente 32 bytes AES. Puede ser un contenedor versionado con keysets y, para derivación desde contraseña, salt, versión de KDF y parámetros.

El contenedor de claves es distinto del formato de cada archivo o nombre cifrado.

## Derivación
Argon2id deriva material a partir de contraseña y salt aleatorio. La salida, parámetros, versión y codificación final quedan pendientes de validación. La contraseña no debe persistirse dentro del contenedor.

## Separación
El material raíz no se utilizará directamente para múltiples propósitos. Se requieren claves separadas para contenido y nombres, mediante keysets independientes o separación de dominios reconocida.

## Responsabilidad del consumidor
La librería no administra almacenamiento, transporte, intercambio, backup, recuperación, rotación ni revocación. La pérdida de la clave implica pérdida práctica de acceso.

## Memoria
La instancia ofrecerá close() y administrador de contexto. Tras el cierre, las operaciones se rechazan. La limpieza es de mejor esfuerzo: Python no garantiza borrar todas las copias de secretos. __del__ no constituye garantía de borrado seguro.
