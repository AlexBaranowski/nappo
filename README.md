# nappo: a chocolate covered nougat
This script is based (like of it 99%) on the work of the @omajid [Original
Gist](https://gist.github.com/omajid/c04b6025de49d0b7b18ab4a7e789484e). It is
used to help bootstrap Dotnet on aarch64 and s390x architecture by creating
tarballs with necessary nuggets.

## Changes for Enterprise Linux 8
This script has small changes explicitly made for EuroLinux or any other
Enterprise Linux 8. You can diff current version with the second (original
import) git commit.

## How to install
```
curl https://raw.githubusercontent.com/AlexBaranowski/nappo/master/nappo.py | sudo tee /usr/bin/nappo
sudo chmod 755 /usr/bin/nappo
# there is a packaging python module that is used
pip3.6 install packaging --user
```
