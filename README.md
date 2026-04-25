# Finanzas Locales

Aplicacion web local para finanzas personales. Corre con Flask, guarda datos en SQLite y se puede abrir desde otros dispositivos de la misma red.

## Ejecutar

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
