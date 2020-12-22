from sklearn.pipeline import Pipeline


class OnlinePipeline(Pipeline):
    """
    A Pipeline that supports online training through partial_fit

    Consider:
        https://github.com/scikit-learn/scikit-learn/issues/3299
        http://scikit-learn.org/stable/modules/scaling_strategies.html#incremental-learning
    """

    def __init__(self, steps, safe=False):
        self.safe = safe
        super(OnlinePipeline, self).__init__(steps)

    def partial_fit(self, X, y=None):
        """
        Apply partial_fit to all steps.

        Note this will fail if a step's estimator does not
        support partial_fit. You can avoid failing by making
        the OnlinePipeline(safe=True), at the risk of introducing
        unwanted semantic differences

        :param X: the X
        :param y: the y
        :return: self
        """
        for i, step in enumerate(self.steps):
            name, est = step
            if self.safe and not hasattr(est, 'partial_fit'):
                # we allow to be safe on all but the last step
                # i.e. only transformers are ok to not have a partial_fit
                if i < len(self.steps) - 1:
                    continue
            est.partial_fit(X, y)
            if i < len(self.steps) - 1:
                # pass on results to next step
                X = est.transform(X)
        return self
