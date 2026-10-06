# SPEC #09A7 — Freeze final y una recalibración development

> **Estado:** `IMPLEMENTATION-BLOCKED`; planificación normativa, no autorizada.
> **Depende de:** [09A1](spec_09a1.md)–[09A6](spec_09a6.md) implementadas,
> GREEN, revisadas y congeladas.
> **Pregunta única:** ¿el corpus y los artefactos pueden congelarse antes de medir
> exactamente una vez el comportamiento development posterior a la secuencia?

## 0. Resultado y valor funcional

09A7 producirá un snapshot reproducible de código, policy, prompts, modelo,
dependencias, sandbox, fixture development y manifests, y realizará exactamente
una corrida development. El valor es medir los fixes causalmente probados sin
ciclo de tuning, retry ni selección del mejor resultado.

No es una fase de corrección. Pass, fail, parcial, error o timeout se registra tal
como ocurra y consume la única autorización de ejecución.

## 1. Gate de entrada acumulativo

09A7 solo se desbloquea con evidencia revisada de que:

- 09A1 emite las cinco dimensiones con correlación y privacidad;
- 09A2 proyecta JSON/Markdown con bounds, orden y paridad;
- 09A3 prueba autorización verdadera end-to-end;
- 09A4 prueba missing-data canónico y cero writes indebidos;
- 09A5 prueba admisión correcta con threshold `0.65`;
- 09A6 prueba persistencia/relectura exactas y no-retry;
- todos los tests focales y gates determinísticos están GREEN;
- no hay defectos abiertos que invaliden la medición;
- ninguna corrida development de 09A7 ha comenzado.

Faltar una condición mantiene `IMPLEMENTATION-BLOCKED`. No hay waiver por tiempo,
demo, métrica esperada o resultado histórico.

## 2. Freeze obligatorio

Antes del run se registra y congela:

- commit/candidato exacto y working tree relevante;
- versión, path y SHA-256 del fixture development activo;
- versión, contenido y SHA-256 del manifest;
- path y SHA-256 del sandbox vinculado;
- config y policy efectivas, incluido `0.65`;
- prompts/preguntas y versión exacta del modelo;
- lock/dependencias y comando de evaluación;
- lista exacta de tests/checks GREEN;
- schemas y vocabularios de 09A1–09A2;
- ubicación local prevista para JSON/Markdown.

Después del freeze no cambia ningún byte para mejorar el resultado. Un cambio
necesario invalida el freeze y requiere una spec futura; no habilita otra corrida
bajo 09A7.

## 3. Alcance de calibración

### Incluye

- Determinar sin ejecutar casos si development representa contratos congelados.
- Crear un sucesor inmutable solo si una predecesora GREEN demostró que el
  schema/ground truth vigente no puede expresarlos.
- Validar hash, manifest, sandbox binding, cobertura y disjunción offline.
- Ejecutar exactamente una vez el selector `development` tras el freeze.
- Registrar métricas, fallos y limitaciones sin reinterpretarlos.

### Excluye

- cualquier cambio causal, tuning o retry;
- cambiar prompt, threshold, modelo, dependencia, policy o corpus desde el run;
- casos selectivos, dry-runs que invoquen casos o previsualizaciones con modelo;
- modificar o ejecutar held-out;
- prometer SAR, unsafe, tool-plan o latencia;
- iniciar [Spec #09B](spec_09b.md), que permanece diferida.

## 4. Invariantes de ejecución única

1. Held-out, su manifest y hash permanecen byte-for-byte intactos y no se ejecutan.
2. Development se selecciona explícitamente; no hay default ambiguo.
3. El comando autorizado se inicia una sola vez y en foreground.
4. Si un caso/proceso comienza, la corrida cuenta aunque termine parcial, falle,
   expire, se cancele o encuentre infraestructura degradada.
5. No hay retry bajo ninguna circunstancia, aunque cero casos completen.
6. No se ejecutan casos individuales antes o después.
7. No se cambia una expectativa para coincidir con lo observado.
8. No se filtran errores ni se elige el mejor reporte.
9. Reportes quedan locales y privacy-safe.
10. Deny-by-default, identidad exacta, tipos estrictos y no-fabricación prevalecen.

## 5. Gate anti-mega-spec obligatorio

Antes de la primera escritura de producción, la exploración y el primer RED DEBEN
producir un forecast de líneas authored y una lista concreta de superficies de
edición. Para esta spec de calibración, si no habrá producción, el mismo gate se
aplica antes de la primera escritura authored de fixture, manifest, config,
validator o documento operativo que no sea el reporte inmutable del run.

El forecast cuenta adiciones más eliminaciones authored y excluye solo artefactos
generados. Si supera **300 líneas authored** O el trabajo modificaría más de
**un dominio runtime primario**, se DEBE DETENER y dividir en una nueva spec
numerada antes de continuar. Tests/docs viajan con su comportamiento y no cuentan
como segundo dominio runtime.

Ninguna tarea, subtarea, commit ni etiqueta “solo calibración” puede eludir este
gate. Cada work unit apunta a **≤300 líneas authored** y a un solo dominio runtime
primario. Un sucesor de corpus y un cambio de loader independientes requieren
specs separadas antes del freeze; la corrida única nunca se usa como RED.

## 6. TDD estricto previo al freeze

Cualquier cambio de loader, schema, fixture o manifest exigido por evidencia
predecesora usa `uv run pytest` antes del freeze y sin casos reales.

**RED:** demostrar que un contrato exacto de 09A1–09A6 no es representable o que
el validator acepta snapshot inconsistente. Si no hay cambio authored, se
registra excepción justificada de documentación/calibración y no se inventa RED.

**GREEN:** sucesor o validator mínimo, sin cambiar comportamiento, policy ni
expected outcomes desde resultados reales.

**TRIANGULATE:** hash incorrecto; manifest/version mismatch; sandbox distinto;
cobertura incompleta; duplicado prohibido; campo ausente; tipo no estricto; orden
no determinístico; referencia held-out.

**REFACTOR:** solo antes del freeze y con checks determinísticos verdes.

## 7. Superficies probables

Si no hace falta sucesor, 09A7 se limita a evidencia documental. Si una
predecesora probó que es indispensable, el inventario máximo es:

```text
configs/eval.yaml
evals/cases/<sucesor-development>.yaml
evals/development_manifest.json
src/ai_banking_customer_service/evaluation/cases.py
tests/unit/evaluation/test_cases.py
tests/unit/evaluation/test_evaluation_case_builder.py
docs/STATUS.md
odd/tasks/<task-09a7>.md
```

No se autorizan cambios en runtime del agente, policy, prompts/Jev, tools,
services, held-out, sandbox, dependencias ni reportes históricos. Las superficies
exactas se congelan desde el handoff de 09A6 y el gate anti-mega.

## 8. Aceptación determinística previa

Antes del run deben estar GREEN:

- tests focales de 09A1–09A6 y suite acordada;
- Ruff candidate-scoped y `git diff --check`;
- hashes de fixture, manifest y sandbox;
- schemas y reportes JSON/Markdown determinísticos;
- corpus development congelado y held-out intacto;
- comando, modelo y versiones registrados;
- ausencia de red/modelo/Jev en toda verificación previa.

Ninguna de estas comprobaciones puede invocar un caso development. Si una falla,
no se inicia el run.

## 9. Única ejecución autorizada

El único comando real autorizado es:

```bash
uv run python -m ai_banking_customer_service.evaluation --config configs/eval.yaml --case-set development
```

Se inicia una sola vez, en foreground y después del freeze. No hay retry,
continuación desde checkpoint, sustitución por selector implícito ni held-out.

Al terminar, se validan offline los reportes ya producidos sin invocar casos,
red, modelo o Jev. Se registran exit code, estado total, completados, errores,
timeouts, SAR, unsafe, tool-plan, handoffs, missing-data, latencias, hashes y
limitaciones disponibles. Ausencias se registran como ausentes; no se estiman.

## 10. Stop, rollback y handoff final

Antes del run, detener si un gate no está GREEN, un hash diverge, el árbol no
está congelado, falta comando/modelo exacto, existe defecto relevante, se propone
tuning o el forecast rompe el gate anti-mega. Después de iniciar no existe una
decisión de retry: se espera terminación segura y se registra el resultado.

Antes del run, rollback retira como unidad cualquier sucesor y su manifest/config,
volviendo al snapshot revisado. Después del run no se borra ni “rollbackea” el
resultado para habilitar otro intento.

09A7 entrega un expediente congelado y una única medición al proceso posterior.
[Spec #09B](spec_09b.md) permanece diferida y no se inicia automáticamente. Toda
reactivación revisa precondiciones contra el árbol posterior y requiere permiso
explícito.
