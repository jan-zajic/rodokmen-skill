#!/usr/bin/env python3
"""Hlídá, jestli jsou příběhy rodů aktuální vůči datům v data/osoby.py.

Použití (z kořene projektu):
  pribehy.py                 přehled: co v kterém příběhu chybí nebo se od poslední aktualizace změnilo
  pribehy.py <příběh> …      podrobně jen pro vybrané příběhy (hlavni, nebo slug rodu: hubnerove, cisarovi …)
  pribehy.py hotovo <příběh> … | vse
                             příběh je aktualizovaný → uloží „otisk“ údajů jeho rodu (data/pribehy/otisky.json)

Příběhy: data/pribeh.md = hlavní rod (web.json → pribeh.rod, jinak nejnižší číslo v LINES),
data/pribehy/<slug rodu>.md = rod z LINES (i vedlejší rody 16+). Členové rodu jsou předci s číslem uvnitř rodu
(stejně jako stránka rodu na webu), jen se stavem doc nebo prob.

Hlásí:
  NOVÍ / NEZMÍNĚNÍ – doložený předek rodu, o kterém příběh nepíše (ani odkazem /osoba/…, ani jménem a příjmením);
  NOVÍ / ZMĚNĚNÍ – předek, který od posledního „hotovo“ v rodu přibyl, nebo se mu změnilo jméno, roky, fakta,
    zápisy či stav.
Po aktualizaci textu spusť „pribehy.py hotovo <příběh>“. kontrola.py pak hlásí jen nové a změněné předky – předky,
které jsi v textu vynechal záměrně (prababička bez dalších údajů), už znovu nehlásí. Dokud příběh potvrzený není,
hlásí kontrola všechny nezmíněné doložené předky.
"""
import hashlib, json, os, re, sys, unicodedata
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OTISKY = os.path.join(DATA, "pribehy", "otisky.json")


def slugify(text):
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def ascii_low(text):
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def gen(k):
    return k.bit_length() - 1


def nacti():
    if not os.path.exists(os.path.join(DATA, "osoby.py")):
        sys.exit("Spusť z kořene projektu rodokmenu (chybí data/osoby.py).")
    ns = {}
    exec(open(os.path.join(DATA, "osoby.py"), encoding="utf-8").read(), ns)
    web = {}
    p = os.path.join(DATA, "web.json")
    if os.path.exists(p):
        try:
            web = json.load(open(p, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            web = {}
    return ns.get("P", {}), ns.get("LINES", {}), ns.get("SAME", {}), web


def pribehy(P, LINES, web):
    """[(klíč, název, soubor, číslo rodu)] pro příběhy, které existují."""
    out = []
    hlavni = (web.get("pribeh") or {}).get("rod") or (min((k for k in LINES if 8 <= k <= 15), default=8))
    if os.path.exists(os.path.join(DATA, "pribeh.md")):
        jmeno = LINES.get(hlavni, ("hlavní rod",))[0]
        out.append(("hlavni", f"hlavní příběh ({jmeno})", os.path.join(DATA, "pribeh.md"), hlavni))
    for k, v in sorted(LINES.items()):
        f = os.path.join(DATA, "pribehy", slugify(v[0]) + ".md")
        if os.path.exists(f):
            out.append((slugify(v[0]), f"příběh {v[0]}", f, k))
    return out


def clenove(P, SAME, k):
    """Předci uvnitř rodu k (k a všichni jeho předci), jen doc/prob a ne zástupné „otec neuveden“."""
    g = gen(k)
    res = []
    for n, p in P.items():
        if not isinstance(n, int) or n < k or n in SAME:
            continue
        if gen(n) >= g and n >> (gen(n) - g) == k and p.get("st") in ("doc", "prob"):
            if p.get("n", "").startswith(("otec neuveden", "matka neuvedena")) or p.get("n") in ("", "?"):
                continue
            res.append(n)
    return sorted(res)


def otisk(p):
    d = json.dumps([p.get("n"), p.get("y"), p.get("st"), p.get("f", []), p.get("r", [])], ensure_ascii=False)
    return hashlib.sha1(d.encode("utf-8")).hexdigest()[:12]


def slugy_webu():
    """{číslo osoby: slug} z posledního exportu webu (web/src/data/site.json), když existuje."""
    p = os.path.join(ROOT, "web", "src", "data", "site.json")
    try:
        lidé = json.load(open(p, encoding="utf-8")).get("people", {})
        return {v["k"]: s for s, v in lidé.items() if isinstance(v, dict) and "k" in v}
    except Exception:  # noqa: BLE001
        return {}


def kmen(w):
    return re.escape(ascii_low(w)[:max(3, min(5, len(w) - 2))])   # „Kaubínková“ ~ „Kaubínkovou“


def zminen(n, p, text_ascii, slugy):
    """Odkaz na osobu (přesný slug z webu), nebo jméno a příjmení těsně u sebe („Annu Spětlíkovou“)."""
    if n in slugy:
        if f"/osoba/{slugy[n]}/" in text_ascii:
            return True
    elif "/osoba/" + slugify(re.sub(r"\(.*?\)|[?…]", " ", p.get("n", ""))) in text_ascii:
        return True
    slova = [w for w in re.findall(r"[^\W\d_]+", re.sub(r"\(.*?\)", " ", p.get("n", ""))) if len(w) > 1]
    if not slova:
        return True
    if len(slova) == 1:   # jen křestní jméno („Kateřina“) – stačí, že ho text obsahuje
        return re.search(r"\b" + kmen(slova[0]), text_ascii) is not None
    vzor = r"\b" + kmen(slova[0]) + r"\w*(?:\W+\w+){0,3}?\W+" + kmen(slova[-1])
    return re.search(vzor, text_ascii) is not None


def stav(vyber=None, podrobne=False):
    """Vrátí [(klíč, název, nezmínění[], změnění[], nový_otisk{})] a vypíše přehled."""
    P, LINES, SAME, web = nacti()
    ot = json.load(open(OTISKY, encoding="utf-8")) if os.path.exists(OTISKY) else {}
    vysledky = []
    slugy = slugy_webu()
    vsechny = pribehy(P, LINES, web)
    for klic, nazev, soubor, k in vsechny:
        if vyber and klic not in vyber:
            continue
        t_ascii = ascii_low(open(soubor, encoding="utf-8").read())
        # předky vedlejšího rodu s vlastním příběhem hlídá jeho příběh, ne příběh nadřazeného rodu
        vlastni = set().union(*[clenove(P, SAME, k2) for _, _, _, k2 in vsechny
                                if k2 > k and k2 >> (gen(k2) - gen(k)) == k] or [set()])
        cl = [n for n in clenove(P, SAME, k) if n not in vlastni]
        nezm = [n for n in cl if P[n].get("st") == "doc" and not zminen(n, P[n], t_ascii, slugy)]
        staré = ot.get(klic, {}).get("osoby")
        zmen = [] if staré is None else [n for n in cl if staré.get(str(n)) != otisk(P[n])]   # i noví (bez otisku)
        vysledky.append((klic, nazev, nezm, zmen, {str(n): otisk(P[n]) for n in cl}))
    return P, vysledky, ot


def jmena(P, ns, kolik=8):
    s = ", ".join(f"{n} {P[n].get('n')}" for n in ns[:kolik])
    return s + (f" a dalších {len(ns) - kolik}" if len(ns) > kolik else "")


def souhrn():
    """Krátké řádky pro kontrola.py."""
    P, vys, ot = stav()
    radky = []
    for klic, nazev, nezm, zmen, _ in vys:
        casti = []
        if klic not in ot:
            if nezm:
                casti.append(f"nezmiňuje doložené předky rodu ({len(nezm)}: {jmena(P, nezm, 4)})")
            casti.append("ještě nebyl potvrzen jako aktuální")
        elif zmen:
            nove = [n for n in zmen if str(n) not in ot[klic]["osoby"]]
            if nove:
                casti.append(f"od poslední aktualizace přibyli předci ({len(nove)}: {jmena(P, nove, 4)})")
            if len(zmen) > len(nove):
                casti.append(f"změnily se údaje předků ({len(zmen) - len(nove)}: {jmena(P, [n for n in zmen if n not in nove], 4)})")
        if casti:
            radky.append(f"PŘÍBĚH: {nazev} – " + "; ".join(casti)
                         + f" → doplň text (reference/pribehy.md, „Udržuj příběhy aktuální“), "
                           f"pak tools/pribehy.py hotovo {klic}")
    return radky


def main():
    a = sys.argv[1:]
    if a and a[0] == "hotovo":
        P, vys, ot = stav(None if a[1:] in ([], ["vse"]) else set(a[1:]))
        if not vys:
            sys.exit("Žádný takový příběh (hlavni, nebo slug rodu – viz pribehy.py bez parametrů).")
        for klic, nazev, nezm, zmen, novy in vys:
            ot[klic] = {"osoby": novy}
            print(f"{nazev}: otisk uložen ({len(novy)} předků)"
                  + (f" – pozor, stále nezmiňuje: {jmena(P, nezm)}" if nezm else ""))
        os.makedirs(os.path.dirname(OTISKY), exist_ok=True)
        with open(OTISKY, "w", encoding="utf-8", newline="\n") as f:
            json.dump(ot, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write("\n")
        return
    P, vys, ot = stav(set(a) if a else None)
    if not vys:
        print("Žádné příběhy (data/pribeh.md, data/pribehy/<slug>.md).")
        return
    for klic, nazev, nezm, zmen, novy in vys:
        print(f"== {nazev} [{klic}] – {len(novy)} předků v rodu"
              + ("" if klic in ot else " – ještě nepotvrzen (pribehy.py hotovo " + klic + ")"))
        for n in nezm:
            print(f"   NEZMÍNĚN  {n:>6} {P[n].get('n')} ({P[n].get('y', '')}) – {'; '.join(P[n].get('f', []))[:140]}")
        for n in zmen:
            print(f"   {'NOVÝ    ' if str(n) not in ot[klic]['osoby'] else 'ZMĚNĚN  '}  {n:>6} {P[n].get('n')} ({P[n].get('y', '')}) – {'; '.join(P[n].get('f', []))[:140]}")
        if not nezm and not zmen:
            print("   aktuální")


if __name__ == "__main__":
    main()
