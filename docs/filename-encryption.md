# Cifrado de nombres

## Alcance
Se transforma un componente de nombre de ruta. No se explora ni recorre el directorio. Cifrar un directorio no modifica sus hijos.

## Requisitos
- Reversibilidad con la clave correspondiente.
- Autenticidad y detección de modificaciones.
- Metadatos autocontenidos; sin sidecars ni bases de datos.
- Clave separada de la destinada al contenido.
- Codificación válida en los filesystems soportados.
- Validación previa de longitud y colisiones.

## Construcción
Se prefiere AES-256-GCM con nonce único y autenticación. La representación debe transportar versión, nonce y ciphertext autenticado, o estructura equivalente. Los campos que intervengan en interpretación deben autenticarse.

## Codificación pendiente
Definir alfabeto permitido, prefijo/marcador, normalización Unicode, sensibilidad a mayúsculas, nombres reservados y reconocimiento de nombres ya cifrados. Deben excluirse separadores de ruta y NUL.

## Longitud y colisiones
El nombre cifrado puede superar el límite por componente. La operación debe detectarlo antes de modificar el recurso y fallar preservando el original. No truncar ciphertext ni usar sidecars en la primera versión.

No sobrescribir destinos existentes por defecto. La comprobación previa no elimina carreras con procesos externos; la publicación debe manejar colisiones reales.

## Extensión
Con encrypt_name=False, el nombre permanece visible y new_extension determina la extensión cifrada. Con encrypt_name=True, se cifra el nombre completo incluida la extensión original; esta se recupera de metadatos autenticados.

El cifrado no oculta jerarquía, cantidad de recursos ni otros metadatos del filesystem.
