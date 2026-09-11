# Sistema de gestión de heladería

Aplicación Django para punto de venta, inventario, caja, clientes y reportes.

## Desarrollo

Requiere Python compatible con Django 6 y un entorno virtual.

```powershell
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe manage.py migrate
venv\Scripts\python.exe manage.py crear_roles_base
venv\Scripts\python.exe manage.py createsuperuser
venv\Scripts\python.exe manage.py runserver
```

En desarrollo se usa SQLite y una clave efímera. Las sesiones se invalidan al reiniciar el proceso si no se define `DJANGO_SECRET_KEY`.

## Pruebas y validación

```powershell
venv\Scripts\python.exe manage.py check
venv\Scripts\python.exe manage.py makemigrations --check --dry-run
venv\Scripts\python.exe manage.py test
```

## Producción

1. Copiar `.env.example` a la configuración secreta del servidor; Django no carga archivos `.env` automáticamente.
2. Generar una clave con `python -c "import secrets; print(secrets.token_urlsafe(64))"`.
3. Configurar PostgreSQL mediante las variables `DB_*`.
4. Ejecutar `manage.py check --deploy`, `migrate` y `collectstatic`.
5. Servir la aplicación con un servidor WSGI/ASGI detrás de HTTPS y un proxy inverso.
6. Programar copias de seguridad cifradas de PostgreSQL y probar periódicamente su restauración.

No debe desplegarse `db.sqlite3`, `media/` ni un archivo `.env` desde Git. Los archivos de medios deben almacenarse y respaldarse fuera del repositorio.

## Roles

- `Cajero`: opera su caja, POS, clientes y sus propios reportes.
- `Supervisor`: además consulta reportes globales, ajusta inventario y anula ventas de cajas aún abiertas.
- `Administrador`: recibe todos los permisos disponibles.

El comando `crear_roles_base` agrega los permisos base sin borrar personalizaciones. Use `--reset` únicamente cuando desee reemplazarlas deliberadamente.

## Reglas contables

- `VentaPago.monto` representa el importe aplicado a la venta.
- `VentaPago.monto_recibido` conserva el importe entregado por el cliente.
- El vuelto solo puede originarse en efectivo.
- Una anulación restaura stock y registra contramovimientos; solo se admite mientras la sesión original permanezca abierta.
- Toda modificación de existencias debe pasar por la pantalla de Inventario para conservar la auditoría.
