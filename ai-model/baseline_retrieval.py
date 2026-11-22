#!/usr/bin/env python3
"""
baseline_retrieval.py -- the simplest possible "translator": for every test
sentence find the most similar *training* sentence (char n-gram TF-IDF) and
return its translation.  Any real model must beat this score.

Run:  python baseline_retrieval.py                 # all directions, test set
      python baseline_retrieval.py --split valid
      python baseline_retrieval.py --directions en-ccp ccp-en bn-ccp
"""
import argparse
from pathlib import Path

import pandas as pd
import sacrebleu
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

LANG_COLS = {"en": "English", "bn": "Bangla", "bl": "Banglish", "ccp": "Chakma", "rmz": "Marma"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/processed/clean_all.csv")
    ap.add_argument("--outdir", default="results")
    ap.add_argument("--split", default="test", choices=["valid", "test"])
    ap.add_argument("--kind", default="sentence", choices=["sentence", "name"],
                    help="which rows to score (names are scored separately)")
    ap.add_argument("--directions", nargs="*", default=None,
                    help="e.g. en-ccp bn-rmz ; default = all 20")
    args = ap.parse_args()

    df = pd.read_csv(args.data, dtype=str, keep_default_na=False)
    train = df[df.split == "train"]
    evalset = df[(df.split == args.split) & (df.kind == args.kind)]
    langs = list(LANG_COLS)
    directions = args.directions or [f"{s}-{t}" for s in langs for t in langs if s != t]

    out = Path(args.outdir)
    out.mkdir(exist_ok=True)
    rows = []
    for d in directions:
        s, t = d.split("-")
        sc, tc = LANG_COLS[s], LANG_COLS[t]
        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), lowercase=True)
        X_train = vec.fit_transform(train[sc])
        X_eval = vec.transform(evalset[sc])
        preds = []
        for start in range(0, X_eval.shape[0], 500):  # chunked to save memory
            sims = linear_kernel(X_eval[start:start + 500], X_train)
            preds.extend(train[tc].values[sims.argmax(axis=1)])
        refs = evalset[tc].tolist()
        chrf = sacrebleu.corpus_chrf(preds, [refs], word_order=2)  # chrF++
        bleu = sacrebleu.corpus_bleu(preds, [refs])
        rows.append({"direction": d, "chrF++": round(chrf.score, 2),
                     "BLEU": round(bleu.score, 2), "n": len(refs)})
        pd.DataFrame({"id": evalset["ID"].values, "source": evalset[sc].values,
                      "prediction": preds, "reference": refs}
                     ).to_csv(out / f"retrieval.{args.split}{"" if args.kind=="sentence" else "_names"}.{d}.tsv", sep="\t", index=False)
        print(f"{d:8s} chrF++={chrf.score:6.2f}  BLEU={bleu.score:6.2f}")

    res = pd.DataFrame(rows)
    res.to_csv(out / f"retrieval_scores.{args.split}{"" if args.kind=="sentence" else "_names"}.csv", index=False)
    print("\nSaved:", (out / f"retrieval_scores.{args.split}{"" if args.kind=="sentence" else "_names"}.csv").resolve())


if __name__ == "__main__":
    main()
