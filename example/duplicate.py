# train a model to learn to duplicate numbers
import pandas as pd
import numpy as np
import os
from omegaml import Omega
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.datasets import load_iris

om = Omega()
om.runtime.celeryapp.conf.CELERY_ALWAYS_EAGER = False
os.environ['DJANGO_SETTINGS_MODULE'] = ''

# create a data frame with x, y
x = np.array(range(0, 10))
y = x * 2
df = pd.DataFrame(dict(x=x, y=y))

# prepare and store data for training the model
X = df[['x']]
Y = df[['y']]
om.datasets.put(X, 'datax')
om.datasets.put(Y, 'datay')

# fit locally and store model for comparison
lr = LinearRegression()
lr.fit(X, Y)
pred = lr.predict(X)
om.models.put(lr, 'duplicate')

# train remotely
result = om.runtime.model('duplicate').fit('datax', 'datay')
result.get()

# check the model actually works
# -- using the data on the server
result = om.runtime.model('duplicate').predict('datax')
pred1 = result.get()
# -- using local data
new_x = np.random.randint(0,100,10).reshape(10,1)
result = om.runtime.model('duplicate').predict(new_x)
pred2 = result.get()

assert (pred == pred1).all(), "oh snap, something went wrong!"
assert (new_x * 2 == pred2).all(), "oh snap, something went wrong!"

print "nice, everything works. thank you very much"
df1 = pd.DataFrame(dict(asked=X.x, result=pred1.flatten()), index=range(0, len(X)))
df2 = pd.DataFrame(dict(asked=new_x.flatten(), result=pred2.flatten()), index=range(0, len(X)))
pd.concat([df1, df2]).sort_values('asked')