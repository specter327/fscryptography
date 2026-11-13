# Gestión de claves

## Terminología

`master_key` representa el contenedor autocontenido de material criptográfico raíz que el consumidor entrega a `Crypto`. No debe llamarse `private_key`, término asociado a criptografía asimétrica.

## API

```python
# Material aleatorio
master_key = Crypto.generate()
crypto = Crypto(master_key=master_key)

# Material protegido mediante contraseña
master_key = Crypto.generate(password="passphrase")
crypto = Crypto(master_key=master_key, password="passphrase")

# Alias explícito de generación protegida
master_key = Crypto.derive(text="passphrase")
crypto = Crypto(master_key=master_key, password="passphrase")
```

`Crypto.generate(password=...)` es un alias de `Crypto.derive(text=...)`. Ambos producen un contenedor de claves protegido por contraseña. La contraseña es necesaria cada vez que se inicializa `Crypto` desde ese contenedor.

## Modelo de clave

La salida pública es una representación autocontenida y versionada de `MasterKey`, codificada en Base64 estándar con padding. La cadena Base64 es una codificación de transporte, no una protección criptográfica. No debe asumirse que representa directamente 32 bytes AES.

El contenedor contiene keysets independientes para las operaciones criptográficas de contenido y nombres. En el modo protegido, el payload que contiene esos keysets se cifra y autentica. La contraseña no se almacena.

`MasterKey` es opaco para el consumidor: no expone keysets, claves derivadas, nonces internos ni detalles del backend. El contenedor de claves es distinto del formato de cada archivo o nombre cifrado.

La estructura lógica y la propuesta de disposición binaria v1 se especifican en [Formato de MasterKey](master-key-format.md). Los casos de conformidad previstos están en [Plan de pruebas del formato MasterKey](master-key-format-test-plan.md). La propuesta de layout aún requiere aprobación y cierre de sus límites criptográficos antes de implementar.

## Generación aleatoria

`Crypto.generate()` crea keysets criptográficos con generadores seguros y serializa el material secreto en un contenedor versionado. El payload del modo aleatorio no está protegido por contraseña ni cifrado por una clave de envoltura. La seguridad de este modo depende de proteger el propio valor `master_key`.

La codificación Base64 no oculta ni protege el material secreto. El consumidor debe tratar el valor como una credencial secreta.

## Derivación y protección mediante contraseña

`Crypto.derive(text=...)` genera keysets criptográficos aleatorios y los protege mediante una clave de envoltura derivada de la contraseña con Argon2id y un salt aleatorio.

El contenedor protegido debe incluir, como mínimo:

- Identificador y versión del formato del contenedor.
- Identificador y versión de la KDF.
- Salt de Argon2id.
- Parámetros de coste necesarios para reproducir la derivación.
- Identificador del algoritmo AEAD de envoltura.
- Nonce de la operación AEAD de protección.
- Ciphertext autenticado que contiene los keysets serializados.

Los campos de cabecera que controlan la interpretación del contenedor deben autenticarse como AAD. El algoritmo AEAD concreto y sus parámetros se fijarán al validar las dependencias; no se implementarán primitivas propias.

`Crypto(master_key=..., password=...)` deriva la clave de protección y abre el contenedor. Una contraseña incorrecta, un contenedor alterado o uno malformado debe producir un error de inicialización; nunca debe generar silenciosamente keysets nuevos.

La contraseña se interpreta como texto UTF-8. La política exacta de normalización Unicode y los límites de longitud deben fijarse antes de implementar. La contraseña nunca se persiste dentro del contenedor.

## Separación

Los keysets de contenido y nombres son independientes. No se reutiliza directamente una misma clave AEAD para ambos propósitos. La separación se realiza mediante keysets generados independientemente por el backend criptográfico.

## Responsabilidad del consumidor

La librería no administra almacenamiento, transporte, intercambio, backup, recuperación, rotación ni revocación. El consumidor debe conservar el contenedor `MasterKey` y, cuando esté protegido, la contraseña. Perder cualquiera de los elementos requeridos implica pérdida práctica de acceso.

## Memoria

La instancia ofrecerá `close()` y administrador de contexto. Tras el cierre, las operaciones se rechazan. La limpieza es de mejor esfuerzo: Python no garantiza borrar todas las copias de secretos. `__del__` no constituye garantía de borrado seguro.
