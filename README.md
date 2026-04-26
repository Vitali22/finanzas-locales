# Finanzas Locales

Aplicacion web local para finanzas personales. Corre con Flask, guarda datos en SQLite y se puede abrir desde otros dispositivos de la misma red.

Version actual: `1.1.0`

## Ejecutar

La forma mas comoda en Windows es abrir:

```text
iniciar_app.bat
```

Ese archivo crea un entorno local `.venv`, instala dependencias, abre el navegador y arranca la app.

Manual:

1. Instala dependencias:

```powershell
pip install -r requirements.txt
```

Si Windows no reconoce `pip`, prueba:

```powershell
py -m pip install -r requirements.txt
```

O:

```powershell
python -m pip install -r requirements.txt
```

Si Windows tampoco reconoce `py` ni `python`, instala Python 3 desde python.org y marca la opcion **Add python.exe to PATH** durante la instalacion. Luego cierra y vuelve a abrir la terminal.

2. Inicia el servidor:

```powershell
python app.py
```

Tambien puedes usar el archivo:

```text
iniciar_app.bat
```

3. Abre en tu computadora:

```text
http://localhost:5000
```

4. Para abrir desde celular, usa la IP local de la computadora:

```text
http://TU_IP_LOCAL:5000
```

La app inicia en `0.0.0.0` y usa el puerto `5000` por defecto.

Para cambiar el puerto:

```powershell
$env:PORT=5050
python app.py
```

## Acceso inicial

Contraseña inicial:

```text
admin123
```

Puedes cambiarla en `Ajustes`.

## Incluye

- Dashboard con dinero disponible, gasto del dia, presupuesto diario y deuda de credito.
- Corte mensual del dia 15 al dia 14 del siguiente mes.
- Gastos con categorias, subcategorias, metodos de pago y filtros.
- Ingresos con categorias y deposito opcional a cuentas de debito.
- Tarjetas de credito y debito/cuentas con limite, saldo, corte y pago.
- Calendario mensual con eventos futuros, recordatorios y gastos reales.
- Alertas visuales para eventos de los proximos 3 dias.
- Tema claro/oscuro.
- Modo privacidad para ocultar saldos en pantalla.
- Cierre de sesion por inactividad.
- Cambio obligatorio de la contraseña inicial.
- Busqueda rapida de gastos por monto, fecha, categoria, metodo o descripcion.
- Respaldos automaticos diarios y semanales en la carpeta `backups/`.
- Exportacion Excel con pestanas.
- Descarga y restauracion de respaldo `.db`.

## Archivos principales

```text
app.py
templates/
static/
finanzas.db
```

`finanzas.db` se crea automaticamente al iniciar la app.

## Control de versiones

Este proyecto usa Git y GitHub para guardar el historial de cambios.

Archivos de version:

```text
VERSION
CHANGELOG.md
```

Flujo recomendado para guardar cambios:

```powershell
git add .
git commit -m "Describe el cambio"
git push
```
