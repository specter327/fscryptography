# API pública

## Principios

La API opera sobre rutas del filesystem. No expone cifrado general de bytes ni streams suministrados por el consumidor. La clave maestra se representa públicamente como texto Base64 estándar y se decodifica a bytes al entrar en la librería.

## Generación de clave maestra

    import fscryptography

    # Generación aleatoria
    master_key = fscryptography.generate()

    # Generación de keysets protegidos por contraseña
    master_key = fscryptography.generate(password="passphrase")

Ambas variantes devuelven una cadena Base64 canónica. La cadena representa el contenedor autocontenido MasterKey; no representa una clave AES plana. La variante con contraseña protege el contenedor mediante Argon2id y AES-256-GCM.

## Gestor y contexto criptográfico

    manager = fscryptography.Manager(key=master_key)

    # Para un contenedor protegido:
    manager = fscryptography.Manager(
        key=master_key,
        password="passphrase",
    )

    with fscryptography.Manager(key=master_key) as manager:
        ...

El gestor decodifica Base64 a bytes, valida y abre el contenedor una sola vez, y conserva en su contexto las primitivas Tink independientes para contenido y nombres. Las operaciones posteriores reutilizan ese contexto; no reciben la clave en cada llamada.

Si el contenedor fue generado con password=..., la contraseña debe suministrarse al construir el gestor. La contraseña se consume durante la apertura y no se conserva en el objeto. Esto es obligatorio para mantener el contrato MasterKey protegido ya aprobado; no es posible abrirlo únicamente con la cadena Base64.

## Cambio y exportación de clave

    manager.change_key(new_key)

    # Para una nueva clave protegida:
    manager.change_key(new_key, password="new passphrase")

    exported_key: str = manager.export_key()

change_key() valida y abre completamente la nueva clave antes de sustituir el contexto activo. Si falla, el contexto anterior permanece intacto. export_key() devuelve la representación Base64 canónica de la clave activa.

## Operaciones sobre recursos

    # Nombre visible: salida document.fscrypt
    manager.file.encrypt(path="document.txt")

    # Extensión de salida personalizada o sin extensión
    manager.file.encrypt(path="archive.tar.gz", new_extension=".locked")
    manager.file.encrypt(path="secret.txt", new_extension="")

    # El nombre completo se cifra con el keyset AEAD de nombres
    manager.file.encrypt(path="private.txt", encrypt_name=True)

    manager.file.decrypt(path="document.fscrypt")

    # Los directorios solo transforman su propio nombre
    manager.dir.encrypt(path="private-directory")
    manager.dir.decrypt(path="~1...")

Las operaciones son métodos del contexto del gestor y reutilizan las primitivas abiertas. El cifrado de archivos utiliza Tink Streaming AEAD y la cabecera v1.0 autenticada como AAD. La extensión original y la de salida se guardan en metadata autenticada. `new_extension=None` selecciona `.fscrypt`; `""` elimina la extensión visible; un sufijo explícito como `.locked` la sustituye. Con `encrypt_name=True`, se cifra el nombre completo y `new_extension` debe ser `None`. Los directorios transforman exclusivamente su propio nombre; no recorren ni cifran su contenido.

## Representación de claves

- Frontera pública: Base64 estándar ASCII (str).
- Interior de la librería: contenedor binario (bytes) y primitivas criptográficas abiertas.
- Exportación: serialización de los bytes internos a Base64 estándar.
- La codificación Base64 no es cifrado ni protección de secretos.

El gestor no conserva la contraseña. close() invalida el contexto y libera referencias a la clave y las primitivas; el borrado seguro de memoria no está garantizado por Python.

## Retornos y errores

Las operaciones file.encrypt(), file.decrypt(), dir.encrypt() y dir.decrypt() devolverán None al completarse correctamente. Los fallos se comunicarán mediante excepciones tipadas; no se devolverá False como sustituto de una excepción.

Todas las excepciones propias derivan de FsCryptographyError. La jerarquía, la clasificación de fallos y la política de preservación de excepciones estándar se definen en [Errores y excepciones](errors.md).

Los errores de argumentos conservan TypeError o ValueError; los errores ordinarios del filesystem conservan las excepciones estándar de Python cuando sea posible. La contraseña incorrecta y la alteración de un contenedor protegido se presentan como AuthenticationError, sin distinguir públicamente ambos casos.

## Estado de implementación

Implementado:
- fscryptography.generate(password=None).
- fscryptography.Manager(key, password=None).
- Decodificación Base64 a bytes para el contexto interno.
- Reutilización de primitivas abiertas por el gestor.
- Manager.change_key() con sustitución atómica del contexto.
- Manager.export_key() a Base64.
- close() y administrador de contexto.

Pendiente:
- Pruebas de conformidad ampliadas, vectores golden y validación de mutaciones.
- Validación de atomicidad/no-sobrescritura y round-trip en Windows/NTFS y GNU/Linux/ext4 reales.
