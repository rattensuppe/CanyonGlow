# CanyonGlow v1.0 - Effekt-Befehlsmatrix

Beispiel für Zone `Skull` / Prefix `A`, Hue `95`, Helligkeit `5`, Tempo `2`.

```text
Solid     AP1,AV:5,AR:0,AD:0,C1:95
Pulse     AP2,AV:5,AR:0,AD:2,C1:95
Breathing AP3,AV:5,AR:0,AD:2,C1:95
Strobe    AP4,AV:5,AR:0,AD:2,C1:95
PT1       AP5,AV:5,AR:0,AD:2,C1:95
PT2       AP6,AV:5,AR:0,AD:2,C1:95
PT3       AP7,AV:5,AR:0,AD:2,C1:95
Rainbow   AP1,AV:5,AR:1,AD:2
```

`Rainbow` sendet absichtlich kein `C1:<Hue>`, weil keine einzelne Farbe genutzt wird.

`Off` ist kein Effekt mehr. Ausschalten erfolgt per EIN/AUS-Schalter:

```text
AP0,AV:0,AR:0,AD:0,C1:<Hue>
```

