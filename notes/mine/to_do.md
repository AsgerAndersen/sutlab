# To do

## Next up

-   funktion, der kan kaldes på et inpektion objekt, så det sammenlignes med et andet inspektion objekt af samme type.
    -   diff field, hvorunder forskellene på alle objekternes tabeller ligger
    -   rel field, hvorunder de relative ændringer mellem alle objekternes tabeller ligger

-   Lav ubance tjeks, så de også kan inkludere alle år.

-   Inspektions funktioner til at lave overblik over hele tidsserien
    -   branchers bvt

-   Adjust funktioner til at ændre og flytte rundt på værdier.
-   adjust_substitute_sut funktion til at skifte del af SUT ud (fx til revisioner af energiprodukter).
-   adjust_subtract_sut til at trække en sut fra en anden (burde bare kunne implementeres ved at gange minus -1 på den sut, der skal trækkes fra og så bruge adjust_add_sut).

-   aggregate og disaggregate funktioner til kategoriske dimensioner.
    -   se på grønreform og sammentænk

-   balancering af prislag

-   deflatering og chain linking

-   ras-sut

-   Flere inspektionsfunktioner
    -   inspect_price_layers_balances
        -   funktion til at tjekke balancer for prislag
    -   tabel navne og summary funktioner for de nuværende inspektions funktioner
    -   docstring delegering til alle delegerede funktioner.

## Spørgsmål
-   Hvordan skal balancing funktionerne forholde sig til negative tal? Og lagre specifikt. Skal de som udgangspunkt ikke ændres, medmindre afstemmerne gør det "manuelt" vha flyt funktioner?
-   Hvordan skal vi arbejde med lagre?

## Data examples

-   Make simplified realistic SUT data. Take a subset of products, which are easy to understand and map 
-   Aggregate products to IO-consistent classification.

## Løse idéer

-   Kan man lave en funktion, der finder vej fra en anvendelse til en anden? Fx konkret, hvis vi alt i alt vil flytte anvendelse fra medicin fip til endelig anvendelse?
    -   Måske en af flere mulige veje, som brugeren så kan vurdere. Eventuelt constraint af, at man fx kun må flytte på tjenesterne.
    -   En simpel start er funktionalitet til at finde produktoverlappet mellem givne kolonner, og kolonneoverlappet mellem givne produkter.
    -   Se ideer i "balancing_path_finding.md" i mine noter