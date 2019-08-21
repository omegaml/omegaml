#!/usr/bin/env bash
# source https://rancher.com/blog/2018/2018-09-17-rke-k8s-cluster-exoscale/
# create firewall for k8s
exo firewall create rke-k8s -d "RKE k8s SG"
exo firewall add rke-k8s -p ALL -s rke-k8s
exo firewall add rke-k8s -p tcp -P 6443 -c 0.0.0.0/0
exo firewall add rke-k8s -p tcp -P 10240 -c 0.0.0.0/0
exo firewall add rke-k8s ssh
# create firewall for omegaml
exo firewall create omegaml -d "omegaml routing"
exo firewall add omegaml -p ALL -s omegaml
exo firewall add omegaml -p tcp -P 5000 -c 0.0.0.0/0
exo firewall add omegaml -p tcp -P 8888 -c 0.0.0.0/0
# ssh access to instances
exo sshkey create rke-k8s-key
echo "Copy key to $HOME/.ssh/id_rke-k8s-key, then ssh-add"
read -p "Press ENTER when ready, or Ctrl-c and restart" ok
# create instances
for i in 1 2 3 4; do
  exo vm delete rancher-$i -f
  exo vm create rancher-$i \
    --cloud-init-file cloud-init.yml \
    --service-offering medium \
    --template "Ubuntu 16.04 LTS" \
    --security-group "rke-k8s,omegaml" \
    --disk 10 \
    --keypair rke-k8s-key
done
exo vm list

