# LLM Cost Autopilot — STEPS para el agente de código

Versión 1.0 · 19 de septiembre de 2026 · Especificación: [PLAN.md](PLAN.md).

Ejecutar por dependencias y criterios de salida. Este documento describe trabajo futuro; únicamente la instalación y lectura de la skill indicadas en fase 0 están realizadas. No se han implementado la aplicación, los scripts propuestos ni los experimentos.

## Protocolo de ejecución

1. Leer PLAN.md, este documento, las instrucciones aplicables al repositorio y la skill TypeSafe. Los planes Fable/Astra son antecedentes; las decisiones consolidadas están en PLAN.
2. Inspeccionar el estado del repositorio antes de editar. Reutilizar trabajo existente y conservar cambios ajenos. El repositorio observado al preparar esta entrega es `C:/Users/sanzp/Desktop/AI/LLM-CostRouter-Jev/llm-cost-optimizer-jev`; verificarlo al retomar.
3. Convertir cada fase en cambios pequeños y comprobables. Al cerrar una fase, actualizar su estado y `docs/progress.md` con archivos, verificaciones, resultados, gasto y siguiente paso. No marcarla completada solo porque exista código.
4. Registrar decisiones relevantes en `docs/decisions.md`: transporte Jev, contratos, pool de modelos, presupuestos, particiones, márgenes de calidad y condiciones de promoción.
5. Respetar autorización y presupuesto ya establecidos. Si falta una credencial o un límite de gasto, continuar con fixtures y tareas locales; solicitar únicamente el dato que impide el siguiente experimento. Una clave presente no establece por sí sola presupuesto.
6. No ejecutar inferencias de pago en CI ni confundir respuestas simuladas con resultados reales. No publicar ni desplegar como consecuencia automática de terminar los archivos.
7. Al trabajar en el entorno actual, prefijar comandos con `rtk` conforme a RTK.md; `rtk proxy` permite ejecutar comandos sin transformación. Las rutas de artefactos siguientes son relativas a la raíz del repositorio de implementación.

## Dependencias y estimación

| Fase | Trabajo | Depende de | Esfuerzo orientativo |
| --- | --- | --- | --- |
| 0 | Skill, alcance y contratos externos | — | 0,5 día |
| 1 | Núcleo, adaptadores mínimos y contabilidad | 0 | 1,5–2 días |
| 2 | Dataset piloto y viabilidad | 1 | 1,5–2 días |
| 3 | Política empírica, Jev y shadow | 2 | 1,5–2 días |
| 4 | Verificación, escalada, API e idempotencia | 3 | 2 días |
| 5 | Auditoría persistente y recuperación | 4 | 1–1,5 días |
| 6 | Calibración y evaluación final | 4 y 5 | 2–3 días más etiquetado |
| 7 | Dashboard, empaquetado y caso de estudio | 6 | 1–2 días |

Son unos 11–15 días de desarrollo centrado, no un compromiso de calendario. Preparar datos, aprobar rúbricas y reducir incertidumbre puede alargarlo. El dashboard puede avanzar con fixtures después de fase 4; no adelantar titulares de ahorro antes de fase 6.

Rama de simplificación: si fase 2 concluye `simplify_fixed_model`, marcar fases 3–5 como `no_aplica` con la evidencia del piloto y adaptar fases 6–7 a benchmark reproducible, selección del fijo, costes, informe y demo offline. Validar en datos independientes cualquier afirmación final o etiquetarla como resultado del piloto. Esta entrega no declara implementado el router ni el servicio; la matriz final se aplica a los componentes realmente construidos y explicita los omitidos.

## Fase 0 — Skill TypeSafe y decisiones iniciales

**Objetivo:** que el agente use el contrato actual de Jev y que el alcance sea ejecutable.

### Instalación: una única vía para Codex

Usar el método `npx skills add` solicitado por el usuario, dirigido solo a Codex y con ámbito de proyecto. No combinarlo con marketplace de Claude ni con un segundo instalador. Desde la raíz del repositorio:

```powershell
rtk proxy npx --yes skills add typesafe-ai/skills --skill typesafe-ai --agent codex --copy --yes
```

`--agent codex` selecciona el agente; `--copy` evita depender de enlaces simbólicos en Windows; la ausencia de `--global` mantiene ámbito local. Es la forma no interactiva del método indicado por el usuario. [Opciones oficiales de skills CLI](https://github.com/vercel-labs/skills).

**Estado comprobado en esta entrega:** instalación completada el 19-09-2026 en `.agents/skills/typesafe-ai/SKILL.md`, dentro del repositorio indicado. Se leyó el archivo instalado y se generó `skills-lock.json`, con origen `typesafe-ai/skills` y `computedHash`:

```text
a6ed7d8a3d2b2d962f8e44b17663767c433b7d1fc32d1ed0349a44f7372513e8
```

Al retomar en ese mismo checkout, comprobar la instalación existente y reutilizarla; no reinstalar automáticamente. En otro checkout, instalar si falta. La skill estará disponible para descubrimiento por Codex en el siguiente turno del proyecto; también puede leerse directamente para aplicarla de inmediato. Conservar el lock para trazabilidad, sin asumir que su hash sea el hash de un único archivo.

Fuentes de la skill: [SKILL.md](https://github.com/typesafe-ai/skills/blob/main/skills/typesafe-ai/SKILL.md) y [versión raw](https://raw.githubusercontent.com/typesafe-ai/skills/main/skills/typesafe-ai/SKILL.md).

### Lista de trabajo

- [x] Instalar la skill TypeSafe únicamente para Codex en el repositorio observado.
- [x] Leer la skill y aplicar al PLAN preguntas acotadas, evidencia, composición en código y evaluación propia.
- [ ] Confirmar instrucciones del checkout, entorno Python/Node/Docker y runtime SQLite real; registrar versiones.
- [ ] Definir contratos iniciales de extracción, clasificación y Q&A contextual, incluidas respuestas válidas cuando falta información.
- [ ] Declarar carga objetivo, idiomas, calidad mínima y latencia; proponer presupuestos de smoke, piloto, evaluación y operación, con estado explícito si faltan.
- [ ] Releer [API TypeSafe](https://docs.typesafe.ai/api), [Choice](https://docs.typesafe.ai/primitives/choice), [Noul](https://docs.typesafe.ai/primitives/noul), [confianza](https://docs.typesafe.ai/confidence), [estado](https://docs.typesafe.ai/concepts/state), [modelos](https://docs.typesafe.ai/models) y [cascada](https://docs.typesafe.ai/cookbooks/sde_cascade). Empezar por `llms.txt`; si no responde, usar navegación y páginas HTML como permite la skill.
- [ ] Revisar [OpenRouter Decisions](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-questions-and-answers-request): API alfa distinta de chat. Proponer `openrouter_decisions` para usar una credencial; registrar `typesafe_direct` como alternativa si la validación real no permite usarla.
- [ ] Guardar fecha de consulta, esquema observado, ID solicitado/resuelto, límites, metadatos de coste y diferencias entre transportes. No afirmar equivalencia a partir de sus nombres.

**Entregables:** `docs/decisions.md`, `docs/progress.md`, `docs/provider-contracts.md`, `.env.example` sin valores secretos y skill/lock comprobados.

**Salida:** alcance, presupuestos pendientes o establecidos y contrato de integración identificados. La selección final del transporte se confirma con el smoke de fase 1, después de disponer de registro de gasto. No lanzar un benchmark aún.

## Fase 1 — Núcleo ejecutable y gasto trazable

**Objetivo:** disponer de una ruta mínima que pueda medir llamadas reales sin perder costes.

- [ ] Crear estructura Python, dependencias fijadas, FastAPI mínimo y contratos internos: `TaskContract`, `ModelProfile`, `DecisionSignals`, `CallResult`, `CheckResult` y `PolicySnapshot`.
- [ ] Implementar configuración Pydantic y esquema generado: claves duplicadas, referencias, límites, campos desconocidos y credenciales condicionales.
- [ ] Crear migración inicial para políticas, solicitudes, llamadas y reservas. Costes enteros, valores desconocidos explícitos y versión de migración.
- [ ] Implementar intención + reserva atómica, llamada fuera de transacción, persistencia de resultado y conciliación. Cubrir concurrencia API/worker desde el núcleo aunque el worker llegue después.
- [ ] Implementar adaptador OpenRouter de generación, con deadline, límites de salida, identificación real de modelo/proveedor y sin reintentos ocultos.
- [ ] Consultar catálogo de modelos, endpoints y tarifas; guardar snapshots. Validar capacidad y soporte de parámetros requeridos, sin inferir calidad del precio.
- [ ] Implementar el adaptador Jev mínimo del transporte seleccionado para el smoke: Choice, Noul y Score; respuesta tipada, uso, timeout y error. Mantenerlo independiente de la política.
- [ ] Crear `scripts/smoke_providers.py` con modo fixture predeterminado y modo real explícito, presupuesto máximo y reporte de gasto. Aproximadamente 10–30 casos bastan para comprobar contrato; no sirven para calibración.
- [ ] Con credenciales y presupuesto, comprobar generación y Jev. Si Decisions alfa no cumple los requisitos, elegir TypeSafe directo y documentar la causa; no desarrollar ambos transportes completos si no hace falta.
- [ ] Registrar facturación o estimación de cada llamada, incluidas fallidas; si no se puede conciliar, marcar el informe como incompleto.

**Entregables:** núcleo ejecutable, migración inicial, adaptadores, fixtures sanitizados, snapshots y `artifacts/smoke/report.json`.

**Verificación:** rechazar configuración inválida antes del gasto; simular timeout/429/respuesta malformada; demostrar reserva concurrente correcta y sustitución de estimación por cargo sin duplicación. Comprobar unidades monetarias con ejemplos conocidos.

**Salida:** una petición de cada proveedor usado produce un resultado trazable o un fallo explícito. El transporte Jev queda elegido y versionado. Sin acceso real puede cerrarse la parte local, pero el smoke real continúa pendiente y no se presentan métricas de proveedor.

## Fase 2 — Piloto y decisión de viabilidad

**Objetivo:** demostrar que hay diferencias aprovechables entre modelos antes de construir el router completo.

- [ ] Construir 100–200 casos representativos con fuente, tarea, idioma, requisitos, etiquetas y agrupación por documento/plantilla. Incluir ausencias, ambigüedades y entradas adversas al contrato.
- [ ] Implementar validadores deterministas y rúbricas de evaluación offline. Separar soporte/corrección de mero formato.
- [ ] Revisar etiquetas y ejemplos ambiguos; conservar `uncertain` cuando no se haya resuelto la referencia.
- [ ] Elegir tres configuraciones generativas y ejecutar cada una sobre los mismos casos elegibles, con ajustes y proveedores registrados. Una cuarta requiere una razón experimental.
- [ ] Guardar todas las salidas, costes, errores y latencias en un manifiesto reproducible. Comprobar capacidad contextual antes de cada llamada.
- [ ] Comparar modelos fijos: barato, más barato que alcanza calidad y strong. Calcular coste por tarea exitosa y variación por tarea.
- [ ] Estimar con transparencia el overhead de routing/verificación/auditoría aún no construido; hacer análisis de sensibilidad, sin llamarlo ahorro medido.
- [ ] Registrar decisión: `continue_router`, `simplify_fixed_model` o `insufficient_evidence`.

**Entregables:** `data/pilot.jsonl`, rúbricas, `scripts/benchmark.py`, perfiles iniciales y `artifacts/pilot/report.md` con evidencia de la decisión.

**Salida:** identificar oportunidades de routing que plausiblemente superen el mejor fijo aceptable después del overhead. Si no existen, simplificar y pasar a una entrega de baseline medido; no forzar complejidad para conservar la arquitectura. Si faltan datos, ampliar solo lo necesario dentro del presupuesto.

## Fase 3 — Política empírica, señales Jev y shadow

**Objetivo:** recomendaciones reproducibles con reglas que no rebajen capacidades ni calidad.

- [ ] Construir perfiles por contrato/configuración: éxitos, muestra, intervalos, costes, latencia y hashes de datos/ajustes/rúbricas.
- [ ] Implementar filtro de candidatos y baseline local por reglas/perfiles. No depender de sklearn sin entrenamiento y validación previos.
- [ ] Definir coste esperado de la trayectoria; si faltan tasas de escalada, usar supuestos conservadores explícitos y conservarlos en el perfil.
- [ ] Implementar selección y fallback cualificados, con códigos de razón y candidatos descartados. Presupuesto insuficiente provoca rechazo, no selección barata no cualificada.
- [ ] Completar el adaptador Jev elegido y preguntas de routing versionadas. `Choice.criteria` como mapa, opciones claras y `other`; Nouls con polaridad explícita.
- [ ] Diseñar estado con instrucciones, contrato y evidencia pertinente. Evitar recortes arbitrarios; detectar contexto no evaluable y probar su salida conservadora.
- [ ] Agrupar preguntas independientes y no permitir dependencias invisibles entre respuestas del mismo lote. Conservar respuestas crudas para análisis.
- [ ] Ejecutar Jev en shadow frente al baseline local. Medir aportación, coste por 1.000 decisiones y latencia; el desacuerdo sobre complejidad no es la métrica de éxito final.
- [ ] Mantener fases 3–5 en fixtures, benchmark o shadow experimental hasta calibrar fase 6. Las pruebas reales acotadas no equivalen a habilitar tráfico activo con gates validados.
- [ ] Probar Jev no disponible, contrato en desacuerdo con tarea inferida, candidato sin perfil y cambios de proveedor/modelo.

**Entregables:** política, perfiles versionados, `config/jev-routing.json`, manifest de transporte/modelo, fixtures y comparación shadow.

**Salida:** misma solicitud y snapshot producen decisión reproducible con fixtures; los fallbacks cumplen restricciones; se puede operar sin llamadas Jev de routing. No activar rutas nuevas por una cifra de confianza sin validación.

## Fase 4 — Verificación antes de entregar y API completa

**Objetivo:** una salida aceptada o un error explícito, con como máximo dos intentos generativos.

- [ ] Construir plantillas confiables de comprobación por contrato: esquema, valores normalizados, ausencia, soporte de etiqueta según entrada/taxonomía, citas, soporte por afirmación y cobertura. En clasificación, pertenencia al conjunto es solo el gate estructural; el gate semántico obligatorio no recibe la etiqueta gold del benchmark.
- [ ] Ejecutar código antes de llamadas semánticas. Separar comprobaciones obligatorias de diagnósticos y evitar aprobar campos no examinados.
- [ ] Implementar agregación `pass/fail/uncertain/error`, umbrales versionados y alternativas del verificador. Las reglas de aceptación se calibran definitivamente en fase 6.
- [ ] Implementar máquina de estados de solicitud, un solo intento generativo extra compartido entre retry/escalada y nuevas comprobaciones sobre la salida final.
- [ ] Respetar deadline global, límites de llamadas y reserva de gastos, incluidas verificaciones y fallback. Si el segundo intento no se acepta, terminar en error.
- [ ] Añadir endpoints de PLAN, metadatos de modelo final, estado verificable de coste y compatibilidad parcial documentada.
- [ ] Implementar clave de idempotencia con hash canónico y resultado recuperable, retención y conflicto. No fusionar peticiones solo por contenido.
- [ ] Capturar política por solicitud e implementar activación local validada/atómica con rollback. No construir todavía actualización HTTP administrativa.
- [ ] Añadir autenticación si se expone fuera de localhost, protección de datos del dashboard y límites de concurrencia.

**Entregables:** API funcional, verificadores, estados, almacenamiento de resultados, activador de política y pruebas de flujo.

**Casos obligatorios:** válido a la primera; barato inválido y fallback válido; fallback inválido; verificador ausente; evidencia incompleta; abstención correcta; timeout con coste desconocido; presupuesto/plazo agotado; retry que consume el segundo intento; petición repetida y conflicto de clave.

**Salida:** ninguno de esos casos produce un falso `contract_passed`, un tercer intento o pérdida de costes. Rechazar streaming y modalidades no soportadas antes de generar.

## Fase 5 — Auditoría durable, retención y recuperación

**Objetivo:** auditar resultados sin bloquear la respuesta y sin confundir auditoría con corrección retroactiva.

- [ ] Completar entidades de evaluaciones, resultados, trabajos y experimentos. Preservar integridad entre solicitud y llamada evaluada.
- [ ] Persistir resultado final y encolado de auditoría seleccionada en una transacción; definir el estado recuperable si el envío HTTP se interrumpe.
- [ ] Guardar los payloads necesarios con expiración y control de acceso; eliminar contenido vencido independientemente de metadatos de costes.
- [ ] Implementar worker con reclamación atómica, lease, heartbeat cuando proceda, recuperación, propietario al completar y reintentos acotados.
- [ ] Aplicar reservas compartidas, subpresupuesto de auditoría y conciliación de gasto tardío. No liberar como gratuita una llamada externa de resultado desconocido.
- [ ] Auditar una muestra aleatoria de todas las rutas, también strong. Incorporar muestreo dirigido solo registrando probabilidades y denominadores.
- [ ] Usar juez independiente con tarea/fuente/rúbrica y una muestra de revisión humana. Crear referencias strong únicamente cuando el experimento lo justifique.
- [ ] Reducir resultados repetidos a una observación terminal por solicitud; preservar incertidumbre y motivos de auditorías omitidas.

**Entregables:** worker, política de retención, reconciliador, muestra de auditoría y pruebas de recuperación.

**Verificación:** reiniciar tras reclamar trabajo y tras completar llamada externa; recuperar lease; impedir cierre por propietario vencido; payload expirado produce `skipped`; auditoría agotada no produce `pass`; lecturas del dashboard no bloquean escrituras prolongadamente; reservas API/worker no admiten gasto dos veces.

**Salida:** auditorías recuperables con costes trazables, duplicados externos posibles explícitos y resultados HTTP previos intactos. No prometer ejecución exactamente una vez.

## Fase 6 — Calibración y experimento final

**Objetivo:** decidir si el router y Jev mejoran coste/calidad con evidencia independiente.

- [ ] Ampliar datos hacia 500–1.000 casos si presupuesto y cobertura lo permiten. Definir tamaño final por incertidumbre necesaria; no por una cifra estética.
- [ ] Crear particiones agrupadas train/validation/test y hashes. Excluir el piloto del test final; impedir duplicados y fugas de etiquetas.
- [ ] Ajustar perfiles, preguntas y umbrales solo en desarrollo/validación. Incluir éxitos y fallos; no entrenar únicamente con errores.
- [ ] Ejecutar baselines y ablaciones obligatorios de PLAN con condiciones pareadas. Evaluar OpenRouter Auto y declarar diferencias si no puede restringirse al mismo pool.
- [ ] Para Auto, comprobar configuración del plugin aplicable, restricciones y modelo real; no interpretar `cost_tier` como techo de gasto.
- [ ] Añadir sklearn o router LLM solo si permite responder una pregunta pendiente. Medir coste/latencia por decisión y éxito de la política resultante.
- [ ] Predeclarar calidad mínima, margen de no inferioridad, latencia y criterio de ahorro; guardar reglas antes de abrir el test.
- [ ] Congelar política, modelos/proveedores, preguntas, rúbricas y perfiles. Ejecutar el test final una vez para esa candidatura; no ajustar al resultado y volver a llamarlo test intacto.
- [ ] Informar éxito por tarea, falsos aceptados/rechazados, errores, incertidumbre, costes completos y latencia; usar intervalos pareados agrupados por fuente.
- [ ] Separar costes operativos de evaluación y shadow. Conservar todos los costes reales y las estimaciones de auditoría si se usó replay, sin presentarlas como facturas.
- [ ] Emitir `promote`, `reject` o `inconclusive`, con razones. Cambios posteriores utilizan un conjunto de promoción nuevo o todavía no consultado.

**Entregables:** dataset y splits versionados, manifiestos, informe comparativo, gráfico coste/calidad, calibración, galería de fallos y decisión de promoción.

**Salida:** comparación reproducible frente al fijo aceptable, con coste de fallos y overhead incluido. Si no se demuestra ahorro o no inferioridad, el informe debe decirlo; la integridad del experimento permite cerrar el proyecto aunque la hipótesis falle.

## Fase 7 — Entrega utilizable y caso de estudio

**Objetivo:** que otra persona ejecute la demo y pueda examinar las conclusiones.

- [ ] Construir Streamlit sobre API o consultas de solo lectura, con filtros por experimento/política/tarea, denominadores, muestras y datos pendientes visibles.
- [ ] Mostrar coste, calidad y latencia juntos; añadir razones de routing, intentos, modelos finales, cobertura de auditoría y casos representativos de fallo.
- [ ] Empaquetar API, worker y dashboard en Docker Compose con volumen local compartido. Validar runtime SQLite y procedimiento de backup/restauración.
- [ ] Crear demo con fixtures sin claves y guía de modo real con credenciales/presupuesto. Datos sintéticos o replay se identifican como tales.
- [ ] Ejecutar carga de servicio con respuestas grabadas/mocks y un smoke real pequeño separado si está autorizado. No hacer 1.000 referencias strong para medir concurrencia del backend.
- [ ] Probar arranque desde entorno limpio, migraciones, retención, reinicio del worker y rollback de política.
- [ ] Redactar README y caso de estudio con problema, workload, baseline, muestra, ahorro observado, diferencia de calidad, latencia, incertidumbre y límites.
- [ ] Revisar archivos públicos para evitar secretos y contenido restringido; entregar resultados reproducibles y listado de costes no conciliados, si existen.

**Entregables:** dashboard, Compose, README, guía de operación, demo, informe final y registro de cierre.

**Salida:** una persona ajena puede reproducir el funcionamiento y entender qué cifras son reales, qué políticas están validadas y qué cuestiones siguen abiertas. La publicación externa requiere el contexto de autorización correspondiente; crear estos artefactos no implica publicarlos.

## Matriz final de comprobación

| Invariante | Evidencia mínima |
| --- | --- |
| Skill TypeSafe instalada y utilizada | Archivo/lock presentes, documentación consultada y transporte documentado. |
| Routing basado en resultados | Perfil por contrato/configuración y baseline comparable. |
| Coste completo | Una entrada por llamada; conciliación sin doble suma ni desconocidos convertidos en cero. |
| Presupuesto y deadline | Pruebas concurrentes y rechazo al no existir ruta admisible. |
| Máximo dos generaciones | Flujo válido, escalada y retry con contador común. |
| Salida final comprobada | Fallo/ausencia de gate nunca tratado como aprobado. |
| Recuperación | Idempotencia, leases y crash con resultado externo desconocido. |
| Auditoría honesta | Muestra, probabilidades, omitidos e incertidumbres visibles. |
| Evaluación independiente | Splits agrupados, test intacto y subconjunto revisado. |
| Caso de estudio defendible | Coste/calidad/latencia con muestra, intervalos y limitaciones. |

## Ampliaciones posteriores

Solo después de cerrar V1: predictor sklearn más detallado, propuestas periódicas de ajuste, API administrativa autenticada, experimentos RouteLLM/LLM router, resúmenes, caché semántica, streaming con resultados provisionales explícitos y despliegue multihost. Cada ampliación necesita su propia hipótesis, presupuesto y evaluación; ninguna justifica rebajar los criterios ya establecidos.
