# AI Banking Customer Service

Demonstration banking assistant designed to handle unrecognized charges securely.

It can query complaint context, review recent transactions, block a card when appropriate, and escalate ambiguous cases to a human specialist.

## What You Can Try

- Report a recent unrecognized charge.
- Confirm a card block.
- Escalate an older, ambiguous, or interest-bearing charge.
- Request assistance when data is missing.
- Chat with the agent in Spanish or Portuguese.
- Verify that unsafe requests are rejected.

## How to Use This Demo

To select a sandbox case, include the synthetic identifier provided by the team.

Example:

> I do not recognize the charge associated with case `CMP-DEMO`. I want to block my card.

If the assistant requests confirmation:

> Yes, I explicitly confirm that I want to block my card.

To test an escalation:

> I do not recognize the charge associated with case `CMP-DEMO`. It is old, includes interest, and I want a person to investigate it.

`CMP-DEMO` is just an example: replace it with a valid synthetic identifier from the sandbox.

## Security

This application uses synthetic demonstration data and services exclusively.

Do not enter:

- full card numbers;
- CVV;
- passwords;
- credentials or API keys;
- real personal information.

Actions performed only affect the local demo state.

## Limitations

This application is not connected to a real bank and does not provide financial advice.

In this demo version, the synthetic identifier selects a specific case from the sandbox. In a production system, the case would be retrieved automatically from the authenticated customer session.

---

# AI Banking Customer Service

Asistente bancario de demostración para gestionar cargos no reconocidos de forma segura.

Puede consultar el contexto de una reclamación, revisar transacciones recientes, bloquear una tarjeta cuando corresponde y escalar casos ambiguos a un especialista humano.

## Qué puedes probar

- Reportar un cargo reciente no reconocido.
- Confirmar el bloqueo de una tarjeta.
- Escalar un cargo antiguo, ambiguo o con intereses.
- Solicitar ayuda cuando faltan datos.
- Conversar con el agente en español o portugués.
- Comprobar que las solicitudes inseguras sean rechazadas.

## Cómo usar esta demo

Para seleccionar un caso del sandbox, incluye el identificador sintético proporcionado por el equipo.

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
