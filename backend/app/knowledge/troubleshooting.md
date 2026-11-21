# Turbofan Troubleshooting Guide (illustrative demo content)

## TS-01 HPC efficiency loss: compressor wash procedure
Symptoms: T30 (HPC outlet temperature) and T50 (LPT outlet temperature) rise slowly over many cycles, Ps30 static pressure rises, and the fuel flow ratio (phi) drops. The engine works harder to make the same thrust.
Most common cause: fouling of the compressor blades by airborne contaminants. Erosion produces the same pattern but does not recover after washing.
Procedure: perform an on-wing compressor wash with the approved cleaning solution, motoring the engine per the manual. Record the health index before and after. A recovery of more than 10 health points within 10 cycles confirms fouling. If there is no recovery, schedule a borescope inspection to check for erosion.
Safety: lock out the starter and ignition before any wash. Follow site environmental rules for wash effluent.

## TS-02 HPC flow capacity loss: borescope inspection
Symptoms: P30 (HPC outlet pressure) falls while Ps30 rises and core speed (Nc) increases to compensate. The surge margin shrinks.
Risk: a compressor stall can damage the engine. Treat this as urgent and restrict the engine to reduced power until inspected.
Procedure: borescope HPC stages 1 to 9. Look for blade tip curl, missing material, cracks and rub marks. Check the variable stator vane (VSV) rigging and actuator response. Record findings with images and compare against manual damage limits.
Decision: within limits, return to service with increased monitoring. Beyond limits, plan HPC module removal at the next available slot.

## TS-03 HPT thermal wear: EGT margin and borescope
Symptoms: T50 exhaust temperature rises faster than T30 at constant core speed. The EGT margin erodes.
Procedure: trend the EGT margin. Borescope the HPT stage 1 blades and nozzle guide vanes for thermal barrier coating loss, burn-through and cracking. Inspect cooling air bleed lines.
Decision: coating loss within limits means shorter inspection intervals. Burn-through means remove the engine.

## TS-04 Fan damage inspection
Symptoms: a change in bypass ratio (BPR) and fan speed, and higher vibration, often after a known foreign object event.
Procedure: visually inspect every fan blade leading edge. Measure nicks and dents against blend limits. Check the fan vibration survey.

## TS-05 Sensor validation
Symptoms: one sensor deviates strongly while physically related sensors stay normal. For example, T50 jumps but T30, Ps30 and fuel flow are unchanged.
Procedure: cross-check against related parameters. Inspect the probe, harness and connectors. Swap or recalibrate the sensor and confirm readings return to the fleet baseline. Do not act on the engine itself until the sensor has been validated.

## Maintenance planning rules
Critical (predicted remaining life of 15 cycles or less): ground the asset or restrict operation, and raise a P1 work order.
Alert (predicted remaining life of 30 cycles or less, or failure probability of 50% or more): raise a P2 work order and plan the repair within the predicted window.
Watch (health index below the alert line for 5 cycles in a row): raise a P3 inspection and increase monitoring.
Always keep a safety margin: plan work to finish before the predicted remaining life is half used.
