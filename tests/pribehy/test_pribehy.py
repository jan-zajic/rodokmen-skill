"""Test hlídání aktuálnosti příběhů (tools/pribehy.py) a jeho hlášek v kontrola.py.

Z kořene repozitáře, adresář s nástroji je argument:
  python3 -I tests/pribehy/test_pribehy.py skills/rodokmen/tools
  (Windows: python -I -X utf8 …)
Postaví dočasný projekt s vymyšlenou rodinou (Novákovi), zkopíruje do něj pribehy.py a kontrola.py a ověří:
nezmínění předci, potvrzení příběhu (hotovo), nový a změněný předek po potvrzení. Nic nestahuje.
"""
import os, shutil, subprocess, sys, tempfile

TOOLS = os.path.abspath(sys.argv[1])
PY = [sys.executable, "-I", "-X", "utf8"]
VYSLEDKY = []


def zapis(cesta, text):
    os.makedirs(os.path.dirname(cesta), exist_ok=True)
    with open(cesta, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def osoby(P):
    return (f"P = {P!r}\nLINES = {{8: ('Novákové', 'Kováři z Holic.'), 9: ('Dvořákové', 'Mlynáři.')}}\n")


def pust(tmp, *args, nastroj="pribehy.py"):
    r = subprocess.run(PY + [os.path.join(tmp, "tools", nastroj), *args], capture_output=True, text=True,
                       encoding="utf-8", cwd=tmp)
    return r.stdout + r.stderr


def over(nazev, podminka, vystup):
    VYSLEDKY.append(bool(podminka))
    print(("OK  " if podminka else "CHYBA ") + nazev)
    if not podminka:
        print("    výstup:", vystup.replace("\n", "\n    "))


P = {
    1: dict(n="Petr Novák", y="* 1990", st="fam"),
    2: dict(n="Josef Novák", y="* 1960", st="fam"),
    4: dict(n="Karel Novák", y="* 1930", st="fam"),
    8: dict(n="Jan Novák", y="1890–1950", st="doc", f=["* 1890 Holice"]),
    16: dict(n="Václav Novák", y="* 1860", st="doc", f=["kovář v Holicích čp. 12"]),
    17: dict(n="Anna Kubíková", y="", st="doc", f=["z Holic"]),
    9: dict(n="Marie Dvořáková", y="* 1895", st="doc"),
    18: dict(n="Josef Dvořák", y="", st="doc"),
}

tmp = tempfile.mkdtemp(prefix="pribehy_")
try:
    zapis(os.path.join(tmp, "data", "osoby.py"), osoby(P))
    zapis(os.path.join(tmp, "data", "zaznamy.json"), "[]")
    zapis(os.path.join(tmp, "data", "pribeh.md"), "---\ntitle: Příběh Nováků\n---\n\n"
          "[Jan Novák](/osoba/jan-novak-1890/) byl synem kováře Václava Nováka z čp. 12.\n")
    zapis(os.path.join(tmp, "data", "pribehy", "dvorakove.md"), "---\ntitle: Příběh Dvořáků\n---\n\n"
          "Mlynářka Marie Dvořáková z Holic.\n")
    os.makedirs(os.path.join(tmp, "tools"))
    for f in ("pribehy.py", "kontrola.py"):
        shutil.copy(os.path.join(TOOLS, f), os.path.join(tmp, "tools", f))

    v = pust(tmp)
    over("hlavní příběh: nezmíněná Anna Kubíková", "NEZMÍNĚN" in v and "Anna Kubíková" in v, v)
    over("hlavní příběh: Václav zmíněn jménem v jiném pádě (Václava Nováka)",
         "Václav Novák" not in v.split("dvorakove")[0], v)
    over("příběh Dvořáků: nezmíněný Josef Dvořák", "Josef Dvořák" in v, v)
    k = pust(tmp, nastroj="kontrola.py")
    over("kontrola hlásí nepotvrzený příběh", "PŘÍBĚH: hlavní příběh (Novákové)" in k and "nebyl potvrzen" in k, k)

    v = pust(tmp, "hotovo", "vse")
    over("hotovo uloží otisky", os.path.exists(os.path.join(tmp, "data", "pribehy", "otisky.json")), v)
    k = pust(tmp, nastroj="kontrola.py")
    over("po potvrzení kontrola příběhy nehlásí", "PŘÍBĚH" not in k, k)

    P2 = dict(P)
    P2[32] = dict(n="Tomáš Novák", y="* 1830", st="doc", f=["sedlák"])
    P2[16] = dict(P[16], f=["kovář v Holicích čp. 12", "† 1920 Holice"])
    zapis(os.path.join(tmp, "data", "osoby.py"), osoby(P2))
    k = pust(tmp, nastroj="kontrola.py")
    over("kontrola hlásí nového předka", "přibyli předci (1: 32 Tomáš Novák)" in k, k)
    over("kontrola hlásí změněné údaje", "změnily se údaje předků (1: 16 Václav Novák)" in k, k)
    over("příběh Dvořáků zůstal aktuální", "příběh Dvořákové" not in k, k)
    v = pust(tmp, "hlavni")
    over("podrobný výpis: NOVÝ a ZMĚNĚN", "NOVÝ" in v and "ZMĚNĚN" in v, v)
    pust(tmp, "hotovo", "hlavni")
    k = pust(tmp, nastroj="kontrola.py")
    over("po dalším potvrzení klid", "PŘÍBĚH" not in k, k)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{sum(VYSLEDKY)} z {len(VYSLEDKY)} v pořádku")
sys.exit(0 if all(VYSLEDKY) else 1)
