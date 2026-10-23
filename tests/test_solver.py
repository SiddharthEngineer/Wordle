import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import solver  # noqa: E402

ALPHABET = "abcdefghijklmnopqrstuvwxyz"


#copy of the original Predictor.calculate_rule, returning "bygbg"
def reference_rule(guess, solution):
    rule = [None] * 5
    counts_true = [solution.count(i) for i in ALPHABET]
    counts_seen = [0] * 26

    for i in range(5):  #greens
        if guess[i] == solution[i]:
            rule[i] = "g"
            counts_seen[ord(guess[i]) - 97] += 1

    for i in range(5):  #rest
        if rule[i] is None:
            index = ord(guess[i]) - 97
            if guess[i] in solution and counts_true[index] > counts_seen[index]:
                rule[i] = "y"
                counts_seen[index] += 1
            else:
                rule[i] = "b"

    return "".join(rule)


@pytest.mark.parametrize("guess, solution, expected", [
    ("speed", "abide", "bbyby"),
    ("geese", "these", "bbggg"),
    ("llama", "hello", "yybbb"),
    ("crane", "crane", "ggggg"),
    ("eerie", "there", "ybybg"),
])
def test_duplicate_letters(guess, solution, expected):
    assert reference_rule(guess, solution) == expected
    assert solver.pattern_string(solver.pattern(guess, solution)) == expected


def test_pattern_matches_reference():
    rng = np.random.default_rng(0)
    guesses = rng.choice(solver.WORDS, 2000)
    solutions = rng.choice(solver.WORDS, 2000)
    for g, s in zip(guesses, solutions):
        assert solver.pattern_string(solver.pattern(g, s)) == reference_rule(g, s), (g, s)


def test_pattern_matrix_matches_pattern():
    rng = np.random.default_rng(1)
    guesses = rng.choice(solver.WORDS, 50, replace=False)
    solutions = rng.choice(solver.WORDS, 60, replace=False)
    matrix = solver.pattern_matrix(guesses, solutions)
    assert matrix.shape == (50, 60)
    assert matrix.dtype == np.uint8
    for i, g in enumerate(guesses):
        for j, s in enumerate(solutions):
            assert matrix[i, j] == solver.pattern(g, s)


def test_filter_candidates_keeps_solution():
    rng = np.random.default_rng(2)
    for _ in range(10):
        solution = str(rng.choice(solver.WORDS))
        rows = [(str(g), reference_rule(str(g), solution)) for g in rng.choice(solver.WORDS, 3)]
        kept = solver.filter_candidates(rows)
        assert solution in kept
        for word in kept:
            for guess, raw in rows:
                assert reference_rule(guess, str(word)) == raw


def test_expected_sizes_regression():
    df = pd.read_csv(ROOT / "output/expected-valid-size.csv").set_index("word")
    got = solver.expected_sizes(["tares", "teras"], solver.WORDS)
    expected = df.loc[["tares", "teras"], "E( |v| )"].to_numpy()
    assert got == pytest.approx(expected, rel=1e-9)


def test_probabilities_and_solve():
    probs = solver.probabilities(solver.WORDS)
    assert probs.sum() == pytest.approx(1.0)
    assert (probs > 0).all()

    rows = solver.solve([])
    assert len(rows) == len(solver.WORDS) == 12972
    assert set(rows[0]) == {"word", "probability", "ev", "wev"}
    probabilities = [r["probability"] for r in rows]
    assert probabilities == sorted(probabilities, reverse=True)


@pytest.mark.parametrize("raw", ["bygb", "bygbx"])
def test_parse_pattern_rejects(raw):
    with pytest.raises(ValueError):
        solver.parse_pattern(raw)


def test_parse_pattern_round_trip():
    for code in range(243):
        assert solver.parse_pattern(solver.pattern_string(code)) == code


@pytest.mark.parametrize("words", [["cr4ne"], ["abcd", "efghij"], ["Crane"], ["cr`ne"]])
def test_encode_rejects(words):
    with pytest.raises(ValueError):
        solver.pattern_matrix(words, ["crane"])
