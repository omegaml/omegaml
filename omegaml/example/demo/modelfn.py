

def create_model():
    import numpy as np

    X = np.random.randint(0, 100, (100,)).reshape(-1, 1)
    Y = X * 2

    from sklearn.linear_model import LinearRegression

    reg = LinearRegression()
    reg.fit(X, Y)
    return reg
