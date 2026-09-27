"""Meldungstexte der Beratung – „Jarvis“-Register, Deutsch und Englisch.

Regeln: höflich-distanziert (Deutsch: Sie-Form), zurückhaltend meldend, Empfehlungen statt
Anweisungen, kurze deklarative Sätze, keine Ausrufezeichen, keine Emoji im Fließtext,
höchstens ein trockener Nachsatz. Je Meldungsart und Sprache zehn Varianten, zufällig gewählt.

Platzhalter: {Im_raum} / {im_raum} („Im Bad“ / „im Bad“, en: „In Bathroom“ / „in
Bathroom“), {raum}, {wert}, {dauer}, {ppm}, {empfohlen}, {aussen}, {wand}, {name}, {rest}.
"""

from __future__ import annotations

from collections.abc import Mapping
import random
import re

_SENTENCE_START = re.compile(r"(^|[.?]\s+)([a-zäöü])")

TEXTS_DE: dict[str, list[str]] = {
    "frostgefahr": [
        "{Im_raum} sind es nur noch {wert} Grad. Ich empfehle, nach den Fenstern zu sehen.",
        "Die Temperatur {im_raum} ist auf {wert} Grad gefallen. Ein Blick auf Fenster und Heizung wäre ratsam.",
        "{Im_raum} messe ich {wert} Grad. Das ist deutlich zu kalt für die Jahreszeit.",
        "{Im_raum} liegt die Temperatur bei {wert} Grad. Ich empfehle, die Ursache zu prüfen.",
        "Kurze Meldung: {im_raum} herrschen {wert} Grad. Frostschäden möchte ich ungern verwalten.",
        "{Im_raum} sind es {wert} Grad. Möglicherweise steht ein Fenster offen.",
        "Die Raumtemperatur {im_raum} beträgt {wert} Grad. Ich empfehle, das zeitnah zu prüfen.",
        "{Im_raum} wird es kalt. Aktuell {wert} Grad.",
        "Ich registriere {wert} Grad {im_raum}. Die Heizung sollte das eigentlich verhindern.",
        "{Im_raum} ist die Temperatur auf {wert} Grad gesunken. Ein prüfender Blick wäre angebracht.",
    ],
    "heizen_fenster": [
        "{Im_raum} heizt die Heizung, während das Fenster seit {dauer} offen steht. Ich empfehle, eines von beiden zu beenden.",
        "Das Fenster {im_raum} ist seit {dauer} offen, und das Thermostat meldet Heizbetrieb. Das ist wenig effizient.",
        "{Im_raum} laufen Heizung und offenes Fenster gleichzeitig. Ich empfehle, das Fenster zu schließen.",
        "Seit {dauer} steht {im_raum} das Fenster offen, die Heizung arbeitet dennoch. Die Straße wird es danken.",
        "{Im_raum} wird bei offenem Fenster geheizt. Ich empfehle, das Fenster zu schließen oder die Heizung ruhen zu lassen.",
        "Das Thermostat {im_raum} heizt gegen ein offenes Fenster an. Ich empfehle, das zu beenden.",
        "Hinweis: {im_raum} ist das Fenster offen und die Heizung aktiv. Das kostet Energie.",
        "{Im_raum} heizt es seit {dauer} bei geöffnetem Fenster. Ich empfehle, das Fenster zu schließen.",
        "Heizung an, Fenster offen, {im_raum}. Eine der beiden Maßnahmen ist entbehrlich.",
        "{Im_raum} meldet das Thermostat Heizbetrieb bei offenem Fenster. Ich empfehle, einzugreifen.",
    ],
    "schimmel": [
        "{Im_raum} erreicht die Luftfeuchte an der Wand {wert} Prozent. Ich empfehle, {dauer} stoßzulüften.",
        "An den kältesten Wandstellen {im_raum} liegt die Feuchte bei {wert} Prozent. Das begünstigt Schimmel.",
        "{Im_raum} besteht Schimmelrisiko. An der Wand sind es {wert} Prozent relative Feuchte.",
        "Die Wandfeuchte {im_raum} liegt bei {wert} Prozent. Ich empfehle, zu lüften und gleichmäßig zu heizen.",
        "{Im_raum} ist die Luft für die kalten Wände zu feucht. Ich empfehle {dauer} Stoßlüften.",
        "Ich schätze die Wandoberfläche {im_raum} auf {wand} Grad bei {wert} Prozent Feuchte. Das ist zu viel.",
        "{Im_raum} steigt das Schimmelrisiko. Ich empfehle, zu lüften. Schimmel ist ein schlechter Mitbewohner.",
        "Die Feuchte an der Wand {im_raum} beträgt {wert} Prozent. Ich empfehle, den Raum zu lüften.",
        "Schimmelgefahr {im_raum}. Wandfeuchte {wert} Prozent. Ich empfehle, {dauer} zu lüften.",
        "{Im_raum} ist es an der Wand zu feucht, {wert} Prozent. Ein kurzes Stoßlüften würde helfen.",
    ],
    "fenster_schliessen": [
        "Das Fenster {im_raum} ist seit {dauer} offen. Empfohlen waren {empfohlen}.",
        "{Im_raum} steht das Fenster seit {dauer} offen. Ich empfehle, es zu schließen.",
        "Das Fenster {im_raum} ist noch offen. Bei {aussen} Grad draußen genügen {empfohlen}.",
        "{Im_raum} wurde ausreichend gelüftet. Ich empfehle, das Fenster zu schließen.",
        "Seit {dauer} ist {im_raum} das Fenster offen. Der Raum dürfte inzwischen gut durchgelüftet sein.",
        "Das Fenster {im_raum} steht noch offen. Ich empfehle, es zu schließen, bevor die Wände auskühlen.",
        "{Im_raum} ist das Fenster seit {dauer} geöffnet. Die Außenluft hat ihren Dienst getan.",
        "Die empfohlene Lüftdauer {im_raum} ist überschritten. Ich empfehle, das Fenster zu schließen.",
        "{Im_raum} wird noch gelüftet. Seit {dauer}, um genau zu sein.",
        "Das Fenster {im_raum} ist offen, draußen sind es {aussen} Grad. Ich empfehle, es zu schließen.",
    ],
    "fenster_regen": [
        "Es regnet, und {im_raum} ist das Fenster offen. Ich empfehle, es zu schließen.",
        "{Im_raum} steht ein Fenster offen, während es regnet. Das Fensterbrett wird nass.",
        "Draußen regnet es. Das Fenster {im_raum} ist noch geöffnet.",
        "Regen und offenes Fenster {im_raum}. Ich empfehle, das Fenster zu schließen.",
        "{Im_raum} ist das Fenster offen, und es hat zu regnen begonnen. Ein Schließen wäre ratsam.",
        "Es regnet. {Im_raum} steht das Fenster offen. Ich empfehle, das zu ändern.",
        "Das Fenster {im_raum} ist offen, es regnet. Lüften ist bei dieser Luftfeuchte ohnehin wenig ergiebig.",
        "Hinweis: Regen, und {im_raum} ist ein Fenster geöffnet.",
        "{Im_raum} regnet es womöglich hinein. Das Fenster ist offen.",
        "Es regnet draußen. Ich empfehle, das Fenster {im_raum} zu schließen.",
    ],
    "lueften_co2": [
        "Der CO2-Wert {im_raum} liegt bei {ppm} ppm. Ich empfehle, {dauer} stoßzulüften.",
        "{Im_raum} ist die Luft verbraucht, {ppm} ppm CO2. Ein kurzes Stoßlüften würde helfen.",
        "{Im_raum} messe ich {ppm} ppm Kohlendioxid. Ich empfehle {dauer} Stoßlüften.",
        "Die Luftqualität {im_raum} lässt nach, {ppm} ppm CO2. Frische Luft wäre angebracht.",
        "{Im_raum} steigt der CO2-Gehalt auf {ppm} ppm. Ich empfehle, das Fenster für {dauer} zu öffnen.",
        "CO2 {im_raum}: {ppm} ppm. Ich empfehle zu lüften. Konzentration ist ein knappes Gut.",
        "{Im_raum} liegt Kohlendioxid bei {ppm} ppm. Stoßlüften für {dauer} genügt.",
        "Die Raumluft {im_raum} ist verbraucht. Ich empfehle, {dauer} zu lüften.",
        "{Im_raum} sind es {ppm} ppm CO2. Ein offenes Fenster für {dauer} würde das beheben.",
        "Ich empfehle, {im_raum} zu lüften. Der CO2-Wert liegt bei {ppm} ppm.",
    ],
    "lueften_feuchte": [
        "Die Luftfeuchte {im_raum} liegt bei {wert} Prozent. Ich empfehle, {dauer} stoßzulüften.",
        "{Im_raum} ist die Luft mit {wert} Prozent recht feucht. Draußen ist es trockener. Ich empfehle zu lüften.",
        "{Im_raum} messe ich {wert} Prozent Luftfeuchte. {dauer} Stoßlüften würden genügen.",
        "Die Feuchte {im_raum} beträgt {wert} Prozent. Die Außenluft ist trockener, Lüften lohnt sich.",
        "{Im_raum} ist es feucht, {wert} Prozent. Ich empfehle, das Fenster für {dauer} weit zu öffnen.",
        "Luftfeuchte {im_raum}: {wert} Prozent. Ich empfehle {dauer} Stoßlüften.",
        "{Im_raum} liegt die Luftfeuchte über dem Zielwert, bei {wert} Prozent. Lüften wäre sinnvoll.",
        "Ich empfehle, {im_raum} {dauer} zu lüften. Die Luftfeuchte liegt bei {wert} Prozent.",
        "{Im_raum} sammelt sich Feuchte, aktuell {wert} Prozent. Draußen ist die Luft trockener.",
        "Die Luft {im_raum} ist mit {wert} Prozent zu feucht. Ein kurzes Stoßlüften würde helfen.",
    ],
    "lueften_dusche": [
        "Nach dem Duschen liegt die Luftfeuchte {im_raum} bei {wert} Prozent. Ich empfehle, {dauer} zu lüften.",
        "{Im_raum} ist es nach dem Duschen feucht, {wert} Prozent. Ich empfehle, das Fenster zu öffnen.",
        "Die Dusche hat {im_raum} {wert} Prozent Luftfeuchte hinterlassen. {dauer} Stoßlüften würden genügen.",
        "{Im_raum} liegt die Luftfeuchte nach dem Duschen bei {wert} Prozent. Lüften wäre jetzt sinnvoll.",
        "Nach dem Duschen empfehle ich {dauer} Stoßlüften {im_raum}. Aktuell {wert} Prozent Feuchte.",
        "{Im_raum} beschlägt vermutlich der Spiegel. {wert} Prozent Luftfeuchte. Ich empfehle zu lüften.",
        "Die Luftfeuchte {im_raum} ist nach dem Duschen auf {wert} Prozent gestiegen. Ich empfehle, zu lüften.",
        "{Im_raum}: {wert} Prozent Feuchte nach dem Duschen. Ich empfehle, das Fenster für {dauer} zu öffnen.",
        "Nach dem Duschen ist die Luft {im_raum} feucht, {wert} Prozent. Lüften beugt Schimmel vor.",
        "Ich empfehle, {im_raum} nach dem Duschen zu lüften. Die Luftfeuchte liegt bei {wert} Prozent.",
    ],
    "feinstaub": [
        "Die Feinstaubbelastung {im_raum} liegt bei {wert} Mikrogramm. Ich empfehle, den Luftreiniger höher zu stellen.",
        "{Im_raum} messe ich {wert} Mikrogramm Feinstaub. Der Luftreiniger könnte stärker arbeiten.",
        "{Im_raum} ist die Luft belastet, {wert} Mikrogramm Feinstaub. Ich empfehle eine höhere Stufe am Luftreiniger.",
        "Feinstaub {im_raum}: {wert} Mikrogramm. Ich empfehle, den Luftreiniger auf Turbo zu stellen.",
        "{Im_raum} ist der Feinstaubwert auf {wert} Mikrogramm gestiegen. Der Luftreiniger dürfte das lösen.",
        "Die Luft {im_raum} enthält {wert} Mikrogramm Feinstaub. Ich empfehle, den Luftreiniger hochzuregeln.",
        "{Im_raum} liegt Feinstaub bei {wert} Mikrogramm. Möglicherweise wurde gekocht oder gebacken.",
        "Ich empfehle, den Luftreiniger {im_raum} stärker laufen zu lassen. Feinstaub {wert} Mikrogramm.",
        "{Im_raum} ist die Feinstaubbelastung erhöht, {wert} Mikrogramm. Der Luftreiniger wartet auf seinen Einsatz.",
        "Feinstaubwert {im_raum}: {wert} Mikrogramm. Eine höhere Luftreinigerstufe wäre sinnvoll.",
    ],
    "feinstaub_ohne_geraet": [
        "Die Feinstaubbelastung {im_raum} liegt bei {wert} Mikrogramm. Ich empfehle, kurz zu lüften, sofern draußen bessere Luft ist.",
        "{Im_raum} messe ich {wert} Mikrogramm Feinstaub. Ein kurzes Stoßlüften könnte helfen.",
        "{Im_raum} ist die Luft mit {wert} Mikrogramm Feinstaub belastet. Ich empfehle zu lüften.",
        "Feinstaub {im_raum}: {wert} Mikrogramm. Ich empfehle, die Quelle zu prüfen und zu lüften.",
        "{Im_raum} ist der Feinstaubwert auf {wert} Mikrogramm gestiegen. Möglicherweise wurde gekocht.",
        "Die Luft {im_raum} enthält {wert} Mikrogramm Feinstaub. Frische Luft wäre angebracht.",
        "{Im_raum} liegt Feinstaub bei {wert} Mikrogramm. Ich empfehle ein kurzes Stoßlüften.",
        "Erhöhter Feinstaub {im_raum}, {wert} Mikrogramm. Ich empfehle, zu lüften.",
        "{Im_raum} ist die Feinstaubbelastung erhöht. Aktuell {wert} Mikrogramm.",
        "Feinstaubwert {im_raum}: {wert} Mikrogramm. Ein offenes Fenster wäre hilfreich.",
    ],
    "zu_trocken": [
        "Die Luftfeuchte {im_raum} liegt bei nur {wert} Prozent. Das ist recht trocken.",
        "{Im_raum} ist die Luft trocken, {wert} Prozent. Ich empfehle, nicht zusätzlich zu lüften.",
        "{Im_raum} messe ich {wert} Prozent Luftfeuchte. Ein Luftbefeuchter oder Pflanzen würden helfen.",
        "Die Luft {im_raum} ist mit {wert} Prozent zu trocken. Schleimhäute bevorzugen etwas mehr.",
        "{Im_raum} liegt die Luftfeuchte bei {wert} Prozent. Ich empfehle, die Heiztemperatur leicht zu senken.",
        "Trockene Luft {im_raum}: {wert} Prozent. Ich empfehle, Wäsche dort zu trocknen.",
        "{Im_raum} ist die Luft trocken. {wert} Prozent relative Feuchte.",
        "Luftfeuchte {im_raum}: {wert} Prozent. Das liegt unter dem Wohlfühlbereich.",
        "{Im_raum} ist es mit {wert} Prozent Luftfeuchte recht trocken. Ich empfehle, gegenzusteuern.",
        "Die Raumluft {im_raum} ist trocken, {wert} Prozent. Ein Glas Wasser schadet ebenfalls nicht.",
    ],
    "filter": [
        "Der Filter des Luftreinigers {im_raum} benötigt Aufmerksamkeit. {name}: {rest}.",
        "{Im_raum} ist Filterwartung fällig. {name}: {rest}.",
        "Der Luftreiniger {im_raum} meldet Filterbedarf. {name}: {rest}.",
        "Ich empfehle, den Filter des Luftreinigers {im_raum} zu prüfen. {name}: {rest}.",
        "Filterhinweis {im_raum}. {name}: {rest}.",
        "{Im_raum} nähert sich der Luftreinigerfilter seinem Ende. {name}: {rest}.",
        "Der Luftreiniger {im_raum} wünscht Pflege. {name}: {rest}.",
        "Ich empfehle, einen Ersatzfilter für den Luftreiniger {im_raum} bereitzulegen. {name}: {rest}.",
        "Filterwartung {im_raum}. {name}: {rest}. Der Filter arbeitet nicht ewig.",
        "{Im_raum} ist der Filter bald verbraucht. {name}: {rest}.",
    ],
    "test": [
        "Dies ist eine Testmeldung der Klimaberatung. Der Kanal funktioniert.",
        "Testmeldung. Die Klimaberatung ist erreichbar.",
        "Die Klimaberatung meldet sich zur Probe. Alles in Ordnung.",
        "Probemeldung der Klimaberatung. Keine weiteren Maßnahmen erforderlich.",
        "Ein Test der Klimaberatung. Sie hören bzw. lesen mich.",
        "Testlauf der Klimaberatung. Der Kanal ist betriebsbereit.",
        "Dies ist nur ein Test. Die Luft ist, soweit bekannt, in Ordnung.",
        "Die Klimaberatung prüft diesen Kanal. Erfolgreich, wie es scheint.",
        "Testmeldung der Klimaberatung. Lüften ist nicht erforderlich.",
        "Kurzer Funktionstest der Klimaberatung. Ende der Meldung.",
    ],
}

TEXTS_EN: dict[str, list[str]] = {
    "frostgefahr": [
        "{Im_raum} it is down to {wert} degrees. I would suggest checking the windows.",
        "The temperature {im_raum} has dropped to {wert} degrees. A look at windows and heating would be advisable.",
        "{Im_raum} I am measuring {wert} degrees. That is rather cold for the season.",
        "{Im_raum} the temperature stands at {wert} degrees. I recommend looking into the cause.",
        "A brief note: {im_raum} it is {wert} degrees. I would rather not manage frost damage.",
        "{Im_raum} it is {wert} degrees. A window may have been left open.",
        "The room temperature {im_raum} is {wert} degrees. I recommend checking it soon.",
        "{Im_raum} it is getting cold. Currently {wert} degrees.",
        "I register {wert} degrees {im_raum}. The heating ought to prevent that.",
        "{Im_raum} the temperature has fallen to {wert} degrees. A closer look would be appropriate.",
    ],
    "heizen_fenster": [
        "{Im_raum} the heating is running while the window has been open for {dauer}. I recommend ending one of the two.",
        "The window {im_raum} has been open for {dauer}, and the thermostat reports heating. That is not very efficient.",
        "{Im_raum} heating and an open window are running at the same time. I recommend closing the window.",
        "The window {im_raum} has been open for {dauer}, yet the heating carries on. The street will be grateful.",
        "{Im_raum} the room is being heated with the window open. I recommend closing the window or letting the heating rest.",
        "The thermostat {im_raum} is heating against an open window. I recommend putting an end to that.",
        "A note: {im_raum} the window is open and the heating is active. That costs energy.",
        "{Im_raum} it has been heating with the window open for {dauer}. I recommend closing the window.",
        "Heating on, window open, {im_raum}. One of the two measures is dispensable.",
        "{Im_raum} the thermostat reports heating with the window open. I recommend stepping in.",
    ],
    "schimmel": [
        "{Im_raum} the humidity at the wall reaches {wert} percent. I recommend airing the room for {dauer}.",
        "At the coldest wall spots {im_raum} the humidity is {wert} percent. That encourages mould.",
        "{Im_raum} there is a risk of mould. The wall shows {wert} percent relative humidity.",
        "The wall humidity {im_raum} is {wert} percent. I recommend airing and heating evenly.",
        "{Im_raum} the air is too humid for the cold walls. I recommend {dauer} of airing.",
        "I estimate the wall surface {im_raum} at {wand} degrees with {wert} percent humidity. That is too much.",
        "{Im_raum} the mould risk is rising. I recommend airing the room. Mould makes a poor housemate.",
        "The humidity at the wall {im_raum} is {wert} percent. I recommend airing the room.",
        "Mould risk {im_raum}. Wall humidity {wert} percent. I recommend airing for {dauer}.",
        "{Im_raum} it is too damp at the wall, {wert} percent. A short burst of fresh air would help.",
    ],
    "fenster_schliessen": [
        "The window {im_raum} has been open for {dauer}. {empfohlen} were recommended.",
        "{Im_raum} the window has been open for {dauer}. I recommend closing it.",
        "The window {im_raum} is still open. At {aussen} degrees outside, {empfohlen} are sufficient.",
        "{Im_raum} has been aired sufficiently. I recommend closing the window.",
        "The window {im_raum} has been open for {dauer}. The room should be well aired by now.",
        "The window {im_raum} is still open. I recommend closing it before the walls cool down.",
        "{Im_raum} the window has been open for {dauer}. The outside air has done its job.",
        "The recommended airing time {im_raum} has been exceeded. I recommend closing the window.",
        "{Im_raum} the airing continues. For {dauer}, to be precise.",
        "The window {im_raum} is open, and it is {aussen} degrees outside. I recommend closing it.",
    ],
    "fenster_regen": [
        "It is raining, and the window {im_raum} is open. I recommend closing it.",
        "{Im_raum} a window is open while it rains. The windowsill is getting wet.",
        "It is raining outside. The window {im_raum} is still open.",
        "Rain and an open window {im_raum}. I recommend closing the window.",
        "{Im_raum} the window is open, and it has started to rain. Closing it would be advisable.",
        "It is raining. {Im_raum} the window is open. I recommend changing that.",
        "The window {im_raum} is open, and it is raining. Airing is of little use at this humidity anyway.",
        "A note: rain, and a window is open {im_raum}.",
        "{Im_raum} it may be raining in. The window is open.",
        "It is raining outside. I recommend closing the window {im_raum}.",
    ],
    "lueften_co2": [
        "The CO2 level {im_raum} is {ppm} ppm. I recommend airing the room for {dauer}.",
        "{Im_raum} the air is stale, {ppm} ppm CO2. A short burst of fresh air would help.",
        "{Im_raum} I am measuring {ppm} ppm of carbon dioxide. I recommend {dauer} of airing.",
        "The air quality {im_raum} is declining, {ppm} ppm CO2. Fresh air would be appropriate.",
        "{Im_raum} the CO2 level has risen to {ppm} ppm. I recommend opening the window for {dauer}.",
        "CO2 {im_raum}: {ppm} ppm. I recommend airing. Concentration is a scarce resource.",
        "{Im_raum} carbon dioxide is at {ppm} ppm. Airing for {dauer} will suffice.",
        "The air {im_raum} is stale. I recommend airing for {dauer}.",
        "{Im_raum} it is {ppm} ppm CO2. An open window for {dauer} would resolve that.",
        "I recommend airing {im_raum}. The CO2 level is {ppm} ppm.",
    ],
    "lueften_feuchte": [
        "The humidity {im_raum} is {wert} percent. I recommend airing the room for {dauer}.",
        "{Im_raum} the air is rather humid at {wert} percent. It is drier outside. I recommend airing.",
        "{Im_raum} I am measuring {wert} percent humidity. {dauer} of airing would suffice.",
        "The humidity {im_raum} is {wert} percent. The outside air is drier, airing is worthwhile.",
        "{Im_raum} it is humid, {wert} percent. I recommend opening the window wide for {dauer}.",
        "Humidity {im_raum}: {wert} percent. I recommend {dauer} of airing.",
        "{Im_raum} the humidity is above target, at {wert} percent. Airing would be sensible.",
        "I recommend airing {im_raum} for {dauer}. The humidity is {wert} percent.",
        "{Im_raum} moisture is building up, currently {wert} percent. The outside air is drier.",
        "The air {im_raum} is too humid at {wert} percent. A short burst of fresh air would help.",
    ],
    "lueften_dusche": [
        "After the shower the humidity {im_raum} is {wert} percent. I recommend airing for {dauer}.",
        "{Im_raum} it is humid after the shower, {wert} percent. I recommend opening the window.",
        "The shower has left {wert} percent humidity {im_raum}. {dauer} of airing would suffice.",
        "{Im_raum} the humidity after the shower is {wert} percent. Airing would be sensible now.",
        "After the shower I recommend {dauer} of airing {im_raum}. Currently {wert} percent humidity.",
        "{Im_raum} the mirror is presumably steamed up. {wert} percent humidity. I recommend airing.",
        "The humidity {im_raum} has risen to {wert} percent after the shower. I recommend airing.",
        "{Im_raum}: {wert} percent humidity after the shower. I recommend opening the window for {dauer}.",
        "After the shower the air {im_raum} is humid, {wert} percent. Airing prevents mould.",
        "I recommend airing {im_raum} after the shower. The humidity is {wert} percent.",
    ],
    "feinstaub": [
        "Particulate matter {im_raum} is at {wert} micrograms. I recommend turning up the air purifier.",
        "{Im_raum} I am measuring {wert} micrograms of particulate matter. The air purifier could work harder.",
        "{Im_raum} the air is polluted, {wert} micrograms of particulate matter. I recommend a higher purifier level.",
        "Particulate matter {im_raum}: {wert} micrograms. I recommend setting the air purifier to its highest level.",
        "{Im_raum} particulate matter has risen to {wert} micrograms. The air purifier should resolve that.",
        "The air {im_raum} contains {wert} micrograms of particulate matter. I recommend turning up the purifier.",
        "{Im_raum} particulate matter is at {wert} micrograms. Perhaps someone has been cooking or baking.",
        "I recommend running the air purifier {im_raum} harder. Particulate matter {wert} micrograms.",
        "{Im_raum} particulate matter is elevated, {wert} micrograms. The air purifier awaits its assignment.",
        "Particulate matter {im_raum}: {wert} micrograms. A higher purifier level would be sensible.",
    ],
    "feinstaub_ohne_geraet": [
        "Particulate matter {im_raum} is at {wert} micrograms. I recommend airing briefly, provided the air outside is better.",
        "{Im_raum} I am measuring {wert} micrograms of particulate matter. A short burst of fresh air might help.",
        "{Im_raum} the air carries {wert} micrograms of particulate matter. I recommend airing.",
        "Particulate matter {im_raum}: {wert} micrograms. I recommend checking the source and airing.",
        "{Im_raum} particulate matter has risen to {wert} micrograms. Perhaps someone has been cooking.",
        "The air {im_raum} contains {wert} micrograms of particulate matter. Fresh air would be appropriate.",
        "{Im_raum} particulate matter is at {wert} micrograms. I recommend a short burst of airing.",
        "Elevated particulate matter {im_raum}, {wert} micrograms. I recommend airing.",
        "{Im_raum} particulate matter is elevated. Currently {wert} micrograms.",
        "Particulate matter {im_raum}: {wert} micrograms. An open window would help.",
    ],
    "zu_trocken": [
        "The humidity {im_raum} is only {wert} percent. That is rather dry.",
        "{Im_raum} the air is dry, {wert} percent. I recommend not airing any further.",
        "{Im_raum} I am measuring {wert} percent humidity. A humidifier or plants would help.",
        "The air {im_raum} is too dry at {wert} percent. Mucous membranes prefer a little more.",
        "{Im_raum} the humidity is {wert} percent. I recommend lowering the heating slightly.",
        "Dry air {im_raum}: {wert} percent. I recommend drying laundry there.",
        "{Im_raum} the air is dry. {wert} percent relative humidity.",
        "Humidity {im_raum}: {wert} percent. That is below the comfort range.",
        "{Im_raum} it is rather dry at {wert} percent humidity. I recommend counteracting.",
        "The air {im_raum} is dry, {wert} percent. A glass of water will not hurt either.",
    ],
    "filter": [
        "The air purifier filter {im_raum} requires attention. {name}: {rest}.",
        "{Im_raum} filter maintenance is due. {name}: {rest}.",
        "The air purifier {im_raum} reports a filter requirement. {name}: {rest}.",
        "I recommend checking the air purifier filter {im_raum}. {name}: {rest}.",
        "Filter notice {im_raum}. {name}: {rest}.",
        "{Im_raum} the air purifier filter is nearing its end. {name}: {rest}.",
        "The air purifier {im_raum} requests some care. {name}: {rest}.",
        "I recommend keeping a replacement filter ready for the air purifier {im_raum}. {name}: {rest}.",
        "Filter maintenance {im_raum}. {name}: {rest}. Filters do not last forever.",
        "{Im_raum} the filter will soon be used up. {name}: {rest}.",
    ],
    "test": [
        "This is a test message from the climate advisor. The channel works.",
        "Test message. The climate advisor is reachable.",
        "The climate advisor reporting for a trial run. All is well.",
        "Trial message from the climate advisor. No further action required.",
        "A test of the climate advisor. You are hearing or reading me.",
        "Test run of the climate advisor. The channel is operational.",
        "This is only a test. The air is, as far as I know, in order.",
        "The climate advisor is checking this channel. Successfully, it seems.",
        "Test message from the climate advisor. No airing required.",
        "Brief function test of the climate advisor. End of message.",
    ],
}
TEXTS: dict[str, dict[str, list[str]]] = {"de": TEXTS_DE, "en": TEXTS_EN}

# Push-Titel (Emoji erlaubt, wie bei den bestehenden Pushs)
TITLES_DE: dict[str, str] = {
    "frostgefahr": "🥶 Frostgefahr",
    "heizen_fenster": "🪟 Heizen bei offenem Fenster",
    "schimmel": "🍄 Schimmelrisiko",
    "fenster_schliessen": "🪟 Fenster schließen",
    "fenster_regen": "🌧️ Fenster offen bei Regen",
    "lueften_co2": "🌬️ Lüften empfohlen",
    "lueften_feuchte": "🌬️ Lüften empfohlen",
    "feinstaub": "😷 Feinstaub",
    "zu_trocken": "🏜️ Trockene Luft",
    "filter": "🧰 Filterwartung",
    "test": "🧪 Klimaberatung",
}
TITLES_EN: dict[str, str] = {
    "frostgefahr": "🥶 Frost risk",
    "heizen_fenster": "🪟 Heating with window open",
    "schimmel": "🍄 Mould risk",
    "fenster_schliessen": "🪟 Close window",
    "fenster_regen": "🌧️ Window open in the rain",
    "lueften_co2": "🌬️ Airing recommended",
    "lueften_feuchte": "🌬️ Airing recommended",
    "feinstaub": "😷 Particulate matter",
    "zu_trocken": "🏜️ Dry air",
    "filter": "🧰 Filter maintenance",
    "test": "🧪 Climate advisor",
}
TITLES: dict[str, dict[str, str]] = {"de": TITLES_DE, "en": TITLES_EN}


def title(topic: str, lang: str = "de", plain: bool = False) -> str:
    """Titel eines Themas (plain = ohne Emoji, für NSPanel und Alexa-Bildschirm)."""
    titles = TITLES.get(lang, TITLES_DE)
    value = titles.get(topic, titles["test"])
    return value.split(" ", 1)[1] if plain and " " in value else value


class _Safe(dict[str, str]):
    """Fehlende Platzhalter bleiben leer statt eine Ausnahme auszulösen."""

    def __missing__(self, key: str) -> str:
        return ""


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def render(
    text_key: str,
    values: Mapping[str, str],
    rng: random.Random | None = None,
    lang: str = "de",
) -> str:
    """Eine zufällige Variante in der gewählten Sprache mit Werten füllen."""
    texts = TEXTS.get(lang, TEXTS_DE)
    variants = texts.get(text_key) or texts["test"]
    template = (rng or random).choice(variants)
    data = _Safe(values)
    if "im_raum" in data:
        data.setdefault("Im_raum", _cap(data["im_raum"]))
    text = " ".join(template.format_map(data).split())
    return _SENTENCE_START.sub(lambda m: m.group(1) + m.group(2).upper(), text)
