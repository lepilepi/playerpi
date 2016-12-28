# Prepare SD

## Copy image 

(Replace `/dev/rdisk2`)
`sudo dd bs=1m if=Downloads/2016-11-25-raspbian-jessie-lite.img of=/dev/rdisk2`

## Enable ssh for headless mode

`touch /Volumes/boot/ssh`


# Setup pi

## Create mount dir

`sudo mkdir -p /mnt/usb/`

## Auto-mount with fstab

`sudo nano /etc/fstab`

add these line (replace `/dev/sda/`):
`/dev/sda        /mnt/usb        vfat    auto,nofail,noatime,users,rw,uid=pi,gid=pi 0 0`


## Update fw (optional)
`sudo apt-get install rpi-update`
`sudo rpi-update`

## Improve sound quality (optional)
Edit `/boot/config.txt`, add this line:
`audio_pwm_mode=2`


## Install packages
`sudo apt-get install mpg321 redis-server python-pip`


## Volume
Set volume in `alsamixer` to full, then store it with:
`sudo alsactl store`


## Redis conf
Set `appendonly yes` in `/etc/redis/redis.conf` (for immediate persistence)


## Install python packages
`sudo pip install -r requirements.txt`

## Create log dir
`sudo mkdir -p /var/log/player/`


## Add as a startup script
`sudo nano /etc/rc.local`

Append this BEFORE the `exit 0` line:

`python /home/pi/hangoskonyv/player.py &`
