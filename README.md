# Analiza potencjału lokalizacyjnego — dataplace.ai 2026

**Sławomir Strzelec** | [portfolio](https://slastrzelec.github.io/portfolio)

---

## Co zostało zrobione i dlaczego tak

Zadanie potraktowałem jako realny brief biznesowy — właściciel sieci sklepów spożywczych w regionie Śląsk/Kraków szuka miejsc na ekspansję. Zamiast skupiać się na optymalizacji hiperparametrów, skupiłem się na **logice analitycznej i jakości decyzji** na każdym etapie.

---

## Dane i połączenia

Trzy źródła danych obsługiwane jednocześnie:

- **Snowflake** — 435 mln sygnałów mobilnych (`RECRUITMENT_TRACES`). Kluczowa decyzja: żadne dane nie są ściągane lokalnie. Cały foot traffic agregowany SQL-em po stronie serwera z użyciem `ST_DISTANCE` i filtrowania przez bbox obszaru analizy. Dane wiarygodne dla okresu **1–7 lipca 2020** (wcześniejsze daty to faza uruchamiania systemu — wykryte w EDA).
- **AWS S3** — 955k budynków (geometrie WKT) i 450k rekordów demograficznych na poziomie adresowym.
- **Pliki CSV** — sklepy klienta, konkurencja, POI, granica obszaru.

---

## Feature Engineering — dlaczego takie cechy

Dla każdej lokalizacji obliczam cechy w **buforze 500m** (EPSG:2180 — układ metryczny PL-1992, nie stopnie). Bufor 500m to standard "catchment area" dla małego sklepu spożywczego.

**Cechy wymagane przez zadanie (23):**

| Grupa | Cechy | Decyzja |
|---|---|---|
| Foot traffic | signal_count, unique_users, peak_morning_signals | Agregacja SQL w Snowflake — `ST_DISTANCE` + bbox pre-filter |
| Zabudowa | building_count, residential/commercial_count, building_density | GeoPandas buffer + sjoin na geometriach WKT; reprojekcja do EPSG:2180 przed buforem |
| Demografia | pop_total, pop_households, avg_hh_size | Spatial join populacji adresowej do buforów |
| POI | poi_* per kategoria, poi_total | Bufor 1km — 500m było za mały przy rzadkich danych POI (tylko 335 punktów) |
| Konkurencja | competitor_count, dist_nearest_competitor_m | Count w buforze + odległość euklidesowa do najbliższego |

**Cechy dodatkowe (8) — własna inicjatywa:**

Zaobserwowałem że cechy bazowe nie wystarczają do dobrego modelu. Dodałem:
- `dist_nearest_client_m`, `nearest_client_revenue` — informacja o własnej sieci okazała się **najsilniejszym predyktorem**. Uzasadnienie: sieć świadomie lokuje sklepy w dobrych obszarach, więc sąsiedni sklep jest proxy dla jakości lokalizacji.
- `residential_ratio`, `commercial_ratio` — charakter zabudowy ważniejszy niż sama liczba budynków
- `pop_density`, `peak_ratio`, `signals_per_user` — cechy pochodne z istniejących kolumn

---

## Model — dlaczego Ridge, nie XGBoost

Porównałem 4 modele na dwóch zestawach cech:

| Model | 23 cechy CV R² | 31 cech CV R² |
|---|---|---|
| Ridge | -0.315 | **+0.393** |
| XGBoost | -0.175 | +0.339 |
| Random Forest | -0.065 | +0.215 |
| SVR | -0.109 | -0.109 |

**Dlaczego Ridge wygrał:** 50 próbek treningowych to za mało dla XGBoost — model się przeuczał. Ridge z regularyzacją L2 radzi sobie znacznie lepiej przy małych zbiorach danych i dużej liczbie cech. Dodatkowe cechy przestrzenne podniosły R² z wartości ujemnych do **0.393**.

**Uczciwa ocena:** R²=0.393 przy 50 próbkach to sensowny wynik, ale model należy traktować jako **narzędzie rankingowe**, nie prognozę przychodów. Wyniki whitespotu interpretuję as-is.

**SHAP:** Najważniejsze cechy to `nearest_client_revenue` (+) i `dist_nearest_client_m` (-) — im bliżej własnej sieci i im lepiej zarabia sąsiedni sklep, tym wyższy predykowany przychód.

---

## Whitespot — jak wyznaczam top lokalizacje

1. Siatka punktów co 500m na obszarze analizy → **28,077 kandydatów**
2. Feature engineering dla każdego punktu (te same cechy co model)
3. Predykcja modelem Ridge + normalizacja do score 0–32.2
4. Filtrowanie: min 800m od własnej sieci, min 150m od konkurencji, min 500 osób, min 50 budynków → **4,837 lokalizacji**

**Top rekomendacje:**

| Rank | Adres | Score | Pop 500m |
|---|---|---|---|
| 1 | ul. 3 Maja, Załęskie Przedmieście, Katowice | 32.2 | 3,232 |
| 2 | ul. Sądowa, Załęskie Przedmieście, Katowice | 31.4 | 3,020 |
| 3 | ul. Bulwar Kurlandzki, Kazimierz, Kraków | 29.3 | 3,561 |

---

## Bonus — aplikacja Streamlit

Zamiast statycznego dashboardu w Looker Studio zbudowałem interaktywną aplikację która pozwala klientowi samodzielnie eksplorować whitespoty z filtrami (score, populacja, odległość od konkurencji, brand konkurencji).

🔗 [Link do aplikacji po deployu](https://dataplace-whitespot-analysis.streamlit.app/)

🔗 [Link do aplikacji po deployu](https://dataplace-whitespot-analysis.streamlit.app/)