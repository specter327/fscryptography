# API pública

## Principios
La API opera sobre rutas del filesystem. No expone cifrado general de bytes ni streams suministrados por el consumidor. Las firmas siguientes son conceptuales hasta cerrar tipos, excepciones y parámetros.

## Generación y derivación
    master_key = Crypto.generate()
    master_key = Crypto.generate(password="passphrase")
    master_key = Crypto.derive(text="passphrase")

generate(password=...) será alias de derive(text=...). Sin contraseña se genera material aleatorio; con contraseña se deriva mediante Argon2id.

## Inicialización
    crypto = Crypto(master_key=master_key)
    with Crypto(master_key=master_key) as crypto:
        ...

La instancia ofrecerá close() y rechazará operaciones tras el cierre. La limpieza de secretos es de mejor esfuerzo.

## Archivos
    crypto.file.encrypt(
        path="document.txt",
        new_extension=".encrypted",
        encrypt_name=False,
    )
    crypto.file.decrypt(path="document.txt.encrypted")

path identifica el archivo. new_extension determina la extensión visible cuando el nombre permanece sin cifrar. encrypt_name indica si se cifra el nombre completo, incluida extensión original.

## Directorios
    crypto.dir.encrypt(path="private-directory")
    crypto.dir.decrypt(path="encrypted-directory")

Estas operaciones transforman exclusivamente el nombre del directorio.

## Contrato pendiente
Definir si generate es método estático o de clase; soporte de PathLike; normalización de new_extension; retorno bool frente a excepciones/resultados estructurados; comportamiento ante operaciones repetidas; concurrencia y uso desde múltiples hilos/tareas.

Un booleano por sí solo no comunica causa ni etapa del fallo. La API debe ofrecer errores tipados y no ocultar fallos inesperados.
