# Omega|ml 

## Installation steps

####Install Load Balancer

metallb-chart-config.yaml

```
configInline:
  address-pools:
  - name: default
    protocol: layer2
    addresses:
    - 192.168.123.15/32
```

```
helm install --name metallb  -f metallb/metallb-chart-config.yaml   stable/metallb
```

#### Install omegaml

You should set options to override defaults.
Options definition in  a yaml file is possible too.

```
helm install --name omegaml ./omegaml  --namespace omegaml --set image.pullPolicy=Always  --set dockerRegistry.user=omegaml --set dockerRegistry.pass=<registry pass>  --set acmeChallenge="LETSENCRYPT SECRET" --set image.name=omegaml/omegaml-ee --set image.tag=1.2.3  --set localVolumes.enabled=true
```


#### Instalaltion with local PV
If you use local PV, you should  set ```localVolumes.enabled``` to ```true```.
In this case PV will be created after installation. Configuration for this PVs will be gathered from persistent section of particular app (mongo and mysql).
Label for this PVs will be provided from persistence.localVolumePath variable of appropriate app.
Also you must pre-create  dir on node for this PV and set label on this node.


