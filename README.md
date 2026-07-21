# Control de Liquidación — App web con tope MOPRE automático

Este paquete contiene todo lo necesario para publicar la app en internet (gratis) y que el
tope MOPRE se actualice solo cada mes mediante un robot de GitHub Actions.

## Qué hay adentro

| Archivo | Qué es |
|---|---|
| `index.html` | La app completa del control (versión con actualización automática de topes). |
| `data/topes.json` | El archivo de topes que mantiene el robot. Viene sembrado con Abril–Julio 2026 verificados contra las resoluciones ANSES. |
| `scripts/actualizar_tope.py` | El robot: lee la página oficial de Indicadores (Ministerio de Capital Humano) y calcula los meses nuevos por movilidad (IPC, API oficial de datos.gob.ar), con autotest y validación cruzada. |
| `.github/workflows/actualizar-tope.yml` | La programación: corre el robot los días 2, 5, 8, 11 y 14 de cada mes. |

## Cómo funciona (en criollo)

1. Cinco veces por mes, GitHub enciende una computadora gratis y ejecuta el robot.
2. El robot busca el tope en la **página oficial** de Indicadores Monetarios y además lo
   **calcula por la fórmula de movilidad** (tope anterior × (1 + IPC de dos meses atrás)),
   que reproduce al centavo las resoluciones de ANSES (verificado con Abril→Julio 2026).
3. Cuando ambos métodos coinciden, el valor queda **confirmado**. Si solo está el cálculo,
   queda **estimado** y la app lo muestra en ámbar hasta que salga la confirmación oficial.
4. La app, al abrirse con internet, lee `data/topes.json` y completa los topes que falten.
   **Un valor cargado a mano siempre tiene prioridad** — el robot nunca lo pisa.
5. Si algo falla (la página cambió, el IPC no valida, el robot dejó de correr), la app
   muestra un **aviso visible** para que ese mes lo cargues a mano. Nunca calcula en
   silencio con un dato dudoso.

## Publicación paso a paso (una sola vez, ~15 minutos)

### 1. Crear el repositorio
1. Entrá a github.com con tu cuenta nueva y tocá **New repository** (botón verde).
2. Nombre: `control-liquidacion` (o el que quieras). Dejalo **Public** (necesario para
   GitHub Pages gratis; no contiene ningún dato de empleados con nombre — solo la app,
   el robot y los topes públicos de ANSES). **Create repository**.

### 2. Subir los archivos
1. En la página del repo: **uploading an existing file** (o Add file → Upload files).
2. Arrastrá TODO el contenido de esta carpeta (incluida la carpeta `.github` — si tu
   explorador no la muestra, activá "ver archivos ocultos").
3. Abajo tocá **Commit changes**.
   - Si la carpeta `.github` no se sube por arrastre, creá el archivo a mano:
     Add file → Create new file → nombre `.github/workflows/actualizar-tope.yml` →
     pegá el contenido → Commit.

### 3. Activar la página web (GitHub Pages)
1. En el repo: **Settings → Pages** (menú izquierdo).
2. En "Build and deployment": Source = **Deploy from a branch**; Branch = **main** y
   carpeta **/(root)**. **Save**.
3. En 1-2 minutos vas a tener la URL: `https://TUUSUARIO.github.io/control-liquidacion/`
   Esa URL es **la app** — es la que compartís con tus compañeros.

### 4. Probar el robot por primera vez
1. En el repo: pestaña **Actions**. Si pide habilitar workflows, aceptá.
2. Elegí "Actualizar tope MOPRE" → botón **Run workflow** → Run.
3. En ~1 minuto termina. Entrá a `data/topes.json` en el repo y fijate que se haya
   actualizado el campo `actualizado` (y, si ya salió el IPC de junio, que aparezca
   agosto como "estimado").

### 5. Nada más
La app publicada lee `data/topes.json` de su mismo sitio automáticamente (ya viene
configurada con esa ruta relativa). Al abrirla vas a ver el aviso verde de topes
actualizados. Listo: no se carga más a mano en meses normales.

### (Opcional) La versión archivo-suelto también puede actualizarse
Si además seguís repartiendo el HTML como archivo suelto, abrilo → Parámetros →
"Actualización automática" → pegá la URL completa:
`https://TUUSUARIO.github.io/control-liquidacion/data/topes.json` → Actualizar ahora.
GitHub permite ese acceso desde cualquier origen, así que funciona también abierto
desde el disco (siempre que haya internet en ese momento).

## Qué mirar si algo sale mal

- **Banner ámbar "no se pudo actualizar"** al abrir la app → sin internet en ese momento
  o URL mal escrita en Parámetros. Los valores ya aplicados quedan; solo no se refresca.
- **Banner "el robot no corre hace X días"** → entrá a Actions en GitHub y fijate si el
  workflow falló (los logs dicen por qué). Mientras tanto, cargá el tope a mano.
- **Banner "aviso del robot"** → el robot detectó algo (cambio de formato de la página,
  cruce fallido). El texto dice exactamente qué verificar.
- Los topes también se pueden corregir a mano en el propio `data/topes.json` del repo
  (editás el archivo en GitHub, cambiás `"estado"` a `"manual"` para que el robot lo respete).
