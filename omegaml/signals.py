'''
Created on Jun 21, 2015

@author: @gaumire
'''
from django.dispatch.dispatcher import Signal


#: signal sent when a task has started
mltask_start = Signal(providing_args=['name'])
# #: signal sent when a task has ended
mltask_end = Signal(providing_args=['state', 'task'])
#: signal sent when a dataset is put
dataset_put = Signal(providing_args=['name'])
#: signal sent when a dataset is retrieved
dataset_get = Signal(providing_args=['name', 'metakind'])
#: signal sent when a job is scheduled
job_schedule = Signal(providing_args=['name'])
#: signal sent when a job is run
job_run = Signal(providing_args=['name'])
