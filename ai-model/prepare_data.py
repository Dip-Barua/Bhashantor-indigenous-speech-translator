#!/usr/bin/env python3
"""
prepare_data.py  --  clean, audit, split and build multilingual training files.

Input : data/raw/dataset.csv   (ID, English, Bangla, Banglish, Chakma, Marma)
Output: data/processed/...     (see README.md)

Run:    python prepare_data.py
        python prepare_data.py --audit-size 400 --seed 42 --langs en bn ccp rmz
"""
import argparse
import itertools
import json
import random
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import pandas as pd

# short code -> column name in the CSV
LANG_COLS = {"en": "English", "bn": "Bangla", "bl": "Banglish", "ccp": "Chakma", "rmz": "Marma"}
ROMAN_COLS = ["Banglish", "Chakma", "Marma"]  # romanised columns -> lowercase
ALL_TEXT_COLS = ["English", "Bangla", "Banglish", "Chakma", "Marma"]


# ----------------------------------------------------------------------------
# cleaning helpers
# ----------------------------------------------------------------------------
def clean_text(s: str, lower: bool = False) -> str:
    s = unicodedata.normalize("NFC", str(s))
    # Bangla nukta letters: make them precomposed so the same letter is always
    # the same code point (NFC leaves them decomposed).
    s = s.replace("\u09a1\u09bc", "\u09dc").replace("\u09a2\u09bc", "\u09dd")
    s = s.replace("\u09af\u09bc", "\u09df")
    s = s.replace("\u00a0", " ").replace("\u200c", "").replace("\u200d", "")
    s = s.replace("\u2019", "'").replace("\u2018", "'")
    s = s.replace("\u201c", '"').replace("\u201d", '"')
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s+([,.!?;:।])", r"\1", s)  # no space before punctuation
    if lower:
        s = s.lower()
    return s


def group_key(s: str) -> str:
    """Punctuation/case-insensitive key, used so near-identical sentences stay
    together in one split (prevents train/test leakage)."""
    return re.sub(r"[\s.,!?;:'\"\u0964()\-\u2013\u2014]+", "", s.lower())


def n_words(s: str) -> int:
    return len(s.split())


# ----------------------------------------------------------------------------
# grouping (union-find over English-key and Bangla-key)
# ----------------------------------------------------------------------------
class DSU:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def build_groups(df: pd.DataFrame) -> pd.Series:
    dsu = DSU(len(df))
    for col in ("English", "Bangla"):
        first_seen = {}
        for i, key in enumerate(df[col].map(group_key)):
            if key in first_seen:
                dsu.union(first_seen[key], i)
            else:
                first_seen[key] = i
    return pd.Series([dsu.find(i) for i in range(len(df))], index=df.index, name="group")


def split_groups(df, valid_frac, test_frac, seed):
    rng = random.Random(seed)
    groups = defaultdict(list)
    for idx, g in df["group"].items():
        groups[g].append(idx)
    gids = list(groups)
    rng.shuffle(gids)
    n = len(df)
    n_valid, n_test = round(n * valid_frac), round(n * test_frac)
    split = {}
    c_valid = c_test = 0
    for g in gids:
        size = len(groups[g])
        if c_test < n_test:
            name, c_test = "test", c_test + size
        elif c_valid < n_valid:
            name, c_valid = "valid", c_valid + size
        else:
            name = "train"
        for idx in groups[g]:
            split[idx] = name
    return pd.Series(split, name="split")


# ----------------------------------------------------------------------------
# flags for human review
# ----------------------------------------------------------------------------
def flag_rows(df: pd.DataFrame) -> pd.DataFrame:
    reasons = defaultdict(list)
    for i, r in df.iterrows():
        for c in ALL_TEXT_COLS:
            if not r[c]:
                reasons[i].append(f"empty_{c}")
        for c in ("Banglish", "Chakma", "Marma"):
            if re.search(r"[^\x00-\x7f]", r[c]):
                reasons[i].append(f"non_ascii_{c}")
        wc_ck, wc_bl = n_words(r["Chakma"]), max(n_words(r["Banglish"]), 1)
        if abs(wc_ck - wc_bl) >= 2 and (wc_ck / wc_bl > 2 or wc_ck / wc_bl < 0.5):
            reasons[i].append("chakma_length_mismatch")
        wc_mr, wc_en = n_words(r["Marma"]), max(n_words(r["English"]), 1)
        if abs(wc_mr - wc_en) >= 2 and (wc_mr / wc_en > 3 or wc_mr / wc_en < 0.34):
            reasons[i].append("marma_length_mismatch")
        for c in ("Chakma", "Marma"):
            if group_key(r[c]) in (group_key(r["English"]), group_key(r["Banglish"])):
                reasons[i].append(f"{c}_copy_of_english_or_banglish")
        if group_key(r["Chakma"]) == group_key(r["Marma"]):
            reasons[i].append("chakma_equals_marma")
    out = df.loc[list(reasons), ["ID", "English", "Bangla", "Chakma", "Marma"]].copy()
    out["reasons"] = ["; ".join(reasons[i]) for i in out.index]
    return out


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="data/raw/dataset.csv")
    ap.add_argument("--outdir", default="data/processed")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--valid-frac", type=float, default=0.10)
    ap.add_argument("--test-frac", type=float, default=0.10)
    ap.add_argument("--audit-size", type=int, default=400)
    ap.add_argument("--langs", nargs="+", default=["en", "bn", "bl", "ccp", "rmz"],
                    choices=list(LANG_COLS))
    ap.add_argument("--train-per-direction", type=int, default=0,
                    help="if >0, keep only this many training pairs per direction "
                         "(keeps Colab training time manageable with 5 languages)")
    ap.add_argument("--drop-flagged", action="store_true",
                    help="exclude flagged rows from train/valid/test (default: keep, "
                         "review flagged_rows.csv first)")
    args = ap.parse_args()

    out = Path(args.outdir)
    (out / "eval").mkdir(parents=True, exist_ok=True)

    raw = pd.read_csv(args.input, dtype=str, keep_default_na=False)
    missing = [c for c in ["ID"] + ALL_TEXT_COLS if c not in raw.columns]
    if missing:
        raise SystemExit(f"Missing columns in CSV: {missing}")

    df = raw.copy()
    for c in ALL_TEXT_COLS:
        df[c] = raw[c].map(lambda s: clean_text(s, lower=(c in ROMAN_COLS)))
    df["ID"] = raw["ID"].str.strip()

    # --- flags + audit sample --------------------------------------------
    flagged = flag_rows(df)
    flagged.to_csv(out / "flagged_rows.csv", index=False)

    audit = df.sample(n=min(args.audit_size, len(df)), random_state=args.seed)
    audit = audit[["ID", "English", "Bangla", "Chakma", "Marma"]].copy()
    for c in ("chakma_ok(Y/N)", "marma_ok(Y/N)", "corrected_chakma",
              "corrected_marma", "notes"):
        audit[c] = ""
    audit.to_csv(out / "audit_sample.csv", index=False)

    # --- optional drop -----------------------------------------------------
    if args.drop_flagged:
        df = df[~df["ID"].isin(set(flagged["ID"]))].reset_index(drop=True)

    # --- grouped, leakage-safe split ----------------------------------------
    df["group"] = build_groups(df)
    df["split"] = split_groups(df, args.valid_frac, args.test_frac, args.seed)
    df.drop(columns=["group"]).to_csv(out / "clean_all.csv", index=False)

    # leakage check (must be zero)
    leak = {}
    for col in ("English", "Bangla"):
        keys = {s: set(df.loc[df.split == s, col].map(group_key)) for s in
                ("train", "valid", "test")}
        leak[col] = {
            "train&valid": len(keys["train"] & keys["valid"]),
            "train&test": len(keys["train"] & keys["test"]),
            "valid&test": len(keys["valid"] & keys["test"]),
        }
    assert all(v == 0 for d in leak.values() for v in d.values()), leak

    # --- tagged multilingual pairs ------------------------------------------
    directions = [(s, t) for s, t in itertools.product(args.langs, repeat=2) if s != t]
    for split in ("train", "valid", "test"):
        sub = df[df.split == split]
        records = []
        for s, t in directions:
            sc, tc = LANG_COLS[s], LANG_COLS[t]
            for _, r in sub.iterrows():
                if r[sc] and r[tc]:
                    records.append({
                        "id": r["ID"], "direction": f"{s}-{t}",
                        "source": f"<2{t}> {r[sc]}", "source_plain": r[sc],
                        "target": r[tc],
                    })
        pairs = pd.DataFrame(records)
        if split == "train":
            if args.train_per_direction > 0:
                pairs = (pairs.groupby("direction", group_keys=False)
                         .apply(lambda g: g.sample(n=min(len(g), args.train_per_direction),
                                                   random_state=args.seed)))
            pairs = pairs.sample(frac=1.0, random_state=args.seed)  # shuffle
        pairs.to_csv(out / f"{split}_all_directions.tsv", sep="\t", index=False)
        pairs.to_json(out / f"{split}_all_directions.jsonl", orient="records",
                      lines=True, force_ascii=False)
        if split != "train":
            for d, g in pairs.groupby("direction"):
                g.to_csv(out / "eval" / f"{split}.{d}.tsv", sep="\t", index=False)

    stats = {
        "rows_total": len(df),
        "rows_per_split": df["split"].value_counts().to_dict(),
        "flagged_rows": len(flagged),
        "flag_reasons": flagged["reasons"].str.split("; ").explode().value_counts().to_dict(),
        "directions": [f"{s}-{t}" for s, t in directions],
        "leakage_check_all_zero": leak,
        "seed": args.seed,
    }
    (out / "stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False),
                                    encoding="utf-8")
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    print(f"\nDone. Files written to: {out.resolve()}")
    print("NEXT: have a native speaker fill audit_sample.csv and review flagged_rows.csv")


if __name__ == "__main__":
    main()
