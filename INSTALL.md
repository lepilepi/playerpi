# Prepare SD

## Copy image 

(Replace `/dev/rdisk2`)
`sudo dd bs=1m if=Downloads/2016-11-25-raspbian-jessie-lite.img of=/dev/rdisk2`

## Enable ssh for headless mode

`touch /Volumes/boot/ssh`


# Setup pi

## Create mount dir

`sudo mkdir -p /mnt/usb/`

## AUto-mount with fstab

`sudo nano /etc/fstab`

add these line (replace `/dev/sda/`):
`/dev/sda        /mnt/usb        vfat    auto,nofail,noatime,users,rw,uid=pi,gid=pi 0 0`


## Install mpg321
`sudo apt-get install mpg321`

## Update fw (optional)
`sudo apt-get install rpi-update`
`sudo rpi-update`

## Improve sound quality (optional)
Edit `/boot/config.txt`, add this line:
`audio_pwm_mode=2`

## Run
`python player.py`
