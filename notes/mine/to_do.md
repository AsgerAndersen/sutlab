# To do

## Next up

-   Implementer novo sagen som eksempel.
    -   brug derefter combined excel loader til at loade novo sag og adde den til sut.
    -   start med løbende priser
    -   start med at gøre sagen væsentligt mindre (eg 5 milliarder som 2019 værdi), så den bliver nemmere at afstemme, når vi bare bruger den som eksempel

-   Design og implementer workflow til at veksle mellem udforskning af afstemning, og automatisk af alle år
    -   Se bud i notes/mine/balancing_workflow.md
    -   Start med løbende priser

-   Implementer flere inspektionsfunktioner

    -   inspect_price_layers_balances
        -   funktion til at tjekke balancer for prislag

    -   funktioner til at lave overblik over hele tidsserien
        -   bnp
        -   produktivitet
        -   kræver implementering af deflatering og chained linked indexing
            -   men start med bare at implementer for løbende priser, så jeg kan gå videre til at designe workflow, hvor det kun er løbende priser, der afstemmes. så vender jeg tilbage til faste priser.
            -   eller faktisk: vent helt med denne funktionalitet, til jeg har implementeret workflow.

## Spørgsmål
-   Hvordan skal balancing funktionerne forholde sig til negative tal? Og lagre specifikt. Skal de som udgangspunkt ikke ændres, medmindre afstemmerne gør det "manuelt" vha flyt funktioner?

## Christina, kommentarer
-   Tror eksport af inspect resultater til excel er vigtig. Scrolling er dårligt, og excel giver fleksibilitet til at udforske og teste idéer.

## Generelt

Forstå måltotaler bedre:
-   Har vi måltotaler for alle trans-brch kombinationer, når afstemningen går i gang?
-   Lagre? Detaljerede forbrugsgrupper. Opdeling af eksport på dk produceret og reeksport.
-   Tolerancer: Hvordan er tolerancerne cirka for de forskellige trans-brch kombinationer? Er det altid bestemt på transaktions niveau?

## Data examples

-   Make simplified realistic SUT data. Take a subset of products, which are easy to understand and map 

## Løse idéer

-   Kan man lave en funktion, der finder vej fra en anvendelse til en anden? Fx konkret, hvis vi alt i alt vil flytte anvendelse fra medicin fip til endelig anvendelse?
    -   Måske en af flere mulige veje, som brugeren så kan vurdere. Eventuelt constraint af, at man fx kun må flytte på tjenesterne.
    -   En simpel start er funktionalitet til at finde produktoverlappet mellem givne kolonner, og kolonneoverlappet mellem givne produkter.
    -   Se ideer i "balancing_path_finding.md" i mine noter