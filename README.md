# fscryptography

**fscryptography** (*filesystem-cryptography*) es una librería Python autónoma para cifrar y descifrar archivos y nombres de archivos y directorios de un sistema de archivos.

Su objetivo es proporcionar una API de alto nivel para operaciones criptográficas sobre recursos identificados mediante rutas, manteniendo la implementación independiente de herramientas de exploración, bibliotecas de representación de recursos y aplicaciones concretas.

> **Estado:** diseño en consolidación. Esta documentación describe el alcance y las decisiones arquitectónicas acordadas; los formatos binarios y algunos detalles de implementación siguen pendientes de validación.

## 1. Alcance y responsabilidades

fscryptography opera directamente sobre recursos del sistema de archivos mediante rutas y operaciones estándar multiplataforma, como `open()` y las interfaces de `os`.

La librería se responsabiliza de:

- Cifrar y descifrar el contenido de archivos.
- Cifrar y descifrar nombres de archivos.
- Cifrar y descifrar nombres de directorios.
- Gestionar internamente el procesamiento segmentado de archivos grandes.
- Mantener la información necesaria para recuperar los recursos en el propio contenido cifrado o nombre cifrado.

No forma parte de su responsabilidad:

- Explorar o descubrir directorios y recursos.
- Realizar búsquedas, filtros o recorridos recursivos.
- Ejecutar operaciones por lotes o administrar colecciones de recursos.
- Proporcionar una API pública para cifrar bytes arbitrarios o trabajar con streams suministrados por el consumidor.
- Administrar el almacenamiento, transporte o recuperación externa de claves.
- Depender de `fsresource-tree` o de cualquier otro proyecto.

El procesamiento segmentado es un mecanismo interno para limitar el uso de memoria; no constituye una API pública de streams.

### Directorios

Las operaciones sobre directorios afectan exclusivamente a su nombre. fscryptography no recorre el directorio ni cifra su contenido.

El consumidor puede combinar fscryptography con una herramienta externa de exploración y orquestación —por ejemplo, `fsresource-tree`—, pero esa integración queda fuera de esta librería. fscryptography recibe rutas y no necesita conocer el origen de estas.

## 2. Modelo criptográfico

### Cifrado de contenido

El diseño utiliza criptografía simétrica para el contenido de los archivos. La decisión de diseño es emplear **AES-256-GCM**, con autenticación e integridad además de confidencialidad.

Los archivos se procesan secuencialmente mediante cifrado autenticado segmentado. Esto permite trabajar con archivos grandes sin cargar su contenido completo en memoria.

- Tamaño de segmento predeterminado: **1 MiB**.
- El tamaño podrá configurarse por el consumidor, dentro de los perfiles que admita el backend criptográfico elegido.
- La unidad interna de segmentación y el overhead criptográfico del backend no tienen por qué coincidir exactamente con 1 MiB de texto plano.

No se implementarán primitivas ni protocolos criptográficos propios: se utilizarán bibliotecas consolidadas y mantenidas.

### Backend criptográfico

**Google Tink** es el candidato prioritario para las primitivas y el formato de cifrado autenticado segmentado. Su plantilla `AES256_GCM_HKDF_1MB` es especialmente relevante para el perfil predeterminado planteado.

La selección definitiva requiere validar la API Python disponible, los perfiles de segmentación admitidos y la interoperabilidad del formato. No se presupone que el backend permita tamaños arbitrarios de segmento.

La intención para la primera versión es mantener una sola familia de algoritmos, un formato y un backend robusto, en lugar de introducir una arquitectura de backends intercambiables.

Referencias técnicas:

- [Google Tink](https://github.com/tink-crypto/tink)
- [Tink — Streaming AEAD](https://developers.google.com/tink/streaming-aead)
- [Tink — Deterministic AEAD](https://developers.google.com/tink/deterministic-aead)
- [Tink — Supported key types](https://developers.google.com/tink/supported-key-types)

## 3. Claves y derivación

La API conceptual contempla dos formas de obtener material criptográfico:

```python
# Generación aleatoria
master_key = Crypto.generate()

# Derivación a partir de una contraseña
master_key = Crypto.generate(password="a long passphrase")

# API de derivación equivalente
master_key = Crypto.derive(text="a long passphrase")

# Inicialización
crypto = Crypto(master_key=master_key)
```

`Crypto.generate(password=...)` se plantea como alias de `Crypto.derive(text=...)`.

La clave se representa como una cadena codificada en Base64 para facilitar su almacenamiento y transporte por parte del consumidor. La representación puede contener un contenedor versionado con el material criptográfico y los parámetros necesarios, y no debe asumirse que sea simplemente la codificación Base64 de una clave AES en bruto.

Para derivar material desde contraseñas se ha definido **Argon2id** como KDF. La sal y los parámetros necesarios para reproducir la derivación deben conservarse en la representación correspondiente. La compatibilidad concreta entre Argon2id y el backend de cifrado debe resolverse integrando una implementación fiable de Argon2id cuando sea necesario; no se presupone que Tink Python proporcione esa KDF.

Las claves destinadas a cifrar contenido y nombres no deben reutilizarse directamente. Se requiere separación criptográfica de claves o derivación de subclaves con separación de dominios, de forma compatible con el modelo de gestión de claves elegido.

fscryptography no administra dónde se guarda la clave ni cómo se comparte. Esa responsabilidad pertenece al consumidor.

## 4. Cifrado de nombres

El cifrado de nombres debe permitir recuperar el nombre original utilizando la clave original, sin depender de una base de datos, archivo sidecar o metadatos externos.

El diseño favorece cifrado autenticado con AES-256-GCM también para los nombres, utilizando material de clave separado del empleado para el contenido. Cada nombre cifrado debe transportar la información necesaria para su descifrado, incluido el nonce y la información de autenticación correspondiente.

La representación debe ser compatible con las restricciones de nombres de los sistemas de archivos. Se debe contemplar que:

- El nombre cifrado puede ser considerablemente más largo que el original.
- El nombre resultante puede exceder el límite permitido por el sistema de archivos.
- Deben detectarse colisiones y nombres de destino incompatibles antes de modificar el recurso.
- La codificación debe utilizar caracteres válidos para los sistemas de archivos soportados.

Cifrar nombres no oculta la cantidad de recursos, la jerarquía de directorios, los tamaños de archivo ni otros metadatos observables del sistema de archivos.

## 5. Metadatos autocontenidos

El descifrado debe requerir únicamente la clave original y el recurso cifrado. Por tanto, todo parámetro necesario para interpretar y recuperar el contenido o nombre debe acompañar al recurso transformado y estar protegido criptográficamente.

Para los archivos, se utilizará el formato autenticado que proporcione el backend de cifrado segmentado, evitando envolverlo innecesariamente en un protocolo propio. Si se requieren metadatos adicionales —por ejemplo, versión, tipo de recurso o extensión original—, deberán ser mínimos y quedar autenticados como parte del formato o mediante datos asociados autenticados (AAD).

Cuando se cifra el nombre completo de un archivo, también queda cifrada su extensión original. Esta deberá poder recuperarse a partir de los metadatos autenticados del recurso.

Los formatos binarios y la estructura final de los nombres cifrados permanecen pendientes de definición.

## 6. Operaciones atómicas

Las operaciones deben proteger el recurso original frente a fallos durante el procesamiento. La estrategia prevista es trabajar sobre un recurso temporal y publicar el resultado únicamente cuando la operación haya terminado correctamente.

Para archivos, el flujo conceptual es:

1. Leer el recurso original sin modificarlo.
2. Crear un temporal en el mismo directorio y filesystem.
3. Procesar el contenido por segmentos hacia el temporal.
4. Completar y validar el formato autenticado, incluido su registro final cuando corresponda.
5. Preparar el nombre de destino y comprobar colisiones.
6. Publicar el resultado y retirar el original únicamente después de confirmar la operación.

En el descifrado, el texto plano no debe publicarse como resultado definitivo hasta que se haya validado la autenticidad de todos los segmentos y del registro final.

`os.replace()` puede proporcionar publicación atómica de un archivo dentro del mismo filesystem. Sin embargo, no convierte por sí solo una secuencia de cambios sobre contenido y nombre en una transacción indivisible, ni garantiza durabilidad frente a una pérdida súbita de energía. Para cubrir esos escenarios pueden ser necesarios sincronización explícita (`flush`, `fsync`) y mecanismos de recuperación.

Por tanto, el objetivo es garantizar publicación atómica y rollback ante errores controlables. Una garantía transaccional universal frente a interrupciones abruptas, fallos del hardware o cambios múltiples requiere una estrategia adicional de recuperación, todavía por definir.

Por defecto, no se sobrescribirán destinos existentes: una colisión debe producir un error sin alterar el original.

## 7. Gestión de memoria

La instancia debe minimizar la permanencia del material de clave en memoria y ofrecer un mecanismo explícito de cierre, preferiblemente mediante `close()` y soporte de administrador de contexto.

La limpieza al cerrar o destruir la instancia será de mejor esfuerzo. Python no garantiza el borrado físico e inmediato de todas las copias de un secreto en memoria; por ello, fscryptography no prometerá una eliminación segura absoluta mediante `__del__` ni mediante la liberación ordinaria de objetos.

## 8. API conceptual

La interfaz pública prevista se centra en operaciones sobre rutas:

```python
# Generación de material criptográfico
master_key = Crypto.generate()
master_key = Crypto.generate(password="passphrase")

# Inicialización
crypto = Crypto(master_key=master_key)

# Archivos
crypto.file.encrypt(
    path="document.txt",
    new_extension=".encrypted",
    encrypt_name=False,
)

crypto.file.decrypt(path="document.txt.encrypted")

# Directorios: únicamente se transforma el nombre
crypto.dir.encrypt(path="private-directory")
crypto.dir.decrypt(path="encrypted-directory")
```

### Parámetros de cifrado de archivos

- `path`: ruta del archivo que se procesará.
- `new_extension`: extensión que se agregará o sustituirá en el nombre visible del archivo cifrado.
- `encrypt_name`: indica si también se cifra el nombre completo, incluida la extensión original.

Cuando `encrypt_name=False`, el nombre permanece visible y `new_extension` determina la extensión del archivo cifrado. Cuando `encrypt_name=True`, el nombre completo se cifra y la extensión original debe recuperarse durante el descifrado a partir de la información autenticada.

Las operaciones se plantean con retorno booleano para indicar éxito o fallo; el contrato definitivo de errores y excepciones deberá especificarse durante la implementación.

## 9. Integración con otras librerías

fscryptography es independiente de `fsresource-tree`.

Una aplicación puede utilizar una librería de exploración para descubrir y ordenar recursos, y después invocar fscryptography con las rutas correspondientes. La orquestación de colecciones, el recorrido recursivo y el orden de procesamiento pertenecen a esa capa externa.

Cuando se cifran nombres de directorios, el consumidor debe considerar que las rutas de sus descendientes cambian. Para procesar un árbol completo, normalmente será necesario cifrar primero los archivos y directorios descendientes y renombrar los directorios padres al final, manteniendo o recalculando las rutas conforme cambien.

## 10. Evolución futura

La criptografía asimétrica no forma parte del alcance inicial. Su posible incorporación se reserva para el intercambio o la protección de claves simétricas.

En un esquema híbrido futuro, el contenido continuaría cifrándose con una clave simétrica eficiente; la clave pública del destinatario protegería esa clave, y la clave privada correspondiente permitiría recuperarla. No se pretende utilizar criptografía asimétrica para cifrar directamente archivos grandes.

## 11. Estado del diseño

| Área | Estado |
|---|---|
| Identidad y alcance de fscryptography | Definidos |
| Operaciones mediante rutas del filesystem | Definidas |
| Ausencia de API pública de bytes/streams | Definida |
| Independencia de fsresource-tree | Definida |
| AES-256-GCM para contenido | Decisión de diseño |
| Procesamiento autenticado segmentado | Definido |
| Segmento predeterminado de 1 MiB | Definido |
| Argon2id para derivación desde contraseña | Decisión de diseño |
| Google Tink como backend | Candidato prioritario, pendiente de validación |
| Clave representada en Base64 y parámetro master_key | Definidos conceptualmente |
| Metadatos autocontenidos y autenticados | Requisito definido |
| Separación de claves para contenido y nombres | Requisito definido |
| Atomicidad y rollback ante errores controlables | Requisito definido; recuperación pendiente |
| Limpieza de claves en memoria | Mejor esfuerzo |
| Formatos binarios definitivos | Pendientes |
| Contrato definitivo de errores y excepciones | Pendiente |
| Intercambio asimétrico de claves | Evolución futura |

---

**fscryptography** busca mantener una responsabilidad acotada: proporcionar operaciones criptográficas fiables sobre recursos del sistema de archivos, sin asumir la exploración, administración ni orquestación de esos recursos.
