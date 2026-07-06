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

Nils — 55 Sekunden
Den fünf nummerierten Schritten folgen. Referenzen begrenzen die Evidenzsuche; der Verifikator erhält begrenzte Evidenz statt des gesamten Internets. Die Audit-Spur macht Ausgaben nachvollziehbar und vergleichbar. Danach die Entscheidungen zur Modulabdeckung erklären.

## Folie 5

Nils — 55 Sekunden
Die drei verpflichtenden Kernmodule sind vollständig umgesetzt und evaluiert. Als optionale Vertiefung ist Modul 5 abgeschlossen: Der LoRA-Adapter wurde trainiert, gespeichert und auf labelgleichen sowie Transfer-Benchmarks verglichen. Modul 4 ist über Fast-DetectGPT erfüllt. Binoculars wurde geprüft, aber das kalibrierte Falcon-Paar umfasst etwa 14 Milliarden Parameter und passt nicht in die verfügbare 8-GB-GPU; ein kleineres Paar würde den publizierten Schwellenwert ungültig machen. Für Modul 6 existiert das Vergleichs- und Importgerüst, aber ohne gemeinsame scite- oder SemanticCite-Vorhersagen wird kein fertiger externer Benchmark behauptet. Diese Grenze trennt implementierten Code bewusst von tatsächlich gemessener Evidenz.

## Folie 6

Nick — 60 Sekunden
Es gibt kein einzelnes bestes Backend. Die APIs prüfen bibliografische Daten, nicht die inhaltliche Stützung. Die Evidenzsuche nutzt Embeddings und fällt bei Bedarf auf lexikalische Suche zurück. OpenAI nutzt store=false; lokale Modelle halten Texte auf dem Gerät.

## Folie 7

Nick — 75 Sekunden
Beim Live-Durchlauf den echten RQ5-Bericht und danach den Modellvergleich zeigen. Heuristik und Ollama erhalten dieselben Claims und dieselbe Evidenz. Abweichungen sind kein automatischer Fehlernachweis, sondern gezielte Stellen für die menschliche Prüfung. Falls die Demo nicht läuft, die statische Folie oder ClaimGuard_UI_Demo.mp4 verwenden.

## Folie 8

Nick — 75 Sekunden
Mit 0,900 Macro-F1 der lexikalischen Prüfung beginnen und mit 0,437 bei echten Aussagen kontrastieren. LoRA erreicht auf dem labelgleichen SciFact-Subset 0,367. Fast-DetectGPT erreicht 0,924 AUROC, aber nur 0,533 Recall und übersieht 7 von 15 generierten Passagen. Jeder Wert braucht Datensatz und Fehlergrenze.

## Folie 9

Nils — 75 Sekunden
Alle vier Backends sahen dieselbe Evidenz. Die Heuristik gewinnt diesen kleinen synthetischen Benchmark, weil direkte lexikalische Muster belohnt werden. LoRA ist am schnellsten, kann aber zwei der fünf Labels nicht ausgeben. Ollama schlägt OpenAI hier; OpenAI ist schneller. Das ist kein universelles Modellranking.

## Folie 10

Nils — 55 Sekunden
Je zwei konkrete Stärken und Schwächen nennen. Fast-DetectGPT erzeugte in diesem kleinen Set keinen menschlichen Fehlalarm, übersah aber 7 von 15 generierten Texten. Der offizielle Datensatz enthält keine Zitiermarker; eine Korrelation wird daher nicht behauptet. Private Berichte wurden nicht an den externen Detektor gesendet.

## Folie 11

Nick — 20 Sekunden; Nils — 15 Sekunden
Nick fasst Pipeline und Evidenz zusammen. Nils schließt mit der ethischen Grenze und lädt zu Fragen ein.

## Folie 12

Beide — 5 Minuten
Vorgeschlagene Aufteilung: Nils beantwortet Fragen zu Architektur und Evaluation; Nick übernimmt Modelle, APIs und Demo. Bei Fragen zum niedrigen Echtdatenwert zuerst auf Domain Shift und die Einzelannotation eingehen.
