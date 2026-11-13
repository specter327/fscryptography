# API pública

## Principios
La API opera sobre rutas del filesystem. No expone cifrado general de bytes ni streams suministrados por el consumidor. Las firmas siguientes son conceptuales hasta cerrar tipos, excepciones y parámetros.

## Generación y derivación
```python
# Genera material criptográfico aleatorio
master_key = Crypto.generate()
crypto = Crypto(master_key=master_key)

# Genera material criptográfico y protege el contenedor con contraseña
master_key = Crypto.generate(password="passphrase")
crypto = Crypto(master_key=master_key, password="passphrase")

# Equivalente explícito
master_key = Crypto.derive(text="passphrase")
crypto = Crypto(master_key=master_key, password="passphrase")
```

Crypto.generate(password=...) es alias de Crypto.derive(text=...). Ambos generan keysets criptográficos y devuelven un contenedor MasterKey protegido mediante una clave derivada de la contraseña con Argon2id.

La contraseña es necesaria cada vez que se inicializa Crypto con un contenedor protegido. No se almacena en MasterKey. La inicialización de un contenedor aleatorio generado sin contraseña no requiere argumento password.

## Inicialización
```python
# Contenedor aleatorio
crypto = Crypto(master_key=master_key)

# Contenedor protegido
crypto = Crypto(master_key=master_key, password="passphrase")

with Crypto(master_key=master_key, password="passphrase") as crypto:
    ...
```

Si el contenedor está protegido, omitir password debe producir un error de inicialización. Una contraseña incorrecta, un contenedor alterado o uno malformado también debe producir un error; nunca se regenerarán claves silenciosamente.

La instancia ofrecerá close() y rechazará operaciones tras el cierre. La limpieza de secretos es de mejor esfuerzo.

## Archivos
```python
crypto.file.encrypt(
    path="document.txt",
    new_extension=".encrypted",
    encrypt_name=False,
)
crypto.file.decrypt(path="document.txt.encrypted")
```

path identifica el archivo. new_extension determina la extensión visible cuando el nombre permanece sin cifrar. encrypt_name indica si se cifra el nombre completo, incluida extensión original.

## Directorios
```python
crypto.dir.encrypt(path="private-directory")
crypto.dir.decrypt(path="encrypted-directory")
```

Estas operaciones transforman exclusivamente el nombre del directorio.

## Contrato pendiente
Definir si generate es método estático o de clase; soporte de PathLike; normalización de new_extension; retorno bool frente a excepciones/resultados estructurados; comportamiento ante operaciones repetidas; concurrencia y uso desde múltiples hilos/tareas; normalización Unicode y límites de longitud de contraseña; algoritmo concreto de protección AEAD del contenedor.

Un booleano por sí solo no comunica causa ni etapa del fallo. La API debe ofrecer errores tipados y no ocultar fallos inesperados.
