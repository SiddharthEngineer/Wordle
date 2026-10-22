"""
Vectorized Wordle solver core.

Patterns are encoded as one base-3 digit per position (0 black, 1 yellow, 2 green),
value sum(d_i * 3**i), so every pattern is a number from 0 to 242.
"""
from functools import lru_cache
from pathlib import Path

import numpy as np
from wordfreq import word_frequency, zipf_frequency

WORDS = np.loadtxt(Path(__file__).parent / "input/valid-wordle-words.txt", dtype=str)

N_PATTERNS = 243
DIGITS = {"b": 0, "y": 1, "g": 2}
LETTERS = "byg"
POWERS = 3 ** np.arange(5)


#pattern code -> "bygbg"
def pattern_string(code):
    out = []
    for _ in range(5):
        out.append(LETTERS[code % 3])
        code //= 3
    return "".join(out)


#"bygbg" -> pattern code, rejecting anything but 5 of b/y/g
def parse_pattern(raw):
    if not isinstance(raw, str) or len(raw) != 5 or any(c not in DIGITS for c in raw):
        raise ValueError(f"Invalid pattern {raw!r}: expected 5 letters of b, y or g.")
    return int(sum(DIGITS[c] * 3 ** i for i, c in enumerate(raw)))


#array of 5-letter words -> (N, 5) uint8 letter codes
def encode(words):
    words = np.asarray(words, dtype=str)
    if words.ndim == 0:
        words = words.reshape(1)
    if len(words) and (np.char.str_len(words) != 5).any():
        raise ValueError("Every word must be 5 lowercase letters a-z.")
    joined = "".join(words.tolist())
    if not joined.isascii():
        raise ValueError("Every word must be 5 lowercase letters a-z.")
    codes = np.frombuffer(joined.encode("ascii"), dtype=np.uint8).reshape(-1, 5)
    if ((codes < 97) | (codes > 122)).any():
        raise ValueError("Every word must be 5 lowercase letters a-z.")
    return codes


#pattern codes for every (guess, solution) pair, from letter codes
def _pattern_codes(g, s):
    codes = np.zeros((len(g), len(s)), dtype=np.uint8)
    #which letters each solution contains, (26, S)
    present = np.zeros((26, len(s)), dtype=bool)
    present[s.T.astype(np.intp) - 97, np.arange(len(s))] = True
    dup = np.array([len(set(row.tolist())) < 5 for row in g], dtype=bool)

    #fast path: no repeated letter in the guess, so yellow = not green and letter in solution
    fast = np.flatnonzero(~dup)
    if len(fast):
        gf = g[fast]
        out = np.zeros((len(fast), len(s)), dtype=np.uint8)
        for i in range(5):
            green = gf[:, i, None] == s[None, :, i]
            yellow = present[gf[:, i].astype(np.intp) - 97] & ~green
            out += green.view(np.uint8) * np.uint8(2 * POWERS[i])
            out += yellow.view(np.uint8) * np.uint8(POWERS[i])
        codes[fast] = out

    #general path: a letter is yellow while the solution has copies not used by greens
    #or by earlier yellows of the same letter
    slow = np.flatnonzero(dup)
    if len(slow):
        gs = g[slow]
        green = gs[:, None, :] == s[None, :, :]  #(G, S, 5)
        not_green = ~green
        out = np.zeros(green.shape[:2], dtype=np.uint8)
        for i in range(5):
            gi = gs[:, i][:, None]
            avail = np.zeros(out.shape, dtype=np.uint8)
            for k in range(5):
                avail += (s[None, :, k] == gi) & not_green[:, :, k]
            earlier = np.zeros(out.shape, dtype=np.uint8)
            for j in range(i):
                earlier += (gs[:, j] == gs[:, i])[:, None] & not_green[:, :, j]
            yellow = not_green[:, :, i] & (avail > earlier)
            out += green[:, :, i].view(np.uint8) * np.uint8(2 * POWERS[i])
            out += yellow.view(np.uint8) * np.uint8(POWERS[i])
        codes[slow] = out
    return codes


#pattern of a single guess against a single solution
def pattern(guess, solution):
    return int(_pattern_codes(encode([guess]), encode([solution]))[0, 0])


#(G, S) uint8 matrix of patterns
def pattern_matrix(guesses, solutions):
    return _pattern_codes(encode(guesses), encode(solutions))


#words consistent with every (guess, "bygbg") row
def filter_candidates(rows, words=WORDS):
    words = np.asarray(words, dtype=str)
    for guess, raw in rows:
        code = parse_pattern(raw)
        words = words[pattern_matrix([guess.lower()], words)[0] == code]
    return words


@lru_cache(maxsize=None)
def _word_frequency(word):
    return word_frequency(word, "en")


@lru_cache(maxsize=None)
def _zipf_frequency(word):
    return zipf_frequency(word, "en")


#probability of each word being the solution: linear word frequency, floored, normalized
def probabilities(words):
    freqs = np.array([_word_frequency(w) for w in words], dtype=float)
    freqs = np.maximum(freqs, 1e-9)
    return freqs / freqs.sum()


#E(|v|) per guess for each weight vector: mean of the non-zero pattern bins over the candidates
def _mean_bins(guesses, candidates, weight_sets, chunk):
    g = encode(guesses)
    cand = encode(candidates)
    outs = [np.empty(len(g), dtype=float) for _ in weight_sets]
    #weights repeated once per guess row of a chunk; the last chunk uses a prefix
    tiled = [np.tile(w, min(chunk, len(g))) for w in weight_sets]
    for start in range(0, len(g), chunk):
        codes = _pattern_codes(g[start:start + chunk], cand)  #(c, S)
        c = codes.shape[0]
        flat = (codes.astype(np.intp) + (N_PATTERNS * np.arange(c))[:, None]).ravel()
        for out, weights in zip(outs, tiled):
            bins = np.bincount(flat, weights=weights[:flat.size], minlength=N_PATTERNS * c)
            bins = bins.reshape(c, N_PATTERNS)
            with np.errstate(invalid="ignore", divide="ignore"):
                out[start:start + c] = bins.sum(axis=1) / (bins > 0).sum(axis=1)
    return outs


def _weights(candidates, weighted):
    if weighted:
        return np.array([_zipf_frequency(w) for w in np.asarray(candidates, dtype=str)], dtype=float)
    return np.ones(len(candidates))


#E(|v|) per guess: mean of the non-zero pattern bins over the candidates
#bins count candidates, or sum their zipf frequency when weighted
def expected_sizes(guesses, candidates, weighted=False, chunk=512):
    return _mean_bins(guesses, candidates, [_weights(candidates, weighted)], chunk)[0]


#remaining words with probability and plain/weighted expected sizes, most likely first
def solve(rows):
    candidates = filter_candidates(rows)
    probs = probabilities(candidates)
    ev, wev = _mean_bins(candidates, candidates, [_weights(candidates, False), _weights(candidates, True)], 512)
    order = np.argsort(-probs, kind="stable")
    return [
        {"word": str(candidates[i]), "probability": float(probs[i]), "ev": float(ev[i]), "wev": float(wev[i])}
        for i in order
    ]
