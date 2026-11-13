# fscryptography — Presentación del proyecto

> Cifrado autenticado orientado al sistema de archivos para Python.

## Propósito

fscryptography proporciona una API compacta basada en rutas para proteger el contenido de archivos regulares y los nombres del filesystem. Está diseñada para integrarse en aplicaciones de nivel superior sin acoplar las operaciones criptográficas a una interfaz de usuario o flujo de trabajo específico.

## Modelo de funcionamiento

1. **Ciclo de vida de claves:** generar o abrir un contenedor MasterKey versionado, opcionalmente protegido mediante contraseña.
2. **Operaciones sobre recursos:** cifrar/descifrar archivos regulares por segmentos y cifrar/descifrar nombres individuales.
3. **Observabilidad transaccional:** conservar journals y exponer inspección de solo lectura para operaciones interrumpidas.

## Límites operativos

- Una operación sobre un archivo protege su contenido y metadata autenticada.
- El cifrado de nombres oculta el nombre completo.
- Una operación sobre un directorio modifica únicamente su propio nombre.
- Los descendientes nunca se recorren ni cifran implícitamente.
- La inspección de recuperación informa del journal; no ejecuta recuperación destructiva ni limpieza.

## Composición criptográfica

| Propósito | Primitiva |
|---|---|
| Contenido de archivos | Google Tink Streaming AEAD — AES256_GCM_HKDF_1MB |
| Nombres del filesystem | Google Tink AEAD — AES256_GCM |
| Protección de clave por contraseña | Argon2id v19 + AES-256-GCM |
| Separación de claves | Keysets independientes para contenido y nombres |

## API pública

~~~python
import fscryptography

master_key = fscryptography.generate()
with fscryptography.Manager(key=master_key) as manager:
    manager.file.encrypt("informe.txt")
    manager.file.decrypt("informe.fscrypt")
    manager.file.encrypt("privado.txt", encrypt_name=True)
    manager.dir.encrypt("directorio-privado")
    records = manager.inspect_recovery("/datos")
~~~

Consulta el [manual de uso](../README.md#manual-de-uso-de-la-api) y la [referencia normativa](api-reference.md).

## Madurez actual

La versión 0.1.0 es una distribución alpha. La API, el diseño criptográfico, el empaquetamiento, la documentación y las pruebas de base están establecidos. Las pruebas de inyección de fallos, recuperación tras interrupciones, casos límite del filesystem y validación multiplataforma ampliada siguen siendo fronteras activas de endurecimiento.

No se declara una auditoría criptográfica independiente. Las garantías específicas de plataforma se describen en [compatibilidad](platform-compatibility.md).

## Integración prevista

fscryptography es un componente de bajo nivel. La aplicación consumidora sigue siendo responsable de seleccionar rutas, administrar respaldos y ciclo de vida de MasterKeys, gestionar flujos de usuario y mantener controles de acceso del sistema operativo.
