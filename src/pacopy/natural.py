from typing import Callable

from .newton import NewtonConvergenceError, newton


def natural(
    problem,
    u0,
    lambda0: float,
    callback: Callable,
    lambda_stepsize0: float = 1.0e-1,
    lambda_stepsize_max: float = float("inf"),
    lambda_stepsize_aggressiveness: float = 2.0,
    max_newton_steps: int = 5,
    newton_tol: float = 1.0e-12,
    max_steps: float = float("inf"),
    verbose: bool = True,
    use_first_order_predictor: bool = True,
    milestones=None,
):
    """Natural parameter continuation.

    The most naive parameter continuation. This simply solves :math:`F(u, \\lambda_0)=0`
    using Newton's method, then changes :math:`\\lambda` slightly and solves again using
    the previous solution as an initial guess. Cannot handle turning points.

    Args:
        problem: Instance of the problem class
        u0: Initial guess
        lambda0: Initial parameter value
        callback: Callback function
        lambda_stepsize0 (float): Initial step size
        lambda_stepsize_aggressiveness (float): The step size is adapted after each step
            such that :code:`max_newton_steps` is exhausted approximately. This parameter
            determines how aggressively the the step size is increased if too few Newton
            steps were used.
        lambda_stepsize_max (float): Maximum step size
        max_newton_steps (int): Maxmimum number of Newton steps
        newton_tol (float): Newton tolerance
        max_steps (int): Maximum number of continuation steps
        verbose (bool): Verbose output
        use_first_order_predictor (bool): Once a solution has been found, one can use it
            to bootstrap the Newton process for the next iteration (order 0). Another
            possibility is to use :math:`u - s J^{-1}(u, \\lambda)
            \\frac{df}{d\\lambda}`, a first-order approximation.
        milestones (Optional[Iterable[float]]): Don't step over these values.
    """
    lmbda = lambda0
    if milestones is not None:
        milestones = iter(milestones)

    k = 0
    try:
        u, _ = newton(
            lambda u: problem.f(u, lmbda),
            lambda u, rhs: problem.jacobian_solver(u, lmbda, rhs),
            problem.norm2_r,
            u0,
            tol=newton_tol,
            max_iter=max_newton_steps,
        )
    except NewtonConvergenceError as e:
        print("No convergence for initial step.")
        raise e

    callback(k, lmbda, u)
    k += 1

    lambda_stepsize = lambda_stepsize0
    if milestones is not None:
        milestone = next(milestones)

    while True:
        if k > max_steps:
            break

        if verbose:
            print(
                f"Step {k}: lambda  {lmbda:.3e} + {lambda_stepsize:.3e}  "
                f"->  {lmbda + lambda_stepsize:.3e}"
            )

        # Predictor
        lmbda += lambda_stepsize
        if milestones:
            lmbda = min(lmbda, milestone)
        if use_first_order_predictor:
            du_dlmbda = problem.jacobian_solver(u, lmbda, -problem.df_dlmbda(u, lmbda))
            u0 = u + du_dlmbda * lambda_stepsize
        else:
            u0 = u

        # Corrector
        try:
            u, newton_steps = newton(
                lambda u: problem.f(u, lmbda),
                lambda u, rhs: problem.jacobian_solver(u, lmbda, rhs),
                problem.norm2_r,
                u0,
                tol=newton_tol,
                max_iter=max_newton_steps,
            )
        except NewtonConvergenceError:
            if verbose:
                print(f"No convergence for lambda={lmbda}.")
            lmbda -= lambda_stepsize
            lambda_stepsize /= 2
            continue

        callback(k, lmbda, u)
        k += 1
        if milestones is not None and lmbda == milestone:
            try:
                milestone = next(milestones)
            except StopIteration:
                break
        else:
            lambda_stepsize *= (
                1
                + lambda_stepsize_aggressiveness
                * ((max_newton_steps - newton_steps) / (max_newton_steps - 1)) ** 2
            )
            lambda_stepsize = min(lambda_stepsize, lambda_stepsize_max)
