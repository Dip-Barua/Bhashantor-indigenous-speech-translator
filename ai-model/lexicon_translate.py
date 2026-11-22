#!/usr/bin/env python3
"""
lexicon_translate.py (v2) -- dictionary-based translator learned from your parallel sentences.

Languages: en, bn (Bangla script), bl (Banglish), ccp (Chakma), rmz (Marma)  -- every pair works.

How a sentence is translated (first rule that applies wins)
  1. exact sentence found in the dataset                 -> stored translation      [exact]
  2. very similar sentence found in the dataset          -> its translation         [similar]
  3. otherwise: phrases + words, using
       - multi-word phrases learned from short sentences
       - your manual corrections (lexicon/manual_lexicon.csv) -- always win
       - the learned word dictionary
       - suffix/spelling matching for unseen word forms     e.g. বাজারে -> বাজার
       - pivoting through another language                  e.g. rmz -> bn -> ccp
       - a target-language word-pair model to choose between candidates
       - transliteration/copy for words that are still unknown
  Markers in the output:  word(?) low confidence | word(~) guessed from a related form
                          [word] unknown (not translated)

Commands
  python lexicon_translate.py build                            # learn from ALL rows -> lexicon/
  python lexicon_translate.py eval --split test                # honest score: learn on train only
  python lexicon_translate.py eval --split valid --ablation    # which improvement helps?
  python lexicon_translate.py tr --src bn --dst ccp "আমি বাজারে যাচ্ছি।" [--explain]
  python lexicon_translate.py repl --src bn --dst ccp
"""
import argparse
import csv
import difflib
import math
import pickle
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

try:
    from bn_translit import word as bn_roman
except Exception:  # transliteration is optional
    bn_roman = None

COLS = {"en": "English", "bn": "Bangla", "bl": "Banglish", "ccp": "Chakma", "rmz": "Marma"}
LANGS = list(COLS)
LATIN = {"en", "bl", "ccp", "rmz"}
NULL = "<null>"
DATA = "data/processed/clean_all.csv"
OUT = Path("lexicon")
MANUAL = OUT / "manual_lexicon.csv"
ALT = {"bn": "bl", "bl": "bn"}  # same language, other writing system


# ----------------------------------------------------------------------------
# text helpers
# ----------------------------------------------------------------------------
def tokens(s, lang):
    if lang == "bn":
        return re.findall(r"[\u0980-\u09ff]+", s)
    return re.findall(r"[a-z0-9']+", s.lower())


def end_punct(s):
    s = s.strip()
    return s[-1] if s and s[-1] in "?!.\u0964" else ""


def norm_key(s):
    return re.sub(r"[\s.,!?;:'\"\u0964()\-]+", "", s.lower())


# ----------------------------------------------------------------------------
# IBM Model 1 (word alignment by EM)
# ----------------------------------------------------------------------------
def model1(pairs, iters=8):
    cooc = defaultdict(set)
    for src, tgt in pairs:
        for e in src + [NULL]:
            cooc[e].update(tgt)
    vf = len({f for fs in cooc.values() for f in fs}) or 1
    t = {(f, e): 1.0 / vf for e, fs in cooc.items() for f in fs}
    for _ in range(iters):
        count, total = defaultdict(float), defaultdict(float)
        for src, tgt in pairs:
            es = src + [NULL]
            for f in tgt:
                z = sum(t[(f, e)] for e in es)
                for e in es:
                    c = t[(f, e)] / z
                    count[(f, e)] += c
                    total[e] += c
        for (f, e), c in count.items():
            t[(f, e)] = c / total[e]
    return t


# ----------------------------------------------------------------------------
# the model
# ----------------------------------------------------------------------------
DEFAULTS = dict(exact=True, similar=True, phrases=True, manual=True, stem=True,
                pivot=True, lm=0.8, fallback=True, mark=False)


class LexModel:
    # ---- building ---------------------------------------------------------
    @classmethod
    def build(cls, df, langs=LANGS, iters=8, verbose=True):
        m = cls()
        m.langs = list(langs)
        m.texts = {l: df[COLS[l]].tolist() for l in langs}
        toks = {l: [tokens(x, l) for x in m.texts[l]] for l in langs}
        m.vocab = {l: Counter(w for ts in toks[l] for w in ts) for l in langs}
        T = {}
        for s in langs:
            for d in langs:
                if s != d:
                    pairs = [(a, b) for a, b in zip(toks[s], toks[d]) if a and b]
                    T[(s, d)] = model1(pairs, iters)
                    if verbose:
                        print(f"  aligned {s}->{d}", file=sys.stderr)
        m.lex, m.phrases = {}, {}
        for s in langs:
            for d in langs:
                if s == d:
                    continue
                cnt = Counter()
                ph = defaultdict(Counter)
                for a, b in zip(toks[s], toks[d]):
                    if not a or not b:
                        continue
                    for e in set(a):
                        for f in set(b):
                            cnt[(e, f)] += 1
                    if 2 <= len(a) <= 4:
                        ph[tuple(a)][tuple(b)] += 1
                cands = defaultdict(list)
                for (f, e), p in T[(s, d)].items():
                    if e == NULL:
                        continue
                    score = p * T[(d, s)].get((e, f), 0.0)
                    if score > 0.02:
                        cands[e].append((f, round(score, 4), cnt[(e, f)]))
                m.lex[(s, d)] = {e: sorted(v, key=lambda x: -x[1])[:5] for e, v in cands.items()}
                m.phrases[(s, d)] = {k: v.most_common(1)[0][0] for k, v in ph.items()}
        # target-side bigram language model
        m.uni, m.bi = {}, {}
        for d in langs:
            u, b = Counter(), Counter()
            for ts in toks[d]:
                prev = "<s>"
                for w in ts:
                    u[w] += 1
                    b[(prev, w)] += 1
                    prev = w
                u["<s>"] += 1
            m.uni[d], m.bi[d] = u, b
        m._index()
        m.manual = load_manual()
        return m

    def _index(self):
        self.keys = {}
        for l in self.langs:
            idx = defaultdict(list)
            for i, t in enumerate(self.texts[l]):
                idx[norm_key(t)].append(i)
            self.keys[l] = idx
        self.prefix = {}
        for l in self.langs:
            p = defaultdict(list)
            for w, c in self.vocab[l].most_common():
                for L in range(2, min(len(w), 12) + 1):
                    p[w[:L]].append(w)
            self.prefix[l] = p
        self.bylen = {}
        for l in self.langs:
            bl = defaultdict(list)
            for k in self.keys[l]:
                bl[len(k)].append(k)
            self.bylen[l] = bl

    # ---- saving ------------------------------------------------------------
    def save(self, path):
        d = {k: v for k, v in self.__dict__.items() if k not in ("prefix", "bylen", "keys")}
        with open(path, "wb") as f:
            pickle.dump(d, f)

    @classmethod
    def load(cls, path):
        m = cls()
        with open(path, "rb") as f:
            m.__dict__.update(pickle.load(f))
        m._index()
        m.manual = load_manual()  # always re-read the latest manual corrections
        return m

    # ---- sentence-level lookups -------------------------------------------
    def _target_of(self, rows, d):
        return Counter(self.texts[d][i] for i in rows).most_common(1)[0][0]

    def exact(self, text, s, d):
        rows = self.keys[s].get(norm_key(text))
        return self._target_of(rows, d) if rows else None

    def similar(self, text, s, d, cutoff=0.94):
        k = norm_key(text)
        if len(k) < 6:
            return None
        pool = []
        for L in range(len(k) - 3, len(k) + 4):
            pool += self.bylen[s].get(L, [])
        hit = difflib.get_close_matches(k, pool, n=1, cutoff=cutoff)
        return self._target_of(self.keys[s][hit[0]], d) if hit else None

    # ---- word-level lookups ------------------------------------------------
    def approx(self, w, s, d):
        """closest known source word (inflection / spelling variant) that has a lexicon entry"""
        lex = self.lex[(s, d)]
        min_prefix = max(3, math.ceil(0.6 * len(w)))   # "algeria" must not match "algorithm"
        for L in range(len(w) - 1, min_prefix - 1, -1):
            for k in self.prefix[s].get(w[:L], [])[:60]:
                if k in lex and abs(len(k) - len(w)) <= 3:
                    return k
        if s in LATIN:
            pool = [k for k in lex if k[:1] == w[:1] and abs(len(k) - len(w)) <= 2]
            hit = difflib.get_close_matches(w, pool, n=1, cutoff=0.8)
            if hit:
                return hit[0]
        return None

    def word_options(self, w, s, d, o, orig=None, is_name=False):
        """-> list of (target_tokens, score, kind)"""
        if o["manual"]:
            man = self.manual.get((s, d), {}).get(w)
            if man:
                return [(tuple(man.split()), 1.0, "manual")]
        direct = self.lex[(s, d)].get(w)
        if direct:
            return [((f,), sc, "lex") for f, sc, _ in direct[:3]]
        if o["stem"] and not is_name:
            k = self.approx(w, s, d)
            if k:
                return [((f,), sc * 0.7, "stem") for f, sc, _ in self.lex[(s, d)][k][:2]]
        if o["pivot"] and not is_name:
            best = {}
            for p in ([ALT[s]] if s in ALT else []) + ["bn", "en", "bl"]:
                if p in (s, d) or p not in self.langs:
                    continue
                for mid, sc1, _ in self.lex[(s, p)].get(w, [])[:2]:
                    for f, sc2, _ in self.lex[(p, d)].get(mid, [])[:2]:
                        best[f] = max(best.get(f, 0), sc1 * sc2)
            if best:
                top = sorted(best.items(), key=lambda x: -x[1])[:2]
                return [((f,), sc * 0.6, "pivot") for f, sc in top]
        if o["fallback"]:
            if s == "bn" and d in LATIN and bn_roman:
                return [((bn_roman(w),), 0.05, "copy")]
            if s in LATIN and d in LATIN:
                return [(((orig or w),), 0.05, "copy")]
        return [((f"[{w}]",), 0.01, "unk")]

    def lm_logp(self, d, prev, w):
        u, b = self.uni[d], self.bi[d]
        vocab = len(u) + 1
        pu = (u[w] + 1) / (sum(u.values()) + vocab)
        return math.log((b[(prev, w)] + pu) / (u[prev] + 1.0))

    # ---- translation -------------------------------------------------------
    def translate(self, text, s, d, **opts):
        o = {**DEFAULTS, **opts}
        if o["exact"]:
            hit = self.exact(text, s, d)
            if hit:
                return hit, "exact", []
        if o["similar"]:
            hit = self.similar(text, s, d)
            if hit:
                return hit, "similar", []
        toks = tokens(text, s)
        origs = re.findall(r"[A-Za-z0-9']+", text) if s in LATIN else []
        if len(origs) != len(toks):
            origs = list(toks)
        caps = [bool(o_[:1].isupper()) for o_ in origs] if s in LATIN else [False] * len(toks)
        units, i = [], 0
        while i < len(toks):
            done = False
            if o["phrases"]:
                for L in (4, 3, 2):
                    key = tuple(toks[i:i + L])
                    tgt = self.phrases[(s, d)].get(key) if len(key) == L else None
                    if tgt:
                        units.append((" ".join(key), [(tgt, 1.0, "phrase")]))
                        i += L
                        done = True
                        break
            if not done:
                units.append((toks[i], self.word_options(toks[i], s, d, o, origs[i] if s in LATIN else None, caps[i])))
                i += 1
        # Viterbi over candidates with a target bigram model
        lam = o["lm"]
        prev_states = [("<s>", 0.0, [])]
        for _, cands in units:
            new = []
            for ci, (tg, sc, kind) in enumerate(cands):
                best = None
                for last, tot, path in prev_states:
                    lp = math.log(max(sc, 1e-4))
                    if lam and kind != "unk":
                        lp += lam * self.lm_logp(d, last, tg[0])
                    cand = (tot + lp, path)
                    if best is None or cand[0] > best[0]:
                        best = cand
                new.append((tg[-1], best[0], best[1] + [ci]))
            prev_states = new
        choice = max(prev_states, key=lambda x: x[1])[2] if prev_states else []
        out, detail = [], []
        for (src, cands), ci in zip(units, choice):
            tg, sc, kind = cands[ci]
            word = " ".join(tg)
            detail.append((src, word, kind, round(sc, 3), [" ".join(c[0]) for c in cands]))
            if o["mark"]:
                if kind == "lex" and sc < 0.15:
                    word += "(?)"
                elif kind in ("stem", "pivot", "copy"):
                    word += "(~)"
            out.append(word)
        p = end_punct(text)
        if d == "bn":
            p = "\u0964" if p == "." else p
        elif p == "\u0964":
            p = "."
        res = " ".join(out) + p
        if d == "en" and res:
            res = res[0].upper() + res[1:]
        return res, "words", detail


# ----------------------------------------------------------------------------
# manual corrections (native speaker edits win over everything)
# ----------------------------------------------------------------------------
def load_manual():
    man = defaultdict(dict)
    if MANUAL.exists():
        with open(MANUAL, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                s, d, a, b = (r.get(k, "").strip() for k in ("src", "dst", "source_word", "target_word"))
                if s and d and a and b and not b.startswith("("):
                    man[(s, d)][a] = b
    return man


# ----------------------------------------------------------------------------
# commands
# ----------------------------------------------------------------------------
def cmd_build(df):
    OUT.mkdir(exist_ok=True)
    print("Learning word alignments (takes a minute or two)...", file=sys.stderr)
    m = LexModel.build(df)
    m.save(OUT / "model.pkl")
    for (s, d), table in m.lex.items():
        rows = [{"source_word": e, "suggested_target": c[0][0], "score": c[0][1], "count": c[0][2],
                 "other_candidates": " | ".join(x[0] for x in c[1:])}
                for e, c in sorted(table.items(), key=lambda kv: -m.vocab[s][kv[0]])]
        pd.DataFrame(rows).to_csv(OUT / f"review_{s}-{d}.csv", index=False)
    if not MANUAL.exists():
        MANUAL.write_text("src,dst,source_word,target_word\n"
                          "bn,ccp,বাজার,(write the correct Chakma word here)\n", encoding="utf-8")
    print(f"Model + review files written to {OUT.resolve()}")
    print("Native speaker: open review_<src>-<dst>.csv, copy corrected words into "
          "lexicon/manual_lexicon.csv (src,dst,source_word,target_word). They take effect immediately.")


def score(preds, refs):
    import sacrebleu
    return (sacrebleu.corpus_chrf(preds, [refs], word_order=2).score,
            sacrebleu.corpus_bleu(preds, [refs]).score)


ABLATION = [
    ("v1 (word dictionary only)", dict(exact=False, similar=False, phrases=False, manual=False,
                                       stem=False, pivot=False, lm=0, fallback=False)),
    ("+ stem/spelling match", dict(exact=False, similar=False, phrases=False, manual=False,
                                   stem=True, pivot=False, lm=0, fallback=False)),
    ("+ pivot", dict(exact=False, similar=False, phrases=False, manual=False,
                     stem=True, pivot=True, lm=0, fallback=False)),
    ("+ phrases", dict(exact=False, similar=False, phrases=True, manual=False,
                       stem=True, pivot=True, lm=0, fallback=False)),
    ("+ language model", dict(exact=False, similar=False, phrases=True, manual=False,
                              stem=True, pivot=True, lm=0.8, fallback=False)),
    ("+ copy/translit fallback", dict(exact=False, similar=False, phrases=True, manual=False,
                                      stem=True, pivot=True, lm=0.8, fallback=True)),
    ("+ similar-sentence match (all)", dict(exact=False, similar=True, phrases=True, manual=False,
                                            stem=True, pivot=True, lm=0.8, fallback=True)),
]


def cmd_eval(df, split, directions, ablation, kind="sentence"):
    train = df[df.split == "train"]
    ev = df[(df.split == split) & (df.kind == kind)]
    print("Learning from the TRAIN split only...", file=sys.stderr)
    m = LexModel.build(train, verbose=False)
    Path("results").mkdir(exist_ok=True)
    configs = ABLATION if ablation else [("final", {})]
    rows = []
    for key in directions:
        s, d = key.split("-")
        refs = ev[COLS[d]].tolist()
        for name, opts in configs:
            opts = dict(opts)
            opts["exact"] = False  # held-out sentences never match exactly anyway
            preds = [m.translate(x, s, d, **opts)[0] for x in ev[COLS[s]]]
            chrf, bleu = score(preds, refs)
            rows.append({"direction": key, "config": name, "chrF++": round(chrf, 2), "BLEU": round(bleu, 2)})
            print(rows[-1], flush=True)
    res = pd.DataFrame(rows)
    tag = ("" if kind == "sentence" else "_names") + (".ablation" if ablation else "")
    res.to_csv(f"results/lexicon_scores.{split}{tag}.csv", index=False)
    if ablation:
        print("\nmean chrF++ over the chosen directions:")
        print(res.groupby("config", sort=False)["chrF++"].mean().round(2).to_string())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "eval", "tr", "repl"])
    ap.add_argument("text", nargs="?")
    ap.add_argument("--src", default="bn")
    ap.add_argument("--dst", default="ccp")
    ap.add_argument("--data", default=DATA)
    ap.add_argument("--split", default="test", choices=["valid", "test"])
    ap.add_argument("--directions", nargs="*", default=None)
    ap.add_argument("--ablation", action="store_true")
    ap.add_argument("--kind", default="sentence", choices=["sentence", "name"])
    ap.add_argument("--explain", action="store_true")
    ap.add_argument("--lm", type=float, default=None)
    a = ap.parse_intermixed_args()

    if a.cmd in ("build", "eval"):
        df = pd.read_csv(a.data, dtype=str, keep_default_na=False)
        if a.cmd == "build":
            return cmd_build(df)
        dirs = a.directions or [f"{s}-{d}" for s in LANGS for d in LANGS if s != d]
        return cmd_eval(df, a.split, dirs, a.ablation, a.kind)

    path = OUT / "model.pkl"
    if not path.exists():
        sys.exit("Run first:  python lexicon_translate.py build")
    m = LexModel.load(path)
    extra = {"lm": a.lm} if a.lm is not None else {}

    def run(text):
        res, how, detail = m.translate(text, a.src, a.dst, mark=True, **extra)
        print(f"  {res}    [{how}]")
        if a.explain and detail:
            for src, tgt, kind, sc, alts in detail:
                print(f"     {src:14s} -> {tgt:18s} {kind:7s} score={sc}  options: {', '.join(alts)}")

    if a.cmd == "tr":
        run(a.text)
    else:
        print(f"{a.src} -> {a.dst}   (empty line to quit)")
        while True:
            line = input("> ").strip()
            if not line:
                break
            run(line)


if __name__ == "__main__":
    main()
