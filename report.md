# Nedelja 7: jedno kontrolisano poboljšanje RAG sistema

**Par:** Aleksa Cevizović, _(ime drugog člana)_
**Demonstraciju vodi:** _(ime)_
**Izabrana promena:** M1, sečenje po rečenicama

---

## 1. Početno stanje

Projekat smo pre bilo kakve izmene stavili u git (`b29ef48 Week 7 starting point`). Tako `git diff` posle promene pokazuje tačno ono što smo menjali.

Komande:

```
python -m pytest
python -m src.eval_runner --out results/before.json
```

Testovi: **18 passed**. Eval:

```
ID   Category                 Expected Got     Hit  Fact  CitPrec Pass
----------------------------------------------------------------------
E01  supported                answer   answer  yes  yes   0.50    PASS
E02  supported                answer   answer  yes  yes   0.50    PASS
E03  supported                answer   answer  yes  yes   0.50    PASS
E04  chunk-boundary           answer   answer  yes  no    1.00    FAIL
E05  paraphrase               answer   answer  no   no    0.00    FAIL
E06  versioned                answer   answer  no   no    0.00    FAIL
E07  supported                answer   answer  yes  yes   1.00    PASS
E08  supported                answer   answer  yes  yes   0.50    PASS
E09  chunk-boundary           answer   answer  yes  no    1.00    FAIL
E10  unsupported              refuse   answer  -    -     0.00    FAIL
E11  unsupported-near-domain  refuse   answer  -    -     0.00    FAIL
E12  unsupported              refuse   refuse  -    -     -       PASS

Passed: 6/12
Behaviour accuracy: 0.83
Retrieval hit rate (supported): 0.78
Mean citation precision (answered): 0.45
eval_set_sha256: afe46db1e75a0b85bb5c9a93b6763e3b96e5cd7b289e12da6d2671e4d8650064
```

Sistem prolazi 6 od 12 pitanja. Pada na granici chunk-a (E04, E09), na parafrazi (E05), na zastareloj verziji dokumenta (E06) i na dva pitanja na koja bi trebalo da odbije odgovor (E10, E11).

---

## 2. Dokumentovani propusti

Pune izlaze CLI-ja čuvamo u `results/E04-before.txt`, `results/E09-before.txt` i `results/E06-before.txt`.

### Propust 1: E04, granica chunk-a

- **Pitanje:** „How many business days does a laptop replacement take?”
- **Očekivano:** odgovor koji citira deo teksta sa činjenicom „5 business days” iz dokumenta hb-01.
- **Šta se desilo:** sistem jeste našao pravi dokument, ali je citirao `hb-01-chunk-0` i `hb-01-chunk-2`. Nijedan od njih ne sadrži broj dana. Rečenica sa odgovorom je presečena na 140 znakova. Broj dana je završio u `hb-01-chunk-1`, a taj chunk je tek četvrti po oceni (0.1071), čak iza stare polise o radu od kuće. Zato ne ulazi u top 2. U citiranom `hb-01-chunk-2` se vidi ostatak presečene reči: „iness days”.
- **Tip propusta:** chunkovanje.

### Propust 2: E09, granica chunk-a

- **Pitanje:** „Where do I request a replacement laptop and how long does it take?”
- **Očekivano:** odgovor koji citira „5 business days” iz hb-01.
- **Šta se desilo:** isti obrazac kao kod E04. Citirani su `hb-01-chunk-0` (0.2609) i `hb-01-chunk-2` (0.2174), a deo sa brojem dana nije ni među prva četiri rezultata. Pola pitanja („gde”) je pokriveno, jer chunk-2 kaže da se zahtev podnosi u IT portalu, ali „koliko traje” nije.
- **Tip propusta:** chunkovanje.

### Dodatno zapažanje: E06, zastarela verzija

- **Pitanje:** „How many days per week can I work remotely?”
- **Očekivano:** „3 days per week” iz važeće politike hb-03 (2026).
- **Šta se desilo:** oba citata su iz zamenjene politike hb-02 (2024), koja kaže „2 days per week”. Korisnik bi dobio pogrešan broj sa izgledom pouzdanog izvora. Stari tekst je kraći, a ocena se deli dužinom chunk-a, pa kraći tekst sa istim rečima dobija višu ocenu.
- **Tip propusta:** retrieval (metapodaci o verziji se ne koriste).

Ovaj propust ne ciljamo promenom M1. Navodimo ga jer ćemo posle promene proveriti da li se i kako promenio.

---

## 3. Specifikacija promene

_Napisano i commit-ovano pre izmene koda._

| | |
|---|---|
| **Propust** | E04 i E09: tačan dokument je pronađen, ali činjenica „5 business days” je u chunk-u koji ne ulazi u top 2, pa nije citirana. |
| **Hipoteza** | Sečenje na fiksnih 140 znakova seče rečenicu sa odgovorom na dva dela. Nijedan od tih delova nema dovoljno reči iz pitanja da bi bio rangiran visoko. Ako rečenica ostane cela u jednom chunk-u, sadržaće i reči iz pitanja („replacement laptop”, „business days”) i sam odgovor, pa bi trebalo da bude rangirana visoko i citirana. |
| **Promena** | Uvodimo sečenje po rečenicama (`CHUNK_STRATEGY = "sentences"`). Tekst se deli na cele rečenice, koje se pakuju u chunk dok ne pređu `CHUNK_SIZE` (140 znakova). Rečenica koja ne staje počinje novi chunk. Rečenica duža od 140 znakova postaje svoj chunk i ne seče se. Overlap se ne koristi. `CHUNK_SIZE` i `CHUNK_OVERLAP` ostaju nepromenjeni, pa je jedino promenjeno podešavanje `CHUNK_STRATEGY`. |
| **Očekivani efekat** | E04 i E09 prelaze iz FAIL u PASS. Rečenica sa „5 business days” ima 163 znaka, pa postaje zaseban chunk i trebalo bi da bude rangirana među prva dva. |
| **Rizik regresije** | Menja se dužina svih chunk-ova, pa se menjaju sve ocene, ne samo za E04 i E09. (1) Kraći chunk-ovi od jedne rečenice mogu dobiti nesrazmerno visoku ocenu i potisnuti relevantan tekst kod drugih pitanja. (2) Duži chunk od 163 znaka dobija nižu ocenu jer se ocena deli dužinom. (3) Prag odbijanja (0.02) ostaje isti, a ocene se pomeraju, pa se može promeniti ponašanje kod pitanja koja treba odbiti (E10, E11, E12). (4) Bez overlapa, informacija koja zavisi od dve susedne rečenice može da se razdvoji. |
| **Provera** | Pokrećemo ceo eval skup istom komandom (`python -m src.eval_runner --out results/after.json`) i poredimo sa `python -m src.eval_compare results/before.json results/after.json`. Uspeh: E04 i E09 prolaze, nema regresija, otisak eval skupa je isti, a `eval_compare` prijavljuje samo jedno promenjeno podešavanje. Testovi moraju da prolaze. E04 dodatno proveravamo ručno kroz CLI. |

---

## 4. Primenjena promena

_(popunjava se posle izmene: opis i `git diff`)_

## 5. Ponovno merenje

_(tabela iz `results/after.json`)_

## 6. Poređenje

_(izlaz `eval_compare`)_

## 7. Ručna provera kroz CLI

_(E04 posle promene: odgovor i citat)_

## 8. Zaključak, regresije i preostala ograničenja

_(šta se popravilo, šta se pokvarilo, šta ostaje slabo)_

## 9. Komentar para

_(komentar drugog para na tri pitanja iz zadatka)_

## 10. Korišćenje AI asistenta

_(za šta smo koristili asistenta i kako smo proverili ono što je predložio)_

## 11. Doprinos članova

_(ko je šta uradio)_
