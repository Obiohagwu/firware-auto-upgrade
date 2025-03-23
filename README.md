# firware-auto-upgrade
automation for device firmware upgrades



## Test version
We are going to start with a test version. Will test on a dummy switch in the office lab.


### How to run
- Install scp (secure copy protocol) via paramiko. scp for copying firmware file to device.
    '''
    pip install paramiko scp
    '''
- Because different devices have different specs, we can make those input variables
'''
python switch_firmware_upgrade.py --hostname switch1 --ip 192.168.1.1 --username admin --model cisco-3750 --firmware ./firmware/switch-firmware-v2.1.bin --target-version 2.1 
'''

'''
Required arguments:
  --hostname       Switch hostname
  --ip             Switch IP address
  --username       SSH username
  --model          Switch model
  --firmware       Path to firmware file
  --target-version Target firmware version

Optional arguments:
  --password       SSH password (if not provided, will prompt securely)
  --remote-path    Remote path to store firmware (default: /flash/)
  --retry-count    Max retry attempts for verification (default: 5)
  --retry-delay    Seconds between retry attempts (default: 60)
'''