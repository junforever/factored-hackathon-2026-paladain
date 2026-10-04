# AI Banking Customer Service

Asistente bancario de demostración para gestionar cargos no reconocidos de forma segura.

Puede consultar el contexto de una reclamación, revisar transacciones recientes, bloquear una tarjeta cuando corresponde y escalar casos ambiguos a un especialista humano.

## Qué podés probar

- Reportar un cargo reciente no reconocido.
- Confirmar el bloqueo de una tarjeta.
- Escalar un cargo antiguo, ambiguo o con intereses.
- Solicitar ayuda cuando faltan datos.
- Conversar con el agente en español o portugués.
- Comprobar que las solicitudes inseguras sean rechazadas.

## Cómo usar esta demo

Para seleccionar un caso del sandbox, incluí el identificador sintético proporcionado por el equipo.

Ejemplo:

> No reconozco el cargo asociado al caso `CMP-DEMO`. Quiero bloquear mi tarjeta.

Si el asistente solicita confirmación:

> Sí, confirmo explícitamente que quiero bloquear mi tarjeta.

Para probar un escalamiento:

> No reconozco el cargo asociado al caso `CMP-DEMO`. Es antiguo, incluye intereses y quiero que lo investigue una persona.

`CMP-DEMO` es solo un ejemplo: reemplazalo por un identificador sintético válido del sandbox.

## Seguridad

Esta aplicación utiliza exclusivamente datos y servicios sintéticos de demostración.

No ingreses:

- números completos de tarjeta;
- CVV;
- contraseñas;
- credenciales o API keys;
- información personal real.

Las acciones realizadas afectan solamente el estado local de la demo.

## Limitaciones

Esta aplicación no está conectada a un banco real y no brinda asesoramiento financiero.

En esta versión de demostración, el identificador sintético permite seleccionar un caso concreto del sandbox. En un sistema productivo, el caso sería obtenido automáticamente desde la sesión autenticada del cliente.
