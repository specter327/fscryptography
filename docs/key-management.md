# Gestión de claves

## Terminología

master_key representa el contenedor autocontenido de material criptográfico raíz. La API pública lo transporta como Base64 estándar; internamente el gestor conserva su representación binaria y las primitivas abiertas. No debe llamarse private_key, término asociado a criptografía asimétrica.

## API pública

    import fscryptography

    # Material aleatorio
    master_key = fscryptography.generate()
    manager = fscryptography.Manager(key=master_key)

    # Contenedor protegido mediante contraseña
    protected_key = fscryptography.generate(password="passphrase")
    manager = fscryptography.Manager(
        key=protected_key,
        password="passphrase",
    )

    # Cambio de contexto
    manager.change_key(master_key)
    exported = manager.export_key()

generate() devuelve siempre una cadena Base64 canónica. Manager recibe esa representación, la decodifica a bytes, valida el contenedor y abre los keysets Tink. Las operaciones criptográficas posteriores deben reutilizar las primitivas almacenadas en el gestor, sin volver a solicitar la clave en cada llamada.

## Contraseña del contenedor protegido

La contraseña es necesaria cada vez que se abre un contenedor protegido. Por tanto, debe proporcionarse a Manager(key=..., password=...) y también a change_key(..., password=...) cuando la nueva clave esté protegida. Se consume durante la apertura y no se almacena en el objeto.

La cadena Base64 por sí sola no permite recuperar el contenido de un contenedor protegido. No se debe almacenar la contraseña dentro del gestor ni alterar el formato MasterKey aprobado para eludir este requisito.

## Representación

- Entrada/salida pública: Base64 estándar ASCII como str.
- Representación interna del contenedor: bytes binarios.
- Contexto operativo: primitivas Tink abiertas para contenido y nombres.
- Exportación: Manager.export_key() vuelve a codificar los bytes internos a Base64.
- Cambio: Manager.change_key() abre y valida la nueva clave antes de reemplazar el contexto. Ante un error, conserva intacto el contexto anterior.

Base64 es una codificación de transporte, no una protección criptográfica. No debe asumirse que el valor representa directamente 32 bytes AES.

## Modelo criptográfico

El contenedor contiene keysets independientes para las operaciones criptográficas de contenido y nombres. En el modo protegido, el payload que contiene esos keysets se cifra y autentica. La estructura binaria v1 aprobada se especifica en [Formato de MasterKey](master-key-format.md); el perfil Argon2id y los límites de apertura se definen en [la política Argon2id](argon2id-policy.md).

La generación aleatoria crea keysets Tink independientes para contenido y nombres. El payload del modo aleatorio no está protegido por contraseña ni cifrado por una clave de envoltura. La seguridad de este modo depende de proteger el propio valor master_key.

El perfil Argon2id v1 utiliza versión 19, memoria 65.536 KiB, 3 iteraciones, paralelismo 1, salt de 16 bytes y salida de 32 bytes. El parser acepta exactamente ese perfil y rechaza cualquier otra combinación antes de ejecutar Argon2id.

Los keysets de contenido y nombres son independientes. El keyset de contenido produce una primitiva Tink Streaming AEAD con la plantilla AES256_GCM_HKDF_1MB; el keyset de nombres produce una primitiva Tink AEAD con la plantilla AES256_GCM.

## Ciclo de vida

Manager.close() invalida la instancia y libera referencias a los bytes de la clave y a las primitivas. El administrador de contexto llama a close() al salir. La limpieza es de mejor esfuerzo: Python no garantiza borrar todas las copias de secretos en memoria. __del__ no constituye garantía de borrado seguro.

## Estado de implementación

El módulo interno `fscryptography._master_key` implementa la generación y apertura del contenedor binario v1.0, incluidos los dos keysets Tink, framing, Base64 estricto, Argon2id con el perfil aprobado y AES-256-GCM para proteger el contenedor.

La API pública implementa `fscryptography.generate()`, `Manager`, cambio de clave, exportación Base64 y ciclo de vida. Las operaciones de archivo y directorio están integradas con las primitivas criptográficas y el filesystem: cifrado/descifrado segmentado de archivos, transformación de nombres, temporales transaccionales, publicación sin reemplazo y journal persistente con inspección de solo lectura.

La validación integral de las garantías de filesystem sigue pendiente en la matriz de plataformas objetivo. La implementación no implica que NTFS, ext4, todas las configuraciones de Windows o GNU/Linux hayan superado pruebas exhaustivas.

## Responsabilidad del consumidor

La librería no administra almacenamiento, transporte, intercambio, backup, recuperación, rotación ni revocación. El consumidor debe conservar el contenedor MasterKey y, cuando esté protegido, la contraseña. Perder cualquiera de los elementos requeridos implica pérdida práctica de acceso.
