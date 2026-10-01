"""Exact EMA arithmetic and constant-alpha diagnostics. No empirical claims.

For variable alpha the recursive operator is time-varying. Its exact weights
must be computed from the actual gain history; a frozen transfer function is
only the response of a different, constant-coefficient operator.
"""
import math


def validate_alpha(alpha):
    if isinstance(alpha, bool) or not isinstance(alpha, (int, float)) or not math.isfinite(alpha) or not 0 < alpha <= 1:
        raise ValueError("alpha must be finite and in (0,1]")


def response(alpha, omega):
    validate_alpha(alpha)
    if not math.isfinite(omega):
        raise ValueError("nonfinite frequency")
    pole = 1 - alpha
    # Avoid cancellation of 1-p at DC for very small positive alpha.
    denominator = complex(alpha + 2 * pole * math.sin(omega / 2) ** 2, pole * math.sin(omega))
    return alpha / denominator


def group_delay(alpha, omega):
    validate_alpha(alpha)
    if not math.isfinite(omega):
        raise ValueError("nonfinite frequency")
    pole = 1 - alpha
    sine_squared = math.sin(omega / 2) ** 2
    scale = math.hypot(alpha, 2 * math.sqrt(pole) * math.sin(omega / 2))
    value = (pole * (alpha - 2 * sine_squared) / scale) / scale
    if not math.isfinite(value):
        raise ValueError("group delay exceeds floating-point range")
    return value


def variance_equivalent_span(alpha):
    """Match steady-state variance to a length-L arithmetic mean.

    L=(2-alpha)/alpha assumes constant gain, independent equal-variance input
    noise and decay of initialization. L need not be integer. It is not a hard
    memory window, elapsed-time horizon or a match for correlated inputs.
    """
    validate_alpha(alpha)
    value = (2 - alpha) / alpha
    if not math.isfinite(value):
        raise ValueError("variance-equivalent span exceeds floating-point range")
    return value


def exact_weights(alphas):
    """Return (weights on x[0..n-1], remaining weight on initial state).

    y[n] = product(1-alpha) * y[-1] + sum(weights[i] * x[i]).
    These weights are valid for a supplied gain trajectory. Dependence of that
    trajectory on inputs/state can make the complete system nonlinear; an
    externally specified trajectory gives a linear time-varying recursion.
    """
    alphas = list(alphas)
    for alpha in alphas:
        validate_alpha(alpha)
    weights = [0.0] * len(alphas)
    survival = 1.0
    for index in range(len(alphas) - 1, -1, -1):
        weights[index] = alphas[index] * survival
        survival *= 1 - alphas[index]
    return weights, survival
