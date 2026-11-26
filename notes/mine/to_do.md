# To do

## Next up

-   Klimaaftryk, dokumentation.
-   GrønREFORM, overlevering.
-   Tjek at sutlab virker på HR24 TA'er:
    -   Giver rigtige BNP tal.
    -   Vi kan aggregere til FTA klassifikationer.

-   Sort økonomi sagen:
    -   Snak med Anette, Martin Brandstrup og/eller Brian om, hvad den går ud?
    -   Hvordan ser den ud som revisionssag? Hvordan skal den sandsynligvis afstemmes? 

-   balancering og inspecifering af prislag.
    -   snak med christina og brian:
        -   hvordan skal de afbalanceres?
        -   hvad skal de stemme med? hvordan inspiceres de?
        -   momsen.

-   Adjust funktioner til at ændre og flytte rundt på værdier.
    -   adjust_add, adjust_multiply, adjust_substistute
        -   adjust_add(products, transactions, categories, value_layers)
    -   adjust_add_to_area (bedre navn): læg total til område, så områdets sum stiger med totalen. totalen fordeles proportionalt.
    -   adjust_divide_sut & adjust_multiply_sut: funktionalitet til at beregne og anvende faktorer.
        -   herunder beregning af prisindeks og deflatering med disse.
        -   måske særlige dataklasser og funktioner til at beregne, indeholde, inspicere og anvende faktorer.
    -   snak med christina og brian:
        -   hvilken funktionalitet har man brug for?
        -   hvordan skal det interagere med prislag?

-   Hvad skal jeg lave for at få branche konverteringen til at fungere?
    -   Dimensions disaggregering er for kompliceret og forskelligartet til at integrere i sutlab.
        -   I stedet brug claude til at forbedre mondrian. Anvend mondrian til disaggregeringen.
    -   Sørg for det spiller sammen med GrønREFORM behovene.
    -   Træk branche aggregering nøgle og grøn reform disaggregering metadata ud fra dst pc.

-   inspect_aggregates funktioner
    -   branchers bvt
    -   Inkluder mulighed for at have df i sut med supplerende branchefordelt information:
        -   LBT, andre produktionsskatter og subsidier, kapitalapparat, etc.
        -   Rollemapping af kolonnenavne, ligesom for sut kolonner.
    -   bvt dekomponering, hvis supplemerende data
    -   branchers produktivitet, hvis TA'er har beskæftigelses data
    -   noget med kapital apparat
    -   inspect_aggregates_real
    -   snak med michael

-   Inspektions funktion til at identificere tidsserier, der udvikler sig underligt, se nedenfor.

-   deflatering og chain linking

-   ras-sut

-   allow for asset classification, so investment can have asset classification in their category dimension (instead of using transactions to distinguish asset classes)


## Underlige tidsserier og identifikation af om revisionsstrukturen ændrer sig over tid

Vi har brug for et redskab til at undersøge om de strukturelle revisioner ændrer sig gennem årene.

Med andre ord skal vi kunne vurdere om revisionernes struktur er den samme.

inspect_sut_comparison beregner revisioner. Men hvordan finder vi ud af, om strukturen er bevaret?

* se om det er de samme kolonner og produkter, der alt i alt ændrer sig mest.
* se om de ændrer sig på samme måde.
* hvis ja, kan vi nøjes med at se på, hvordan de eg ændrer sig i 2019, og hvis vi er tilfredse med denne ændring, kan vi erklære os tilfredse med det hele.

**Bedre tilgang, tror jeg:**

* Generelt værktøj til at finde "underlige" udviklinger i tidsserierne. Dette kan være ændringer i totaler eller i strukturen. For produkter og for kolonner.
* Dette værktøj kan køre på enhver ta serie.
* Vi kan køre dette værktøj på de reviderede ta'er (eller direkte på revisionerne), eventuelt i aggregeret udgave, for at finde underlige udviklinger.
* Hvis der ikke er (nye) underlige udviklinger, så kan vi nøjes med at undersøge 2019.
* Vi kan også køre dette værktøj på de ureviderede ta'er for at få en baseline for underlighed i tidsserierne.

Snak med Michael og eventuelt andre fra model gruppen.

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