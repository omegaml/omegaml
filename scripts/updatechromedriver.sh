#!/usr/bin/env bash
run=$(which sudo)
if [[ -z `which google-chrome` ]]; then
    # set non interactive install mode
    $run apt update
    $run apt install -y unzip
    echo 'tzdata tzdata/Zones/Europe select Paris' | sudo debconf-set-selections
    echo 'tzdata tzdata/Areas select Europe' | sudo debconf-set-selections
    curl --silent --show-error --location --fail --retry 3 --output /tmp/google-chrome-stable_current_amd64.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
    $run DEBIAN_FRONTEND=noniteractive DEBCONF_NONINTERACTIVE_SEEN=true dpkg -i /tmp/google-chrome-stable_current_amd64.deb
    $run DEBIAN_FRONTEND=noniteractive DEBCONF_NONINTERACTIVE_SEEN=true apt-get -fy install
    $run sed -i 's|HERE/chrome"|HERE/chrome" --disable-setuid-sandbox --no-sandbox|g' "/opt/google/chrome/google-chrome"
fi
google-chrome --version
CHROME_VERSION="$(google-chrome --version)"
export CHROMEDRIVER_RELEASE="$(echo $CHROME_VERSION | sed 's/^Google Chrome //')"
export CHROMEDRIVER_RELEASE=${CHROMEDRIVER_RELEASE%%.*}
CHROMEDRIVER_VERSION=$(curl --silent --show-error --location --fail --retry 4 --retry-delay 5 http://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROMEDRIVER_RELEASE})
curl --silent --show-error --location --fail --retry 4 --retry-delay 5 --output /tmp/chromedriver_linux64.zip "http://chromedriver.storage.googleapis.com/$CHROMEDRIVER_VERSION/chromedriver_linux64.zip"
cd /tmp
unzip chromedriver_linux64.zip
$run rm -rf /usr/local/bin/chromedriver
$run mv chromedriver /usr/local/bin/chromedriver
$run chmod +x /usr/local/bin/chromedriver
# allow users to replace chromedriver with newest version without sudo rights
chromedriver --version
