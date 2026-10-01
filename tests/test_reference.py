"""FABRICATION-DISCLOSURE: mathematical vectors here are test fixtures only."""
import cmath
import math
import unittest
from source.reference.filter_math import exact_weights, group_delay, response, variance_equivalent_span


class FilterMathematicsTests(unittest.TestCase):
    def test_group_delay_against_phase_derivative(self):
        for alpha in (0.02, 0.1, 0.3, 1.0):
            for omega in (0.0, 0.1, 0.5, 2.0):
                h = 1e-6
                numerical = -(cmath.phase(response(alpha, omega + h)) - cmath.phase(response(alpha, omega - h))) / (2 * h)
                self.assertAlmostEqual(group_delay(alpha, omega), numerical, places=6)
        self.assertAlmostEqual(group_delay(0.1, 0), 9)

    def test_exact_time_varying_kernel_matches_recursion(self):
        alphas, inputs, initial = [0.02, 0.3, 0.1, 0.2], [1, 5, 2, 3], 2.5
        value = initial
        for alpha, event in zip(alphas, inputs):
            value = alpha * event + (1 - alpha) * value
        weights, tail = exact_weights(alphas)
        self.assertAlmostEqual(value, sum(w * x for w, x in zip(weights, inputs)) + tail * initial)
        self.assertAlmostEqual(sum(weights) + tail, 1)

    def test_dc_identity_with_small_gains(self):
        for alpha in (1e-12, 1e-100, 1e-300):
            self.assertEqual(response(alpha, 0), 1)
            self.assertTrue(math.isclose(group_delay(alpha, 0), (1 - alpha) / alpha, rel_tol=1e-12))

    def test_span_is_variance_match_for_constant_alpha(self):
        for alpha in (0.02, 0.1, 0.3):
            squared_weight_sum = alpha * alpha / (1 - (1 - alpha) ** 2)
            self.assertAlmostEqual(1 / squared_weight_sum, variance_equivalent_span(alpha))

    def test_invalid_math_inputs_rejected(self):
        for alpha in (0, -0.1, 1.1, True, math.inf, math.nan):
            with self.assertRaises(ValueError):
                response(alpha, 0)

    def test_unrepresentable_span_fails_instead_of_emitting_infinity(self):
        with self.assertRaises(ValueError):
            variance_equivalent_span(1e-320)

    def test_generator_gain_history_preserves_exact_kernel(self):
        expected = exact_weights([0.1, 0.3, 1.0])
        self.assertEqual(exact_weights(a for a in [0.1, 0.3, 1.0]), expected)


if __name__ == "__main__":
    unittest.main()
