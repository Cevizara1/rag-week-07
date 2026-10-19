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

Commit `d54bd75 M1: sentence-aware chunking`. Ceo diff je u `results/m1.diff`.

- `src/chunking.py`: implementirana je funkcija `split_text_by_sentences`. Tekst se deli na rečenice posle `.`, `!` ili `?`, a rečenice se pakuju u chunk dok ne pređu 140 znakova. Rečenica koja ne staje počinje novi chunk, a rečenica duža od 140 znakova ostaje cela.
- `src/config.py`: `CHUNK_STRATEGY = "chars"` je promenjeno u `"sentences"`. Ništa drugo u konfiguraciji nije menjano.
- `tests/test_chunking.py`: dodata su tri testa za novo ponašanje: cele rečenice, pakovanje kratkih rečenica i duga rečenica kao zaseban chunk.

Sve tri izmene služe jednoj nameri: da se tekst ne seče usred rečenice. Testovi samo proveravaju da funkcija radi ono što specifikacija kaže.

Kako sada izgleda dokument hb-01:

| Chunk | Pre (140 znakova, overlap 30) | Posle (po rečenicama) |
|---|---|---|
| 0 | „Laptop replacement: … set up by IT staff with” | „Laptop replacement: broken, lost or stolen laptops can be replaced.” |
| 1 | „op is set up by IT staff … 5 business days. Report lost or sto” | „After manager approval, … handover can take up to 5 business days.” (163 znaka, cela rečenica) |
| 2 | „iness days. Report lost or stolen devices … such as m” | „Report lost or stolen devices to security first. Request a replacement laptop in IT portal under Hardware.” |
| 3 | „ardware. Accessories such as mouse …” | „Accessories such as mouse or headset are ordered through that same form.” |

## 5. Ponovno merenje

Ista komanda: `python -m src.eval_runner --out results/after.json`. Testovi: **21 passed**.

```
ID   Category                 Expected Got     Hit  Fact  CitPrec Pass
----------------------------------------------------------------------
E01  supported                answer   answer  yes  yes   0.50    PASS
E02  supported                answer   answer  yes  yes   0.50    PASS
E03  supported                answer   answer  yes  yes   1.00    PASS
E04  chunk-boundary           answer   answer  yes  yes   1.00    PASS
E05  paraphrase               answer   answer  no   no    0.00    FAIL
E06  versioned                answer   answer  yes  yes   0.50    PASS
E07  supported                answer   answer  yes  yes   1.00    PASS
E08  supported                answer   answer  yes  yes   0.50    PASS
E09  chunk-boundary           answer   answer  yes  yes   1.00    PASS
E10  unsupported              refuse   answer  -    -     0.00    FAIL
E11  unsupported-near-domain  refuse   answer  -    -     0.00    FAIL
E12  unsupported              refuse   refuse  -    -     -       PASS

Passed: 9/12
Behaviour accuracy: 0.83
Retrieval hit rate (supported): 0.89
Mean citation precision (answered): 0.55
eval_set_sha256: afe46db1e75a0b85bb5c9a93b6763e3b96e5cd7b289e12da6d2671e4d8650064
```

## 6. Poređenje

`python -m src.eval_compare results/before.json results/after.json`:

```
Fixed (fail -> pass): E04, E06, E09
Regressed (pass -> fail): none
Unchanged: E01, E02, E03, E05, E07, E08, E10, E11, E12

Summary:
  passed: 6 -> 9 (+3)
  total: 12 -> 12 (+0)
  behaviour_accuracy: 0.8333 -> 0.8333 (+0.0)
  retrieval_hit_rate: 0.7778 -> 0.8889 (+0.1111)
  mean_citation_precision: 0.4545 -> 0.5455 (+0.091)

Changed settings:
  CHUNK_STRATEGY: 'chars' -> 'sentences'
```

Otisak eval skupa je isti pre i posle. Promenjeno je samo jedno podešavanje i alat ne prijavljuje upozorenje.

## 7. Ručna provera kroz CLI

`python -m src.cli --question "How many business days does a laptop replacement take?" --show-retrieved` (ceo izlaz je u `results/E04-after.txt`):

```
Citations:
  hb-01-chunk-1: Equipment replacement (version 2026, current)
  hb-01-chunk-0: Equipment replacement (version 2026, current)

Retrieved:
  0.2069  hb-01-chunk-1: After manager approval, a replacement laptop is set up by IT staff with your files, accounts, email and access rights, and handover can take up to 5 business days.
  0.2000  hb-01-chunk-0: Laptop replacement: broken, lost or stolen laptops can be replaced.
```

Odgovor i citat izgledaju onako kako eval tvrdi: cela rečenica sa „5 business days” je na prvom mestu i citirana je.

## 8. Zaključak, regresije i preostala ograničenja

**Hipoteza je potvrđena.** E04 i E09 su prešli u PASS zato što rečenica sa odgovorom više nije presečena. Kod E09 je efekat čak bolji od očekivanog. Citirana su dva chunk-a koja zajedno pokrivaju oba dela pitanja: „gde” („Request a replacement laptop in IT portal under Hardware”) i „koliko traje” („5 business days”).

**Regresija nema.** Ipak, promena je uticala i na pitanja koja nismo ciljali, jer su se promenile dužine svih chunk-ova:

- **E06 je prošao, ali ne iz pravog razloga.** Nova politika (2026, „3 days”) sada je na prvom mestu, jer je njena prva rečenica ostala sama u kratkom chunk-u i dobila višu ocenu. Stara politika (2024, „2 days”) je i dalje citirana kao druga. Korisnik u odgovoru vidi oba broja. Eval to računa kao prolaz jer je preciznost citata tačno 0.50, koliko je minimum. Uzrok, nepoštovanje verzije dokumenta, nije rešen. To bi rešila promena M5.
- **E03 je bolji:** preciznost citata je porasla sa 0.50 na 1.00, jer su oba citata sada iz dokumenta o budžetu za obuku.
- **E01, E02 i E08 i dalje citiraju jedan nepovezan chunk kao dopunu.** Kod E01 se dopuna promenila: umesto stare citira se nova politika rada od kuće. Prolaze samo zato što je preciznost 0.50.

**Preostala ograničenja:**

1. **E05 (parafraza)** i dalje pada. „Notebook computer” nema nijednu zajedničku reč sa „laptop”, a leksička pretraga ne razume sinonime. Nijedna promena iz menija ovo ne rešava. Bila bi potrebna pretraga po značenju (embeddings) ili preformulisanje pitanja.
2. **E10 i E11** i dalje dobijaju odgovor umesto odbijanja. Prag odbijanja (0.02) je prenizak za E10 (najviša ocena 0.077). E11 („parental leave policy”) ima višu ocenu (0.222) od nekih ispravnih odgovora, jer deli reči „leave” i „policy” sa politikom godišnjeg odmora. Zato samo podizanje praga ne može da ga reši bez novog pogrešnog odbijanja.
3. **Popravka E04 je tesna:** 0.2069 prema 0.2000. Mala promena u tekstu ili pitanju mogla bi da vrati chunk bez činjenice na prvo mesto. Uzrok je to što ocena deli broj poklapanja dužinom chunk-a, pa duža rečenica sa odgovorom dobija nižu ocenu.
4. **Eval meri samo jedan deo pitanja E09.** Proverava se samo „5 business days”, ne i to da li je pokriveno „gde”. To smo ovde proverili ručno.
5. **Bez overlapa** informacija koja zavisi od dve susedne rečenice sada može da završi u dva odvojena chunk-a. Eval skup ne sadrži takvo pitanje, pa ovaj rizik nije izmeren.

## 9. Komentar para

_(komentar drugog para na tri pitanja iz zadatka)_

## 10. Korišćenje AI asistenta

Koristili smo Claude Code za:

- objašnjenje koda projekta i zadatka;
- pregled svih opcija iz menija u odvojenoj privremenoj kopiji projekta, da bismo izabrali promenu;
- nacrt opisa propusta, specifikacije i ovog izveštaja;
- implementaciju funkcije `split_text_by_sentences` i testova.

Kako smo proverili:

- Pregled opcija iz privremene kopije nismo koristili kao dokaz.
- Specifikaciju smo pročitali i commit-ovali pre izmene koda.
- Diff smo pregledali pre commit-a.
- Testove, eval pre i posle i poređenje pokrenuli smo u samom projektu, istim komandama.
- Odgovor za E04 posle promene proverili smo ručno kroz CLI.

Tvrdnje u izveštaju oslanjaju se samo na sačuvane izlaze u `results/`.

_(dopunite svojim rečima šta ste sami proverili)_

## 11. Doprinos članova

_(ko je šta uradio)_
