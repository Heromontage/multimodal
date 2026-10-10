"""Importable probability calibration for portable saved models."""
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit


class ScoreCalibration:
    """Regularized monotone sigmoid fit to training-only cross-fitted NB scores."""

    def fit(self, scores, y):
        scores = np.asarray(scores)
        self.mean_ = scores.mean()
        self.scale_ = max(scores.std(), 1e-8)
        z = (scores-self.mean_)/self.scale_
        y = np.asarray(y)

        def loss(ab):
            s = ab[0]*z+ab[1]
            err = expit(s)-y
            return (np.sum(np.logaddexp(0, s)-y*s)+.5*ab[0]**2,
                    np.array([np.dot(err, z)+ab[0], err.sum()]))

        fit = minimize(loss, [1., np.log(y.mean()/(1-y.mean()))], jac=True,
                       method='L-BFGS-B', bounds=[(0., None), (None, None)])
        if not fit.success:
            raise RuntimeError(f'Calibration did not converge: {fit.message}')
        self.slope_, self.intercept_ = fit.x
        return self

    def predict(self, scores):
        return expit(self.slope_*(np.asarray(scores)-self.mean_)/self.scale_+self.intercept_)

