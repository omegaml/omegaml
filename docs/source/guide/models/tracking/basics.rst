How it works
------------

omega-ml provides experiment and model tracking for development, testing and
production use. The tracking system is designed to be simple and flexible, and
can be used to track experiments, models, and other artifacts. Any data can be
logged to the tracking system, including metrics, parameters, artifacts, system
statistics and more.

The tracking system has three distinct components

1. Experiment: An experiment is a named context, or log, in which data can be
   logged. Experiments are created using the `om.runtime.experiment` context
   manager. This experiment object can be used to log data to the experiment,
   and to retrieve data from the experiment.

2. TrackingProviders: These are the backend storage systems that store the
   tracking data. The default tracking provider logs all data to `om.datasets`.
   Other tracking providers can be added by as a plugin, by subclassing
   `TrackingProvider`.

3. DriftMonitor: The drift monitor builds on the tracking system to provide
   drift detection and monitoring, using the data logged to the tracking system.

