# ClaimGuard – Präsentationsnotizen

10 Minuten Vortrag + 5 Minuten Fragen.

## Folie 1

Nils — 20 Sekunden
Mit einem Satz eröffnen: ClaimGuard entscheidet nicht über Täuschung, sondern ordnet Evidenz für eine menschliche Prüfung. Beide Vortragenden sowie die drei Fragen Aussage, Referenz und Stützung vorstellen.

## Folie 2

Nils — 55 Sekunden
Den Kontrast links nutzen. Plagiat, erfundene Referenzen und nicht gestützte Zitate sind unterschiedliche Probleme. ClaimGuard konzentriert sich auf Zitierintegrität und Evidenz. Das System unterstützt Entscheidungen; es erhebt keinen Vorwurf.

## Folie 3

Nils — 45 Sekunden
Von links nach rechts erklären. Die drei Fragen entsprechen den drei Kernmodulen. Jede Entscheidung bleibt im JSON nachvollziehbar; Markdown ist die Ansicht für Prüfende.

## Folie 4

Nils — 70 Sekunden
Den fünf nummerierten Schritten folgen. Referenzen begrenzen die Evidenzsuche; der Verifikator erhält nicht einfach das gesamte Internet. Die Audit-Spur macht die Ausgabe reproduzierbar. Danach an Nick übergeben.

## Folie 5

Nick — 75 Sekunden
Es gibt kein einzelnes bestes Backend. Die APIs prüfen bibliografische Daten, nicht die inhaltliche Stützung. Die Evidenzsuche nutzt Embeddings und fällt bei Bedarf auf lexikalische Suche zurück. OpenAI nutzt store=false; lokale Modelle halten Texte auf dem Gerät.

## Folie 6

Nick — 90 Sekunden
Live: den vorbereiteten Befehl ausführen und rq5_openai.md öffnen. Offline: diese Folie verwenden. Nur die verkürzte, übersetzte Aussage lesen. Auf Quellen und Evidenz zeigen, die Bewertungen vergleichen und erklären, warum sichtbare Begründungen wichtig sind.

## Folie 7

Nick — 75 Sekunden
Mit dem F1-Wert 0,900 der lexikalischen Prüfung beginnen und mit 0,437 Macro-F1 bei echten Aussagen kontrastieren. Embeddings halfen in diesem kleinen Direkt-Evidenz-Benchmark nicht. Das Parser-Ergebnis vorsichtig einordnen: nur fünf Fälle. Entscheidend ist die Lücke zwischen synthetischen und echten Daten.

## Folie 8

Nils — 75 Sekunden
Gold-Benchmark-Ergebnisse von der mit † markierten Einzelfall-Diagnose trennen. Die Heuristik gewinnt den kleinen synthetischen Benchmark, weil direkte lexikalische Muster belohnt werden. LoRA ist schnell, kann aber zwei der fünf ClaimGuard-Labels nicht ausgeben. OpenAI war deutlich schneller als Ollama; ein vollständiger Goldvergleich fehlt noch.

## Folie 9

Nils — 55 Sekunden
Je zwei konkrete Stärken und Schwächen nennen. Einschränkungen sind gemessene technische Erkenntnisse. Binoculars ist integriert, aber das kalibrierte Modellpaar ist mit 8 GB VRAM nicht ausführbar.

## Folie 10

Nick — 20 Sekunden; Nils — 15 Sekunden
Nick fasst Pipeline und Evidenz zusammen. Nils schließt mit der ethischen Grenze und lädt zu Fragen ein.

## Folie 11

Beide — 5 Minuten
Vorgeschlagene Aufteilung: Nils beantwortet Fragen zu Architektur und Evaluation; Nick übernimmt Modelle, APIs und Demo. Bei Fragen zum niedrigen Echtdatenwert zuerst auf Domain Shift und die Einzelannotation eingehen.
