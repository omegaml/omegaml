# ~/.bashrc: executed by bash(1) for non-login shells.

# kubernets info
alias kinfo="kubectl cluster-info"
alias k="kubectl"

# show active git branch
gb() {
 # >nul will ignore any error messages
 # printf will print this without a new line
 git branch 2>/dev/null | grep "*" | awk '{ if($2=="develop") { printf "(\033[1;32m%s\033[0m)\n",$2 } else {printf "(\033[7;31m%s\033[0m)\n",$2 }}'
}
# activate git branch display for any git repository
export PROMPT_COMMAND=gb
PS1="omegaml-dev \w\$ "

# activate conda env
. /opt/conda/etc/profile.d/conda.sh
conda activate base
conda activate omegamlee
